"""Terminal outcome records shared by human-facing clients.

Preserve repeated labels, branch diagnostics and source-row lineage while exposing
one record for each terminal entity or fan-out leaf. Identifiers are result-local.
"""

from __future__ import annotations

from typing import Any

from braidworks.core.executor import ExecutionResult
from braidworks.core.strand import StrandSet


def strand_record(entity_id: str, status: str, ss: StrandSet, want: list[str]) -> dict[str, Any]:
    # If --want is empty (e.g. `run` with no filter), show everything produced.
    types = want or sorted(ss.available_types())
    values = {t: ss.get(t).value for t in types if ss.get(t) is not None}
    rec: dict[str, Any] = {
        "entity": entity_id,
        "status": status,
        "values": values,
        "source_row": ss.source_row,
        "missing": [t for t in want if not ss.has(t)],
        "requires_review": status == "review" or ss.requires_review,
        "warnings": list(ss.warnings),
        "errors": list(ss.errors),
        "completion": [step.to_json() for step in ss.completion],
        "strands": {t: ss.get(t).to_json() for t in values},
        "diagnostics": [],
        "truncations": [],
        "candidates": [],
        "references": [],
    }
    if ss.parent_id is not None:
        rec["parent"] = ss.parent_id
    return rec


def execution_records(result: ExecutionResult, want: list[str]) -> list[dict[str, Any]]:
    """One record per terminal object; attach branch diagnostics without duplicating rows."""
    terminal: dict[int, tuple[StrandSet, str, Any]] = {}
    for ss in result.resolved:
        terminal[id(ss)] = (ss, "resolved", None)
    for ss, wr in result.unresolved:
        terminal.setdefault(id(ss), (ss, "unresolved", wr))
    for item in result.review_queue:
        terminal.setdefault(
            id(item.strand_set), (item.strand_set, "review", item.triggering_result)
        )
    for error in result.fatal_errors():
        terminal[id(error.strand_set)] = (error.strand_set, "error", None)
    records = []
    for ss, status, wr in terminal.values():
        record = strand_record(ss.entity_id, status, ss, want)
        record["diagnostics"] = [
            {key: value for key, value in error.to_json().items() if key != "strand_set"}
            for error in result.errors
            if error.strand_set is ss
        ]
        record["references"] = [reference.to_json() for reference in result.references]
        record["truncations"] = [
            item.to_json()
            for item in result.truncations
            if (ss.source_row is not None and item.source_row == ss.source_row)
            or (ss.source_row is None and item.entity_id in (ss.entity_id, ss.parent_id))
        ]
        if wr is not None:
            record["candidates"] = [candidate.to_json() for candidate in wr.candidates]
            record["warnings"] = list(dict.fromkeys([*record["warnings"], *wr.warnings]))
            record["errors"] = list(dict.fromkeys([*record["errors"], *wr.errors]))
        records.append(record)
    return number_records(records)


def number_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Stable sort retains sibling order; labels need not be unique.
    records.sort(key=lambda record: record["source_row"] or 0)
    for index, record in enumerate(records, start=1):
        record["outcome"] = f"o{index}"
    return records
