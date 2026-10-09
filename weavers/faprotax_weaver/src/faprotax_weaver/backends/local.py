"""The local backend for faprotax_weaver.

Maps full NCBI lineage names to putative functional groups from bundled
``FAPROTAX.txt``. Source patterns use ordered complete words, so species epithets
can match inside binomial names without substring false positives. Membership
honors ordered add/subtract/intersect operations over earlier defined groups.
A taxon matching no groups is a miss, not evidence that it lacks those functions.

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
from typing import Any

from braidworks.core import BackendBase, LookupRecord

from faprotax_weaver.rules import RuleError, _evaluate, _parse_groups

# The bundled FAPROTAX release. This is the backend's fingerprint source, so it
# must change when the bundled FAPROTAX.txt changes and stay identical otherwise.
DATA_VERSION = "faprotax-1.2.12"
_DATA_FILE = "FAPROTAX.txt"
_FUNCTIONAL_GROUPS = "microbe.ecology.functional_groups"


@lru_cache(maxsize=1)
def _load_rules():
    raw = (files("faprotax_weaver") / "data" / _DATA_FILE).read_text(encoding="utf-8")
    return _parse_groups(raw)


def _load_groups() -> Mapping:
    """Immutable ordered operations; compatibility for local rule inspection."""
    from types import MappingProxyType

    return MappingProxyType({name: group.rules for name, group in _load_rules().items()})


def _functional_groups(lineage_names: list[str]) -> list[str]:
    """Evaluate source word patterns and ordered group set operations."""
    return _evaluate(_load_rules(), lineage_names)


def _lineage_names(value: Any) -> list[str]:
    """Ordered names from an ``ncbi.taxon.lineage`` strand value.

    The strand is a list of ``{taxid, rank, name}`` dicts (root->tip); we read
    ``name``. Plain-string entries are tolerated defensively.
    """
    names: list[str] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                name = entry.get("name")
                if name:
                    names.append(str(name))
            elif isinstance(entry, str) and entry:
                names.append(entry)
    return names


class FaprotaxLocalBackend(BackendBase):
    """Looks up an organism's functional groups in the bundled FAPROTAX DB.

    Always configured — the data ships inside the package, so there is nothing
    to download or open.
    """

    name = "local"

    def is_configured(self) -> bool:
        return True

    def fingerprint(self) -> str:
        return f"faprotax-local-{DATA_VERSION}"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        return await asyncio.to_thread(self._fetch_sync, queries)

    def _fetch_sync(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        matches: dict[tuple[str, ...], tuple[str, ...]] = {}
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            names = _lineage_names(query.get("ncbi.taxon.lineage"))
            key = tuple(name.lower() for name in names)
            if key not in matches:
                try:
                    matches[key] = tuple(_functional_groups(names)) if names else ()
                except RuleError as exc:
                    records.append(
                        LookupRecord(query=query, error=f"Invalid FAPROTAX rules: {exc}")
                    )
                    continue
            groups = list(matches[key])
            if groups:
                records.append(
                    LookupRecord(query=query, found=True, values={_FUNCTIONAL_GROUPS: groups})
                )
            else:  # no known-function clade in the lineage — a normal miss
                records.append(LookupRecord(query=query, found=False))
        return records
