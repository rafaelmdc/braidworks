"""The local backend for faprotax_weaver.

Maps an organism's NCBI lineage to FAPROTAX functional groups, from the bundled
``FAPROTAX.txt``. FAPROTAX defines ~90 functional groups, each as a list of
member taxon patterns (``*Level*Level*`` — an ordered, case-insensitive
subsequence over a taxon's lineage names). A taxon is affiliated with a group if
any of that group's patterns is a subsequence of the taxon's lineage. Groups may
compose others via ``add_group:``, resolved recursively at load. A taxon matching
zero groups is a miss (FAPROTAX only annotates clades of known function).

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

from braidworks.core import BackendBase, LookupRecord

# The bundled FAPROTAX release. This is the backend's fingerprint source, so it
# must change when the bundled FAPROTAX.txt changes and stay identical otherwise.
DATA_VERSION = "faprotax-1.2.12"
_DATA_FILE = "FAPROTAX.txt"
_FUNCTIONAL_GROUPS = "microbe.ecology.functional_groups"


@lru_cache(maxsize=1)
def _load_groups() -> dict[str, tuple[tuple[str, ...], ...]]:
    """Parse the bundled FAPROTAX.txt into ``{group_name: (member_patterns,)}``.

    A member pattern is a tuple of lowercased taxon tokens (from ``*A*B*``).
    ``add_group:`` references are flattened recursively (cycle-guarded), so each
    group carries the full set of patterns it and its included groups define.
    """
    raw = (files("faprotax_weaver") / "data" / _DATA_FILE).read_text(encoding="utf-8")

    # First pass: group -> ordered list of members, each ("taxa", tokens) or
    # ("group", referenced_group_name).
    parsed: dict[str, list[tuple[str, Any]]] = {}
    current: str | None = None
    for line in raw.splitlines():
        line = line.split("#", 1)[0].rstrip()  # drop full-line and inline comments
        if not line.strip():
            continue
        if line.startswith("*"):  # member taxon pattern: *Level1*Level2*
            tokens = tuple(t.lower() for t in line.strip().strip("*").split("*") if t)
            if current is not None and tokens:
                parsed[current].append(("taxa", tokens))
        elif line.lstrip().startswith("add_group:"):  # compose another group
            ref = line.split("add_group:", 1)[1].strip()
            if current is not None and ref:
                parsed[current].append(("group", ref))
        elif not line[0].isspace():  # group header at column 0: name<TAB>attrs
            current = line.split("\t", 1)[0].split()[0].strip()
            parsed.setdefault(current, [])

    # Second pass: flatten add_group references into concrete pattern sets.
    resolved: dict[str, tuple[tuple[str, ...], ...]] = {}

    def patterns_for(name: str, seen: frozenset[str]) -> list[tuple[str, ...]]:
        if name in resolved:
            return list(resolved[name])
        if name in seen:  # cycle guard
            return []
        seen = seen | {name}
        out: list[tuple[str, ...]] = []
        for kind, value in parsed.get(name, []):
            if kind == "taxa":
                out.append(value)
            else:
                out.extend(patterns_for(value, seen))
        return out

    for name in parsed:
        resolved[name] = tuple(patterns_for(name, frozenset()))
    return resolved


def _is_subsequence(pattern: tuple[str, ...], lineage_lower: list[str]) -> bool:
    """True if every pattern token appears in ``lineage_lower`` in order."""
    it = iter(lineage_lower)
    return all(any(token == name for name in it) for token in pattern)


def _functional_groups(lineage_names: list[str]) -> list[str]:
    """The sorted FAPROTAX functional groups affiliated with this lineage."""
    lineage_lower = [n.lower() for n in lineage_names]
    return sorted(
        group
        for group, patterns in _load_groups().items()
        if any(_is_subsequence(p, lineage_lower) for p in patterns)
    )


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
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            names = _lineage_names(query.get("ncbi.taxon.lineage"))
            groups = _functional_groups(names) if names else []
            if groups:
                records.append(
                    LookupRecord(query=query, found=True, values={_FUNCTIONAL_GROUPS: groups})
                )
            else:  # no known-function clade in the lineage — a normal miss
                records.append(LookupRecord(query=query, found=False))
        return records
