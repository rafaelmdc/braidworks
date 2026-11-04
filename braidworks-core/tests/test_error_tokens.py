"""Status classification must not treat biological identifiers as HTTP failures."""

import pytest
from braidworks.core.errors import ErrorCategory, classify_error


@pytest.mark.parametrize(
    "message",
    [
        "lookup failed for taxid 1500123",
        "lookup failed for AF-P40300",
        "query abc429def failed",
        "release 5.0.0 failed",
        "file model_503.xml failed",
    ],
)
def test_identifier_digits_are_not_statuses(message):
    assert classify_error(message) is ErrorCategory.UNKNOWN


@pytest.mark.parametrize(
    "message,category",
    [
        (
            "HTTPStatusError: Server error '503 Service Unavailable'",
            ErrorCategory.UPSTREAM_UNAVAILABLE,
        ),
        ("HTTP 507", ErrorCategory.UPSTREAM_UNAVAILABLE),
        ("429", ErrorCategory.RATE_LIMITED),
        ("HTTP 401: no API key", ErrorCategory.AUTH),
        ("no API key configured", ErrorCategory.CONFIG),
        ("missing configuration", ErrorCategory.CONFIG),
        ("HTTP 404", ErrorCategory.NOT_FOUND),
        ("taxid 1500123: ReadTimeout", ErrorCategory.TIMEOUT),
    ],
)
def test_status_tokens_and_specific_configuration(message, category):
    assert classify_error(message) is category
