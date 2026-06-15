"""Error classification — turn an opaque failure string into a category + plain-English
explanation, so the executor and CLI can report *what went wrong* instead of leaking a
raw stack-trace fragment.

Weavers surface failures as strings (``LookupRecord.error`` -> ``WeaveResult.errors``),
so classification here is deliberately string-based: it reads the message a backend
already produced (which usually embeds the HTTP status or the exception name) rather
than requiring every weaver to pass a structured error. A backend *may* later attach a
category at the source for precision, but this gives broad coverage with no weaver churn.
"""

from __future__ import annotations

from enum import Enum


class ErrorCategory(Enum):
    """A coarse, actionable bucket for why a step failed (not an exception type)."""

    UPSTREAM_UNAVAILABLE = "upstream_unavailable"  # the data source 5xx'd / is down
    RATE_LIMITED = "rate_limited"  # 429 / too-many-requests
    TIMEOUT = "timeout"  # the request did not complete in time
    NETWORK = "network"  # could not reach the host (DNS/connection)
    AUTH = "auth"  # 401/403 — key or permission required
    NOT_FOUND = "not_found"  # 404 — usually a NO_MATCH, occasionally an error
    BAD_RESPONSE = "bad_response"  # parsed but unexpected shape (possible API drift)
    CONFIG = "config"  # the backend is misconfigured locally
    INPUT = "input"  # the entity lacked a required input
    UNKNOWN = "unknown"  # unclassified — fall back to the raw message


# Substrings (lower-cased) that map a raw message to a category, most-specific first.
# Order matters: a "503 ... timeout" reads as UPSTREAM_UNAVAILABLE before TIMEOUT.
_SIGNATURES: tuple[tuple[ErrorCategory, tuple[str, ...]], ...] = (
    (ErrorCategory.RATE_LIMITED, ("429", "too many requests", "rate limit")),
    (ErrorCategory.AUTH, ("401", "403", "unauthorized", "forbidden", "api key", "apikey")),
    (
        ErrorCategory.UPSTREAM_UNAVAILABLE,
        ("500", "502", "503", "504", "internal server error", "bad gateway",
         "service unavailable", "serviceunavailable", "server error"),
    ),
    (ErrorCategory.TIMEOUT, ("timeout", "timed out", "read timeout", "connect timeout")),
    (
        ErrorCategory.NETWORK,
        ("connection", "connecterror", "name or service not known", "getaddrinfo",
         "failed to resolve", "network is unreachable", "could not reach"),
    ),
    (ErrorCategory.NOT_FOUND, ("404", "not found")),
    (
        ErrorCategory.BAD_RESPONSE,
        ("jsondecode", "expecting value", "invalid json", "unexpected", "keyerror",
         "schema", "missing key"),
    ),
    (ErrorCategory.CONFIG, ("not configured", "misconfigur", "no api key", "missing config")),
)


def classify_error(message: str | None) -> ErrorCategory:
    """Bucket a raw failure message. Returns ``UNKNOWN`` when nothing matches."""
    if not message:
        return ErrorCategory.UNKNOWN
    text = message.lower()
    for category, needles in _SIGNATURES:
        if any(n in text for n in needles):
            return category
    return ErrorCategory.UNKNOWN


# Transient / availability failures: not a sign the integration is broken, and they can
# happen from anywhere (a slow network, a throttled IP), so a live test treats them as a
# *green-lightable warning* rather than a hard failure. A 5xx (UPSTREAM_UNAVAILABLE), an
# auth error, or a bad response shape is deliberately NOT here — those mean something is
# actually wrong and should fail loudly.
GREENLIGHTABLE_CATEGORIES = frozenset(
    {ErrorCategory.TIMEOUT, ErrorCategory.NETWORK, ErrorCategory.RATE_LIMITED}
)


def is_greenlightable(category: ErrorCategory) -> bool:
    """True for transient connectivity failures a human can wave through (timeout /
    connection / rate-limit) — as opposed to a real contract or server error."""
    return category in GREENLIGHTABLE_CATEGORIES


def classify_status(status_code: int) -> ErrorCategory:
    """Map an HTTP status to a category (429 → rate-limit, 5xx → upstream, 401/3 → auth)."""
    if status_code == 429:
        return ErrorCategory.RATE_LIMITED
    if status_code in (401, 403):
        return ErrorCategory.AUTH
    if status_code == 404:
        return ErrorCategory.NOT_FOUND
    if 500 <= status_code < 600:
        return ErrorCategory.UPSTREAM_UNAVAILABLE
    return ErrorCategory.UNKNOWN


def classify_exception(exc: BaseException) -> ErrorCategory:
    """Classify an exception by its *type* (and HTTP status if it carries one) — robust
    where the message is empty, which is exactly how httpx raises timeouts (``str()`` is
    ``''``). Inspects the class name so core needs no ``httpx`` dependency; falls back to
    the message text. ``ReadTimeout`` → TIMEOUT, ``ConnectError`` → NETWORK,
    ``HTTPStatusError`` → by ``response.status_code``."""
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return ErrorCategory.TIMEOUT
    if "connect" in name or "network" in name:
        return ErrorCategory.NETWORK
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return classify_status(status)
    return classify_error(str(exc) or name)


def format_exc(exc: BaseException) -> str:
    """A never-empty, classifiable message for an exception. httpx timeouts stringify to
    ``''``; this prefixes the type name so the failure is legible and ``classify_error``
    can bucket it (``ReadTimeout`` contains 'timeout', etc.)."""
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def skip_if_transient(result: object) -> None:
    """For live (network) tests: skip with a green-lightable note when ``result`` is an
    ERROR caused by a transient connectivity failure (timeout / connection / rate-limit),
    so a flaky upstream doesn't read as a code regression. A 5xx / schema / auth error is
    left alone — the test's own assertions fail it loudly. Duck-typed on
    ``result.status``/``result.errors``; imports pytest lazily so core stays test-free."""
    import pytest

    status = getattr(result, "status", None)
    if getattr(status, "name", "") != "ERROR":
        return
    message = "; ".join(getattr(result, "errors", ()) or ())
    category = classify_error(message)
    if is_greenlightable(category):
        pytest.skip(
            f"upstream {category.value} — green-light if expected: {message or category.value}"
        )


def explain_error(category: ErrorCategory, *, source: str | None = None) -> str:
    """A one-line, plain-English explanation for a category, naming ``source`` if given."""
    who = source or "the data source"
    return {
        ErrorCategory.UPSTREAM_UNAVAILABLE: (
            f"{who} is temporarily unavailable (upstream server error) — this is on the "
            f"source's side, so retry later."
        ),
        ErrorCategory.RATE_LIMITED: (
            f"{who} rate-limited the request (too many requests) — slow down or supply "
            f"an API key."
        ),
        ErrorCategory.TIMEOUT: (
            f"{who} did not respond in time (timeout) — the service may be slow or "
            f"unreachable."
        ),
        ErrorCategory.NETWORK: (
            f"could not reach {who} (network/connection error) — check connectivity."
        ),
        ErrorCategory.AUTH: (
            f"{who} rejected the request (authentication/permission) — an API key or "
            f"credentials may be required."
        ),
        ErrorCategory.NOT_FOUND: f"{who} has no data for this identifier.",
        ErrorCategory.BAD_RESPONSE: (
            f"{who} returned an unexpected response (possible API change) — the backend "
            f"may need updating against the live API."
        ),
        ErrorCategory.CONFIG: f"{who} is not configured correctly on this machine.",
        ErrorCategory.INPUT: "a required input strand was missing.",
        ErrorCategory.UNKNOWN: f"{who} failed for an unrecognized reason.",
    }[category]
