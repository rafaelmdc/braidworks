"""Terminal outcome records shared by human-facing clients.

Preserve repeated labels, branch diagnostics and source-row lineage while exposing
one record for each terminal entity or fan-out leaf. Identifiers are result-local.
"""

from __future__ import annotations

from typing import Any

from braidworks.core.errors import ErrorCategory, explain_error
from braidworks.core.executor import ExecutionResult
from braidworks.core.listing import Listing
from braidworks.core.strand import StrandSet

# Statuses whose rows carry an outcome worth explaining: what they matched and why a
# field is missing (an unresolved or paused row is explained by its status).
_EXPLAINED_STATUSES = frozenset({"resolved", "error"})


def strand_record(
    entity_id: str,
    status: str,
    ss: StrandSet,
    want: list[str],
    identity: tuple[str, ...] = (),
) -> dict[str, Any]:
    # If --want is empty (e.g. `run` with no filter), show everything produced.
    types = want or sorted(ss.available_types())
    values = {t: ss.get(t).as_value() for t in types if ss.get(t) is not None}
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
        # Size of every sized list shown here (a Listing): its true total and whether
        # this record holds all of it.
        "totals": {
            t: {"total": v.total, "complete": v.complete}
            for t, v in values.items()
            if isinstance(v, Listing)
        },
    }
    # What the input was matched to: the identifying values its first step always
    # returns (an accession, a species), shown so a name-based match can be checked.
    if status in _EXPLAINED_STATUSES:
        rec["matched"] = {
            t: ss.get(t).as_value() for t in identity if t not in want and ss.get(t) is not None
        }
    if ss.parent_id is not None:
        rec["parent"] = ss.parent_id
    return rec


def execution_records(
    result: ExecutionResult, want: list[str], identity: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
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
        record = strand_record(ss.entity_id, status, ss, want, identity)
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


def missing_reasons(
    record: dict[str, Any], producers: dict[str, list[tuple[str, str]]]
) -> dict[str, str]:
    """Why each requested field is absent from a resolved or error record.

    ``producers`` maps a field to the ``(source, capability)`` steps of the route that
    produce it. The reason comes from what that step did for this entity: it failed
    (with the error's plain-English explanation), found no match, was not reached
    because an earlier step returned nothing, or ran without returning the field.
    """
    if record["status"] not in _EXPLAINED_STATUSES or not record["missing"]:
        return {}
    steps = {step["capability_id"]: step for step in record["completion"]}
    failures = {
        error["capability_id"]: error
        for error in record["diagnostics"]
        if error.get("capability_id") and not error.get("recovered")
    }
    sources = {cap: source for pairs in producers.values() for source, cap in pairs}
    reasons: dict[str, str] = {}
    for field in record["missing"]:
        for source, capability in producers.get(field, ()):
            step = steps.get(capability)
            if step is None:
                continue
            reason = _step_reason(source, step["status"], failures.get(capability))
            upstream = next(
                (cap for cap, step in steps.items() if cap != capability and cap in failures),
                None,
            )
            if step["status"] == "skipped" and upstream is not None:
                # Not reached because an earlier step failed: name that failure, not
                # just the gap it left.
                cause = _step_reason(
                    sources.get(upstream, upstream.split(".")[0]), "error", failures[upstream]
                )
                reason = f"{source} was not reached because {cause}"
            reasons[field] = reason
            break
    return reasons


def _step_reason(source: str, status: str, failure: dict[str, Any] | None) -> str:
    if status == "error" or failure is not None:
        category = ErrorCategory(failure["category"]) if failure else ErrorCategory.UNKNOWN
        if category is ErrorCategory.CONFIG:
            return f"{source} is not set up on this machine (run `braidworks doctor`)"
        return explain_error(category, source=source)
    if status == "no_match":
        return f"{source} has no match"
    if status == "skipped":
        return f"{source} was not reached: an earlier step returned nothing to start from"
    return f"{source} returned no value"


def route_identity(prepared, registry) -> tuple[str, ...]:
    """Fields that identify what each input matched, declared by the sources.

    For every route step that starts from a row's own input, the outputs of the step's
    always-computed groups (UniProt's ``identity`` group: accession, gene, organism),
    which every call returns whatever was requested.
    """
    fields: set[str] = set()
    for braid, indices in prepared.plans:
        if not indices:
            continue
        given = prepared.request.inputs[indices[0]].available_types()
        for step in braid.steps:
            if not step.input_types <= given:
                continue
            try:
                capability = registry.get_capability(step.weaver_id, step.capability_id)
            except KeyError:  # a step the registry no longer declares adds nothing
                continue
            for group in capability.output_groups:
                if group.id in capability.always_computed_groups:
                    fields |= group.outputs
    # Identifiers other sources join on (an accession) first, then descriptive fields.
    joins = {t for m in registry.manifests() for c in m.capabilities for t in c.consumes}
    return tuple(sorted(fields, key=lambda t: (t not in joins, t)))


def route_producers(braids) -> dict[str, list[tuple[str, str]]]:
    """``{field: [(source, capability), ...]}`` for every step of the given routes."""
    producers: dict[str, list[tuple[str, str]]] = {}
    for braid in braids:
        for step in braid.steps:
            for field in sorted(step.output_types):
                pair = (step.weaver_id, step.capability_id)
                if pair not in producers.setdefault(field, []):
                    producers[field].append(pair)
    return producers


def number_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Stable sort retains sibling order; labels need not be unique.
    records.sort(key=lambda record: record["source_row"] or 0)
    for index, record in enumerate(records, start=1):
        record["outcome"] = f"o{index}"
    return records
