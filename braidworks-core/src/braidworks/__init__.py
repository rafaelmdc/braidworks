"""Braidworks: retrieve and connect biological data across databases.

    import braidworks as bw

    result = bw.get(["P04637", "TP53"], have="protein.query",
                    want=["protein.name", "structure.pdb.ids"], organism="9606")
    result.to_pandas()

``get`` routes through the installed sources and returns a :class:`Result` table.
:class:`Session` reuses sources and settings across queries. ``braidworks.weaver`` is
the import for weaver authors; ``braidworks.core`` is the full engine. ``fetch`` remains
for existing code.
"""

from braidworks._result import Result
from braidworks._session import Session, async_get, find, get, path, sources
from braidworks.core.fetch import FetchResult, async_fetch, fetch
from braidworks.core.listing import Listing

__all__ = [
    "FetchResult",
    "Listing",
    "Result",
    "Session",
    "async_fetch",
    "async_get",
    "fetch",
    "find",
    "get",
    "path",
    "sources",
]
