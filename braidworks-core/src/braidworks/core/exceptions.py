"""Braidworks exception hierarchy.

The split between these mirrors the failure model in the architecture:

- ``BackendConfigurationError`` is a *run-level* failure. A declared, configured
  backend is broken at runtime (corrupt DB, bad credentials, unreachable host).
  The executor re-raises it immediately and aborts. It is never per-entity and
  never triggers fallback.
- ``BackendUnavailable`` means a declared backend is simply not configured in
  *this* instance. The executor may fall back to the next backend if
  ``FallbackCondition.BACKEND_UNAVAILABLE`` is set.
- Per-entity weaver failures are *not* exceptions; they are
  ``WeaveStatus.ERROR`` results.

Planning and registration failures (``NoPathError``, ``NoPlanError``,
``InvalidManifestError``) surface at plan/register time, never at runtime.
"""

from __future__ import annotations


class BraidworksError(Exception):
    """Base class for all Braidworks errors."""


class BackendConfigurationError(BraidworksError):
    """A configured backend is broken at runtime. Run-level: aborts the executor.

    Never per-entity, never triggers fallback, never appears in ``fallback_on``.
    """


class BackendUnavailable(BraidworksError):
    """A declared backend is not configured in this particular weaver instance.

    Distinct from ``InvalidManifestError``: the manifest correctly declares a
    backend the class implements; it is just not wired up in this instance. The
    executor may fall back if ``FallbackCondition.BACKEND_UNAVAILABLE`` is set.
    """


class NoPathError(BraidworksError):
    """No route exists through the capability graph to a requested target type."""


class NoPlanError(BraidworksError):
    """A route exists but no valid backend can be assigned under the policy.

    Raised at plan time, not runtime. E.g. ``LOCAL_ONLY`` against a capability
    that only declares ``("api",)``.
    """


class UnsupportedCapability(BraidworksError):
    """A capability id was requested that the weaver does not implement."""


class ReviewRequired(BraidworksError):
    """Raised by the executor under ``ReviewPolicy.RAISE`` when a result needs review."""


class MissingInputError(BraidworksError):
    """An entity lacks the starting strand types required by a braid (preflight)."""


class InvalidManifestError(BraidworksError):
    """A weaver manifest failed validation at ``register()`` time."""


class CapabilityUnavailableWarning(UserWarning):
    """A registered weaver declares capabilities it cannot offer as configured.

    Emitted at registration so the gap is visible *before* a fetch fails with what looks
    like a missing capability. Silence with ``warnings.filterwarnings`` if the omission is
    deliberate (e.g. an offline-only deployment).
    """
