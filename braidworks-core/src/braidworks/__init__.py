"""Braidworks: a composable network of typed biological data resolvers.

The high-level convenience surface is re-exported here so a consumer can write
``braidworks.fetch(want, ids)`` without reaching into ``braidworks.core``. The full
planning/execution API stays available under ``braidworks.core``.
"""

from braidworks.core.fetch import FetchResult, async_fetch, fetch

__all__ = ["fetch", "async_fetch", "FetchResult"]
