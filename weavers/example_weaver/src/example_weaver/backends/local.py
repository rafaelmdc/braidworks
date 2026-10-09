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
from io import StringIO
from typing import Any

from braidworks.core import BackendBase, LookupRecord, format_exc

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


class _InvalidTable(ValueError):
    """The bundled teaching source violates its declared CSV schema."""


def _parse_table(raw: str) -> dict[str, dict[str, str]]:
    """Pure CSV normalization: strict headers/rows and unique positive taxids.

    Column order is irrelevant. Blank trait cells mean absent values. Empty data
    with a valid header is allowed; malformed source is never interpreted as a miss.
    """
    reader = csv.DictReader(StringIO(raw), strict=True)
    required = {"tax_id", *_COLUMNS}
    table: dict[str, dict[str, str]] = {}
    try:
        headers = reader.fieldnames or []
        if len(headers) != len(required) or set(headers) != required:
            raise _InvalidTable(
                "Example CSV requires unique tax_id, gram_stain, optimum_temp headers"
            )
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise _InvalidTable(f"Example CSV row {reader.line_num} has missing or extra cells")
            raw_taxid = row["tax_id"].strip()
            if not raw_taxid.isascii() or not raw_taxid.isdecimal() or int(raw_taxid) <= 0:
                raise _InvalidTable(f"Example CSV row {reader.line_num} requires a positive taxid")
            taxid = str(int(raw_taxid))
            if taxid in table:
                raise _InvalidTable(f"Example CSV row {reader.line_num} repeats a taxid")
            table[taxid] = {type_id: row[col] for col, type_id in _COLUMNS.items() if row[col]}
    except csv.Error as exc:
        raise _InvalidTable(f"Example CSV is malformed: {exc}") from exc
    return table


@lru_cache(maxsize=1)
def _load_table() -> dict[str, dict[str, str]]:
    """Read bundled data once; cached parsed data stays private to the backend."""
    raw = (files("example_weaver") / "data" / _DATA_FILE).read_text(encoding="utf-8")
    return _parse_table(raw)


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
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # This lookup has no expensive path, so groups_to_compute is unused here;
        # the mapper still filters to the requested outputs.
        try:
            table = _load_table()
        except (OSError, UnicodeError, _InvalidTable) as exc:
            error = f"Example source error: {format_exc(exc)}"
            return [LookupRecord(query=query, error=error) for query in queries]
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            taxid = str(query.get("ncbi.taxon.id"))
            values = table.get(taxid)
            if values is None:
                records.append(LookupRecord(query=query, found=False))  # a miss is normal
            else:
                records.append(LookupRecord(query=query, found=True, values=dict(values)))
        return records
