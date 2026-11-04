"""Worker retry decisions for explicitly transient transport exceptions.

Source HTTP status/result policy stays in backends. Unknown exceptions are not
assumed transient; a message containing 'timeout' is not a retry signal.
"""

from __future__ import annotations

from braidworks.core.exceptions import BraidworksError
from redis.exceptions import AuthenticationError, AuthorizationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

# httpx is a source backend dependency, not a required worker dependency. Its
# concrete transport types are recognized when installed; no status-code policy
# or message-based classification belongs at this boundary.
try:
    from httpx import NetworkError, TimeoutException
except ImportError:  # workers serving non-HTTP sources do not need httpx
    _HTTP_TRANSIENT: tuple[type[Exception], ...] = ()
else:
    _HTTP_TRANSIENT = (NetworkError, TimeoutException)

_TRANSIENT = (
    ConnectionError,
    TimeoutError,
    RedisConnectionError,
    RedisTimeoutError,
    *_HTTP_TRANSIENT,
)


def should_retry(exc: Exception) -> bool:
    """Retry only known connection/timeout failures; domain errors take precedence."""
    return not isinstance(
        exc, (BraidworksError, AuthenticationError, AuthorizationError)
    ) and isinstance(exc, _TRANSIENT)
