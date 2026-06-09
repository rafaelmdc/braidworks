"""The local backend for example_weaver — a *worked reference implementation*.

This is the fully-implemented counterpart to what `weaverkit new` leaves as a
stub: a real ``fetch`` and ``fingerprint`` over a small bundled CSV. Read it
end-to-end to see the shape an agent should produce — then map the same pattern
onto your own source. The contract for each method is in
weaverkit/docs/implementing-backends.md.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from importlib.resources import files
from typing import Any

from braidworks.core import BackendBase, LookupRecord

# Bump this whenever the bundled data changes — it is the backend's fingerprint,
# so it must change when the data changes and stay identical for identical data.
DATA_VERSION = "example-traits-2026-06-07"
_DATA_FILE = "example_traits.csv"

# CSV column -> the produced strand type_id it maps to. Keeping this table here
# (not scattered through fetch) is what makes the mapping auditable.
_COLUMNS = {
    "gram_stain": "microbe.trait.gram_stain",
    "optimum_temp": "microbe.trait.optimum_temp",
}


@lru_cache(maxsize=1)
def _load_table() -> dict[str, dict[str, str]]:
    """taxid -> {produced_type_id: value}, parsed once from the bundled CSV."""
    raw = (files("example_weaver") / "data" / _DATA_FILE).read_text(encoding="utf-8")
    table: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(raw.splitlines()):
        table[row["tax_id"]] = {
            type_id: row[col] for col, type_id in _COLUMNS.items() if row.get(col)
        }
    return table


class ExampleLocalBackend(BackendBase):
    """Looks up taxon traits in the bundled CSV.

    Always configured — the data ships inside the package, so there is nothing to
    download. A real local backend would instead check that its DB file exists.
    """

    name = "local"

    def is_configured(self) -> bool:
        return True

    def fingerprint(self) -> str:
        return f"example-local-{DATA_VERSION}"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[LookupRecord]:
        # This lookup has no expensive path, so groups_to_compute is unused here;
        # the mapper still filters to the requested outputs.
        table = _load_table()
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            taxid = str(query.get("ncbi.taxon.id"))
            values = table.get(taxid)
            if values is None:
                records.append(LookupRecord(query=query, found=False))  # a miss is normal
            else:
                records.append(LookupRecord(query=query, found=True, values=dict(values)))
        return records
