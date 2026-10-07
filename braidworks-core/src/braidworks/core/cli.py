"""The ``braidworks`` command-line interface — query and inspect the weaver network.

Designed for the bash-native researcher: build a strand and get results without
writing Python. Inputs come from flags, a file (one value per line, or a CSV/TSV
with type-id columns), or stdin; results print as a human table by default or as
``--json`` / ``--jsonl`` / ``--tsv`` / ``--csv`` for piping into ``jq`` / pandas.
Progress and counts go to **stderr** so stdout stays clean, pipeable data.

Subcommands
  weave   plan a route from what you HAVE to what you WANT, across all weavers, and run it
  run     call ONE weaver capability directly (no routing)
  weavers list installed weavers and their capabilities
  keys    list the strand types that flow between weavers (who produces / consumes)
  path    show the route from one type to another without running it
  references  print source citations for the installed weavers

The registry is discovered from installed ``braidworks.weavers`` entry points, so a
freshly ``pip install``-ed weaver shows up with no code change.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import sqlite3
import sys
from collections.abc import Sequence
from typing import Any

from braidworks.core.archive import begin_archive, write_archive
from braidworks.core.braid import BackendPolicy
from braidworks.core.cache_policy import CachePolicy
from braidworks.core.discovery import build_registry_from_entry_points
from braidworks.core.errors import classify_error, explain_error
from braidworks.core.exceptions import BraidworksError, NoPathError, NoPlanError
from braidworks.core.executor import (
    ExecutionError,
    ExecutionResult,
    ExpandPolicy,
    ReviewPolicy,
)
from braidworks.core.inputs import read_input_rows
from braidworks.core.outcomes import (
    execution_records as _result_records,
)
from braidworks.core.outcomes import (
    number_records as _number_records,
)
from braidworks.core.outcomes import (
    strand_record as _record,
)
from braidworks.core.parameters import map_parameter_items
from braidworks.core.persistence_options import QueryPersistence, execute_managed_query
from braidworks.core.persistent_query import continue_run
from braidworks.core.planner import Braider
from braidworks.core.query import (
    QueryOptions,
    QueryRequest,
    normalize_expansion,
    prepare_query,
)
from braidworks.core.references import (
    format_references,
    references_for,
)
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveStatus
from braidworks.core.review import ReviewDecision
from braidworks.core.run_store import SQLiteRunStore, run_status
from braidworks.core.runner import validate_batch_size
from braidworks.core.strand import StepOutcome, Strand, StrandSet


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _split_types(value: str | None) -> list[str]:
    """Parse a comma/space-separated ``--want a,b c`` list, order-preserving."""
    if not value:
        return []
    parts = value.replace(",", " ").split()
    seen: dict[str, None] = {}
    for p in parts:
        seen.setdefault(p, None)
    return list(seen)


def _parse_kv(item: str) -> tuple[str, str]:
    """Parse ``TYPE=VALUE`` (value may itself contain ``=``)."""
    if "=" not in item:
        raise SystemExit(f"error: expected TYPE=VALUE, got {item!r}")
    key, _, val = item.partition("=")
    key = key.strip()
    if not key:
        raise SystemExit(f"error: empty type in {item!r}")
    return key, val


def _parse_params(items: list[str] | None) -> list[tuple[str | None, str, str]]:
    """Parse ``--param`` values into ``(capability_id | None, name, value)`` triples.

    Forms: ``name=value`` (applies to whichever step declares ``name``) or
    ``capability_id:name=value`` (targets one capability).
    """
    out: list[tuple[str | None, str, str]] = []
    for item in items or []:
        key, _, value = item.partition("=")
        if "=" not in item:
            raise SystemExit(f"error: expected --param NAME=VALUE, got {item!r}")
        cap_id, sep, name = key.partition(":")
        if sep:
            out.append((cap_id.strip(), name.strip(), value))
        else:
            out.append((None, key.strip(), value))
    return out


def _expand_policy(spec: str) -> ExpandPolicy:
    """Parse ``--expand``: ``none`` (default best-one), ``all``, or ``top:K``."""
    spec = (spec or "none").strip().lower()
    if spec in ("none", "top", "best", "1"):
        return ExpandPolicy()
    if spec == "all":
        return ExpandPolicy.all()
    if spec.startswith("top:"):
        try:
            k = int(spec.split(":", 1)[1])
        except ValueError:
            raise SystemExit(f"error: --expand top:K needs an integer, got {spec!r}")
        return ExpandPolicy.top_k(k)
    raise SystemExit(f"error: --expand expects none | all | top:K, got {spec!r}")


def _load_registry(only: str | None) -> BraidRegistry:
    names = frozenset(_split_types(only)) if only else None
    registry = build_registry_from_entry_points(only=names)
    if not registry.manifests():
        _err(
            "no weavers installed (nothing advertises the 'braidworks.weavers' entry "
            "point). Install a weaver package, e.g. `uv pip install -e weavers/pdbe_weaver`."
        )
        raise SystemExit(1)
    return registry


# --------------------------------------------------------------------------- #
# input collection: flags + file/stdin (the batch UX)
# --------------------------------------------------------------------------- #
def _open_input(path: str) -> io.TextIOBase:
    if path == "-":
        return sys.stdin
    return open(path, newline="")


def _rows_from_file(path: str, in_type: str | None) -> list[dict[str, str]]:
    """Read a batch input file into a list of ``{type_id: value}`` rows.

    Two shapes:
      * ``--in-type T`` set → **one value per line** (blank lines and ``#`` comments
        skipped); each line becomes ``{T: line}``.
      * otherwise → a **delimited table** whose header row is type-ids (``.csv`` =
        comma, anything else = tab); each data row becomes ``{type: value}`` for the
        non-empty cells.
    """
    handle = _open_input(path)
    try:
        delimiter = None if path == "-" else "," if path.endswith(".csv") else "\t"
        return read_input_rows(handle, input_type=in_type, delimiter=delimiter)
    except ValueError as exc:
        raise SystemExit(f"error: {path}: {exc}") from exc
    finally:
        if handle is not sys.stdin:
            handle.close()


def _collect_inputs(args: argparse.Namespace) -> list[StrandSet]:
    """Build the StrandSets to run from ``--have`` constants and/or a batch file.

    ``--have TYPE=VAL`` (repeatable) are *constants* broadcast onto every entity; a
    ``--in-file`` (or stdin via ``-``) supplies the per-entity strands. With no file,
    the constants alone form a single entity.
    """
    constants = dict(_parse_kv(item) for item in (args.have or []))
    sets: list[StrandSet] = []

    if args.in_file:
        rows = _rows_from_file(args.in_file, args.in_type)
        if not rows:
            _err(f"warning: no input rows read from {args.in_file}")
        for i, row in enumerate(rows, start=1):
            merged = {**constants, **row}
            # A one-value-per-line batch reads better regrouped by the value itself.
            ident = row[args.in_type] if args.in_type else f"e{i}"
            sets.append(StrandSet.from_strands(ident, [Strand(t, v) for t, v in merged.items()]))
    else:
        if not constants:
            raise SystemExit("error: nothing to run — pass --have TYPE=VALUE or --in-file PATH")
        sets.append(StrandSet.from_strands("e1", [Strand(t, v) for t, v in constants.items()]))
    for index, ss in enumerate(sets, start=1):
        ss.source_row = index
    return sets


# --------------------------------------------------------------------------- #
# output: one record per entity, rendered per --format
# --------------------------------------------------------------------------- #
def _cell(value: Any) -> str:
    """Flatten a value for a TSV/CSV/human cell (lists join with ``;``)."""
    if isinstance(value, list):
        return "; ".join(_cell(v) for v in value)
    if isinstance(value, (dict,)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else str(value)


def _emit(records: list[dict[str, Any]], fmt: str, want: list[str]) -> None:
    if fmt == "json":
        json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    if fmt == "jsonl":
        for rec in records:
            sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return
    if fmt in ("tsv", "csv"):
        delimiter = "," if fmt == "csv" else "\t"
        # Stable metadata columns, followed by value keys in requested order.
        metadata = ["entity", "status", "source_row", "outcome"]
        if any("parent" in r for r in records):
            metadata.append("parent")
        metadata += [
            "missing",
            "requires_review",
            "warnings",
            "errors",
            "diagnostics",
            "truncations",
            "completion",
            "candidates",
            "strands",
            "references",
        ]
        value_cols = list(want)
        for rec in records:
            for k in rec["values"]:
                if k not in value_cols:
                    value_cols.append(k)
        cols = metadata + value_cols
        writer = csv.writer(sys.stdout, delimiter=delimiter, lineterminator="\n")
        writer.writerow(cols)
        for rec in records:
            row = [
                json.dumps(rec.get(c, []), ensure_ascii=False)
                if c in metadata[4:] and c != "parent"
                else _cell(rec.get(c))
                for c in metadata
            ]
            row += [_cell(rec["values"].get(c)) for c in value_cols]
            writer.writerow(row)
        return
    # human (default)
    for rec in records:
        head = rec["entity"]
        if "parent" in rec:
            head += f"  (from {rec['parent']})"
        head += "" if rec["status"] == "resolved" else f"  [{rec['status']}]"
        print(head)
        if not rec["values"]:
            print("  (no values)")
        for k, v in rec["values"].items():
            print(f"  {k}: {_cell(v)}")
        print()


def _summary(counts: dict[str, int]) -> None:
    parts = [f"{n} {label}" for label, n in counts.items() if n]
    _err("→ " + (", ".join(parts) if parts else "nothing produced"))


def _report_truncations(result: ExecutionResult) -> None:
    for item in result.truncations:
        _err(
            f"warning: expansion limit {item.limit} at {item.capability_id} for "
            f"{item.entity_id} (source row {item.source_row}): "
            f"kept {item.kept} of {item.requested}, omitted {item.omitted}"
        )


def _report_errors(errors: list[Any]) -> None:
    """Surface structural errors (e.g. an upstream API 500) loudly on stderr, each with
    a plain-English explanation of its category.

    Without this they are invisible: the affected entities never reach stdout, so a run
    that errored otherwise looks like a clean empty result. A ``recovered`` error (the
    weave rerouted around it) is shown as a note, not a failure."""
    if not errors:
        return
    _err(f"\n{len(errors)} error(s):")
    for e in errors:
        where = f" at {e.capability_id}" if e.capability_id else ""
        source = e.capability_id.split(".")[0] if e.capability_id else None
        tag = " (recovered via another route)" if getattr(e, "recovered", False) else ""
        _err(
            f"  ✗ {e.strand_set.entity_id}{where}{tag}: {explain_error(e.category, source=source)}"
        )
        _err(f"      ↳ {e.message}")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def _map_params(
    parsed: list[tuple[str | None, str, str]], caps_by_id: dict[str, Any]
) -> dict[str, dict[str, Any]] | None:
    """Map parsed ``--param`` triples onto the capabilities involved in a route.

    A bare ``NAME=VALUE`` lands on every involved capability that declares ``NAME``;
    ``CAP:NAME=VALUE`` targets one. On an unmatched parameter (likely a typo) the
    error is printed to stderr and ``None`` is returned so the caller exits 1."""
    try:
        return map_parameter_items(parsed, caps_by_id)
    except ValueError as exc:
        _err(f"error: {exc}. See `braidworks weavers` for each capability's parameters.")
        return None


def _input_groups(sets: list[StrandSet]) -> list[list[StrandSet]]:
    """Batch rows together only when they actually have the same input types."""
    grouped: dict[frozenset[str], list[StrandSet]] = {}
    for ss in sets:
        grouped.setdefault(ss.available_types(), []).append(ss)
    return list(grouped.values()) or [[]]


def _absorb_result(result: ExecutionResult, part: ExecutionResult) -> None:
    result.resolved.extend(part.resolved)
    result.unresolved.extend(part.unresolved)
    result.review_queue.extend(part.review_queue)
    result.errors.extend(part.errors)
    result.truncations.extend(part.truncations)
    references = {
        reference.weaver_id: reference for reference in result.references + part.references
    }
    result.references = [references[key] for key in sorted(references)]


def _archive_start(args, sets, registry, plans, caps, params):
    if not args.archive:
        return None
    return begin_archive(
        sets,
        registry,
        options={key: value for key, value in vars(args).items() if key != "func"},
        plans=plans,
        effective_params={
            cid: cap.resolve_params((params or {}).get(cid, {})) for cid, cap in caps.items()
        },
    )


def _archive_finish(args, archive, records, execution):
    if archive is None:
        return True
    try:
        write_archive(args.archive, archive, records=records, execution=execution)
    except (OSError, ValueError, TypeError) as exc:
        _err(f"error: could not write run archive: {exc}")
        return False
    return True


def _persistence_from_args(args):
    return QueryPersistence(
        args.cache_db,
        args.run_db,
        getattr(args, "run_id", None) if args.command == "weave" else None,
        CachePolicy(args.cache_positive_ttl, args.cache_negative_ttl, args.cache_max_bytes),
        args.lease_seconds,
    )


async def _execute_prepared(args, registry, prepared):
    persistence = _persistence_from_args(args)
    announced = False

    def saved(checkpoint):
        nonlocal announced
        if not announced:
            _err(f"durable run: {checkpoint.run_id} (store: {args.run_db})")
            announced = True
        if checkpoint.status in ("complete", "review"):
            _err(f"run status: {checkpoint.status}, revision {checkpoint.revision}")

    return await execute_managed_query(registry, prepared, persistence, on_saved=saved)


def _parse_decisions(values):
    decisions = []
    for value in values or ():
        key, sep, action = value.partition("=")
        if not sep:
            raise ValueError("decision expects ENTITY_KEY=select:INDEX|accept|reject")
        verb, colon, index = action.partition(":")
        if verb == "select" and colon:
            try:
                index = int(index)
            except ValueError as exc:
                raise ValueError("candidate INDEX must be a zero-based integer") from exc
        elif colon:
            raise ValueError("Only select accepts an index")
        else:
            index = None
        decisions.append(ReviewDecision(key, verb, index))
    return tuple(decisions)


def _cmd_runs(args):
    try:
        store = SQLiteRunStore(args.run_db, create=False)
        checkpoints = [store.load(args.run_id)] if args.run_id else store.list()
        statuses = [run_status(cp) for cp in checkpoints]
        if args.format == "json":
            json.dump(
                statuses[0] if args.run_id else statuses, sys.stdout, ensure_ascii=False, indent=2
            )
            print()
        else:
            for status in statuses:
                print(
                    f"{status['run_id']}  {status['status']}  revision={status['revision']}  inputs={status['inputs']}"
                )
                for item in status["reviews"]:
                    ss = item["strand_set"]
                    result = item["triggering_result"]
                    print(
                        f"  review {ss['execution_key']}  entity={ss['entity_id']}  source_row={ss.get('source_row')}  capability={result['capability_id']}"
                    )
                    for index, candidate in enumerate(result["candidates"]):
                        values = {
                            strand["type_id"]: strand["value"] for strand in candidate["strands"]
                        }
                        print(
                            f"    select:{index}  confidence={candidate['confidence']}  {json.dumps(values, ensure_ascii=False)}"
                        )
                    print("    reject" + (" | accept" if result["status"] == "ok" else ""))
        return 0
    except (ValueError, OSError, sqlite3.Error, KeyError) as exc:
        _err(f"error: could not read run store: {exc}")
        return 1


def _cmd_resume(args):
    try:
        store = SQLiteRunStore(args.run_db, create=False)
        original = store.load(args.run_id)
        prepared = original.definition.prepared
        registry = _load_registry(args.only)
        caps = {cid: registry.get_capability(wid, cid) for wid, cid in prepared.capability_ids}
        archive = _archive_start(
            args,
            list(prepared.request.inputs),
            registry,
            [braid.to_json() for braid, _ in prepared.plans],
            caps,
            prepared.effective_params,
        )
        checkpoint = asyncio.run(
            continue_run(
                registry,
                store,
                args.run_id,
                cache=_persistence_from_args(args).cache(),
                decisions=_parse_decisions(args.decision),
                lease_seconds=args.lease_seconds,
            )
        )
        result = checkpoint.state.result
        want = sorted(prepared.request.targets)
        records = _result_records(result, want)
        if not _archive_finish(args, archive, records, result.to_json()):
            return 1
        _emit(records, args.format, want)
        _err(f"run {checkpoint.run_id}: {checkpoint.status}, revision {checkpoint.revision}")
        _report_errors(result.errors)
        _report_truncations(result)
        if args.references:
            _err(format_references(result.references))
        return int(
            bool(
                result.fatal_errors()
                or (
                    args.strict
                    and (result.unresolved or any(row["requires_review"] for row in records))
                )
            )
        )
    except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
        _err(f"error: could not resume run: {exc}")
        return 1


def _cmd_weave(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    backend_policy = BackendPolicy(args.policy)
    want = _split_types(args.want)
    sets = _collect_inputs(args)

    # Traversal fan-out: --for-each <relationship> / --traverse <capability-id>.
    traversal_tokens = list(args.for_each or []) + list(args.traverse or [])
    if traversal_tokens:
        return _weave_traversed(args, registry, want, traversal_tokens, sets)

    if not want:
        raise SystemExit("error: --want TYPE[,TYPE…] is required")
    try:
        prepared = prepare_query(
            registry,
            QueryRequest(
                tuple(sets),
                frozenset(want),
                options=QueryOptions(
                    backend_policy,
                    normalize_expansion(args.expand),
                    ReviewPolicy(args.review_policy),
                    args.confidence_threshold,
                    args.max_expansion,
                ),
                parameter_items=tuple(_parse_params(args.param)),
            ),
        )
    except (NoPathError, NoPlanError) as exc:
        _err(f"no route: {exc}")
        _err("try `braidworks keys` to see what is produced, or `braidworks path --from … --to …`.")
        return 1
    except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
        _err(f"error: {exc}")
        return 1
    plans = [(braid, [sets[i] for i in indices]) for braid, indices in prepared.plans]
    step_caps = {cid: registry.get_capability(wid, cid) for wid, cid in prepared.capability_ids}
    params = prepared.effective_params
    archive = _archive_start(
        args, sets, registry, [b.to_json() for b, _ in plans], step_caps, params
    )
    _err(f"running {sum(len(b.steps) for b, _ in plans)} step(s) over {len(sets)} input(s)…")
    try:
        result = asyncio.run(_execute_prepared(args, registry, prepared))
    except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
        _err(f"error: {exc}")
        return 1

    records = _result_records(result, want)
    if not _archive_finish(args, archive, records, result.to_json()):
        return 1

    _emit(records, args.format, want)
    if args.references:
        refs = format_references(result.references)
        if refs:
            _err("\nSources:\n" + refs)
    _summary(
        {
            "resolved": len(result.resolved),
            "unresolved": len(result.unresolved),
            "review": len(result.review_queue),
            "errors": len(result.errors),
        }
    )
    _report_errors(result.errors)
    _report_truncations(result)
    # A *fatal* structural error (blocked an entity, not rerouted) fails the run; a
    # failure on one branch of an otherwise-resolved entity is reported but not fatal.
    # --strict also fails on unresolved/review.
    if result.fatal_errors():
        return 1
    if args.strict and (result.unresolved or any(row["requires_review"] for row in records)):
        return 1
    return 0


def _weave_traversed(
    args: argparse.Namespace,
    registry: BraidRegistry,
    want: list[str],
    tokens: list[str],
    sets: list[StrandSet],
) -> int:
    """Run a weave that fans *through* one or more relationships (--for-each/--traverse).

    Each token names a fan capability (a relationship noun, or a full capability id);
    we run them in order, re-rooting on every produced value, then plan ``--want`` from
    each child. ``--want`` is optional here — with none you just get the fanned entities.
    """
    backend_policy = BackendPolicy(args.policy)
    try:
        prepared = prepare_query(
            registry,
            QueryRequest(
                tuple(sets),
                frozenset(want),
                tuple(tokens),
                options=QueryOptions(
                    backend_policy,
                    normalize_expansion(args.expand, traversal=True),
                    ReviewPolicy(args.review_policy),
                    args.confidence_threshold,
                    args.max_expansion,
                ),
                parameter_items=tuple(_parse_params(args.param)),
            ),
        )
        caps_by_id = {
            cid: registry.get_capability(wid, cid) for wid, cid in prepared.capability_ids
        }
        archive = _archive_start(
            args,
            sets,
            registry,
            [{"traversals": [list(item) for item in prepared.traversals], "want": want}],
            caps_by_id,
            prepared.effective_params,
        )
        _err(
            f"fanning through {' → '.join(cid for _, cid in prepared.traversals)} over {len(sets)} input(s)…"
        )
        result = asyncio.run(_execute_prepared(args, registry, prepared))
    except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
        _err(f"error: {exc}")
        return 1

    records = _result_records(result, want)
    if not _archive_finish(args, archive, records, result.to_json()):
        return 1

    _emit(records, args.format, want)
    if args.references:
        refs = format_references(result.references)
        if refs:
            _err("\nSources:\n" + refs)
    _summary(
        {
            "resolved": len(result.resolved),
            "unresolved": len(result.unresolved),
            "review": len(result.review_queue),
            "errors": len(result.errors),
        }
    )
    _report_errors(result.errors)
    _report_truncations(result)
    if result.fatal_errors():
        return 1
    if args.strict and (result.unresolved or any(row["requires_review"] for row in records)):
        return 1
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    manifest = registry.get_manifest(args.weaver)
    if manifest is None:
        _err(f"unknown weaver {args.weaver!r}. Try `braidworks weavers`.")
        return 1
    cap = next((c for c in manifest.capabilities if c.id == args.capability), None)
    if cap is None:
        ids = ", ".join(c.id for c in manifest.capabilities)
        _err(f"weaver {args.weaver!r} has no capability {args.capability!r}. Has: {ids}")
        return 1

    backend = args.backend
    if backend is None:
        if len(cap.backends) == 1:
            backend = cap.backends[0]
        else:
            _err(
                f"--backend is required ({args.weaver}.{args.capability} has: "
                f"{', '.join(cap.backends)})"
            )
            return 1

    want = _split_types(args.want) or sorted(cap.produces)
    if backend not in cap.backends:
        _err(
            f"error: backend {backend!r} is not declared for {args.weaver}.{args.capability}. "
            f"Available: {', '.join(cap.backends)}"
        )
        return 1
    # One capability here, so every --param NAME=VALUE applies to it (CAP: prefix optional).
    mapped = _map_params(_parse_params(args.param), {cap.id: cap})
    if mapped is None:
        return 1
    raw_params = mapped.get(cap.id, {})
    try:  # validate/default against the declaration up front for a clean error
        run_params = cap.resolve_params(raw_params)
    except ValueError as exc:
        _err(f"error: {exc}")
        return 1
    sets = _collect_inputs(args)
    weaver = registry.get_weaver(args.weaver)
    archive = _archive_start(
        args,
        sets,
        registry,
        [{"weaver_id": args.weaver, "capability_id": cap.id, "backend": backend, "want": want}],
        {cap.id: cap},
        {cap.id: run_params},
    )
    _err(f"running {args.weaver}.{args.capability} over {len(sets)} input(s)…")
    try:
        results = asyncio.run(
            weaver.execute_batch(
                args.capability,
                sets,
                requested_outputs=frozenset(want),
                backend=backend,
                params=run_params,
            )
        )
        validate_batch_size(len(sets), len(results), context=f"{args.capability} [{backend}]")
    except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
        _err(f"error: {exc}")
        return 1

    records: list[dict[str, Any]] = []
    counts = {"resolved": 0, "unresolved": 0, "review": 0, "errors": 0}
    diagnostics: list[ExecutionError] = []
    for ss, wr in zip(sets, results, strict=True):
        merged = ss.clone()
        merged.merge_result(wr)
        merged.completion.append(
            StepOutcome(
                cap.id, backend, wr.status.value, tuple(strand.type_id for strand in wr.strands)
            )
        )
        if wr.status is WeaveStatus.ERROR:
            status = "error"
            for message in wr.errors or ("backend returned ERROR without a diagnostic",):
                diagnostics.append(
                    ExecutionError(
                        strand_set=merged,
                        error_type="WeaverError",
                        message=message,
                        capability_id=cap.id,
                        category=classify_error(message),
                    )
                )
        elif wr.status is WeaveStatus.AMBIGUOUS or wr.requires_review:
            status = "review"
        elif wr.status is WeaveStatus.NO_MATCH:
            status = "unresolved"
        else:
            status = "resolved"
        counts["errors" if status == "error" else status] += 1
        record = _record(ss.entity_id, status, merged, want)
        if wr.errors:
            record["errors"] = list(wr.errors)
        if wr.candidates:
            record["candidates"] = [candidate.to_json() for candidate in wr.candidates]
            _err(f"{ss.entity_id}: {len(wr.candidates)} candidate(s) require review")
        record["diagnostics"] = [
            {key: value for key, value in error.to_json().items() if key != "strand_set"}
            for error in diagnostics
            if error.strand_set is merged
        ]
        record["references"] = [ref.to_json() for ref in references_for([args.weaver], registry)]
        records.append(record)
    records = _number_records(records)
    if not _archive_finish(
        args, archive, records, {"direct_results": [item.to_json() for item in results]}
    ):
        return 1
    _emit(records, args.format, want)
    _summary(counts)
    _report_errors(diagnostics)
    if counts["errors"] or (args.strict and (counts["unresolved"] or counts["review"])):
        return 1
    return 0


def _cmd_weavers(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    manifests = sorted(registry.manifests(), key=lambda m: m.weaver_id)
    if args.format == "json":
        out = [
            {
                "weaver": m.weaver_id,
                "version": m.version,
                "title": m.title,
                "capabilities": [
                    {
                        "id": c.id,
                        "consumes": sorted(c.consumes),
                        "produces": sorted(c.produces),
                        "set_outputs": sorted(c.set_outputs),
                        "backends": list(c.backends),
                        "parameters": [p.to_json() for p in c.parameters],
                    }
                    for c in m.capabilities
                ],
            }
            for m in manifests
        ]
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    for m in manifests:
        print(f"{m.weaver_id}  v{m.version}  — {m.title}")
        for c in m.capabilities:
            consumes = ", ".join(sorted(c.consumes)) or "(none)"
            produces = ", ".join(sorted(c.produces))
            fan = "  ⤜ fan: " + ", ".join(sorted(c.set_outputs)) if c.set_outputs else ""
            print(f"    {c.id}: {consumes}  →  {produces}{fan}")
            for p in c.parameters:
                bits = [p.type]
                if p.enum:
                    bits.append("∈ {" + ", ".join(str(e) for e in p.enum) + "}")
                if p.default is not None:
                    bits.append(f"default={p.default}")
                desc = f" — {p.description}" if p.description else ""
                print(f"        --param {p.name} ({', '.join(bits)}){desc}")
        print()
    return 0


def _cmd_keys(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    producers: dict[str, list[str]] = {}
    consumers: dict[str, list[str]] = {}
    for m in registry.manifests():
        for c in m.capabilities:
            label = f"{m.weaver_id}.{c.id}"
            for t in c.produces:
                producers.setdefault(t, []).append(label)
            for t in c.consumes:
                consumers.setdefault(t, []).append(label)

    keys = sorted(set(producers) | set(consumers))
    if args.produces:
        keys = [k for k in keys if k == args.produces]
    if args.consumes:
        keys = [k for k in keys if k == args.consumes]

    if args.format == "json":
        out = {
            k: {
                "produced_by": sorted(producers.get(k, [])),
                "consumed_by": sorted(consumers.get(k, [])),
            }
            for k in keys
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    for k in keys:
        prod = ", ".join(sorted(producers.get(k, []))) or "—"
        cons = ", ".join(sorted(consumers.get(k, []))) or "—"
        print(f"{k}\n    produced by: {prod}\n    consumed by: {cons}")
    return 0


def _cmd_path(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    frm, to = _split_types(args.frm), _split_types(args.to)
    if not frm or not to:
        raise SystemExit("error: --from and --to are both required")
    try:
        braid = Braider(registry).plan(
            available_types=frozenset(frm),
            target_types=frozenset(to),
            backend_policy=BackendPolicy(args.policy),
        )
    except (NoPathError, NoPlanError) as exc:
        _err(f"no route from {frm} to {to}: {exc}")
        return 1
    print(f"{', '.join(frm)}  →  {', '.join(to)}   ({len(braid.steps)} step(s))")
    for i, step in enumerate(braid.steps, start=1):
        ins = ", ".join(sorted(step.input_types))
        outs = ", ".join(sorted(step.output_types))
        print(
            f"  {i}. {step.weaver_id}.{step.capability_id} [{step.primary_backend}]: {ins} → {outs}"
        )
    return 0


def _cmd_references(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    refs = references_for([m.weaver_id for m in registry.manifests()], registry)
    if args.format == "json":
        json.dump([r.to_json() for r in refs], sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    print(format_references(refs) or "(no citations)")
    return 0


# --------------------------------------------------------------------------- #
# argument parser
# --------------------------------------------------------------------------- #
def _add_input_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--have",
        action="append",
        metavar="TYPE=VALUE",
        help="an input strand; repeatable. Broadcast onto every --in-file row.",
    )
    p.add_argument(
        "--in-file",
        metavar="PATH",
        help="batch input: a CSV/TSV with type-id columns, or (with --in-type) "
        "one value per line. Use '-' for stdin.",
    )
    p.add_argument(
        "--in-type",
        metavar="TYPE",
        help="treat --in-file as one VALUE per line of this strand type.",
    )


def _add_output_flags(p: argparse.ArgumentParser, *, strict: bool = True) -> None:
    p.add_argument(
        "--format",
        choices=["human", "json", "jsonl", "tsv", "csv"],
        default="human",
        help="output format (default: human).",
    )
    p.add_argument(
        "--only", metavar="WEAVERS", help="restrict to these weaver ids (comma/space separated)."
    )
    if strict:
        p.add_argument(
            "--archive",
            metavar="PATH",
            help="save a self-contained JSON run archive (new file; no overwrite).",
        )
        p.add_argument(
            "--strict",
            action="store_true",
            help="exit non-zero if any input is unresolved or needs review.",
        )


def _add_persistence_flags(parser, *, start=False):
    parser.add_argument("--cache-db", metavar="PATH", help="opt-in local SQLite lookup cache")
    parser.add_argument(
        "--cache-positive-ttl",
        type=float,
        default=3600,
        help="positive/ambiguous lifetime in seconds; 0 disables admission",
    )
    parser.add_argument(
        "--cache-negative-ttl",
        type=float,
        default=300,
        help="no-match lifetime in seconds; 0 disables admission",
    )
    parser.add_argument(
        "--cache-max-bytes",
        type=int,
        default=256 * 1024 * 1024,
        help="cache payload budget; physical SQLite size may differ",
    )
    parser.add_argument(
        "--run-db", metavar="PATH", required=not start, help="opt-in local durable run store"
    )
    parser.add_argument(
        "--lease-seconds",
        type=float,
        default=60,
        help="run owner lease, renewed while executing (default: 60 seconds)",
    )
    if start:
        parser.add_argument("--run-id", help="new run identity; existing IDs are never overwritten")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="braidworks",
        description="Query and inspect the Braidworks weaver network from the shell.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # weave
    w = sub.add_parser("weave", help="plan a route from --have to --want and run it.")
    _add_input_flags(w)
    w.add_argument("--want", metavar="TYPE[,TYPE…]", help="target strand types.")
    w.add_argument(
        "--for-each",
        action="append",
        metavar="RELATIONSHIP",
        dest="for_each",
        help="fan the weave THROUGH a relationship, then plan --want from each "
        "result (e.g. --for-each orthologs). Repeatable; implies --expand all.",
    )
    w.add_argument(
        "--traverse",
        action="append",
        metavar="CAPABILITY",
        help="like --for-each but names a fan capability id directly "
        "(e.g. --traverse ncbi.list_orthologs); the unambiguous form.",
    )
    w.add_argument(
        "--expand",
        default=None,
        metavar="none|all|top:K",
        help="fan out one→many set outputs (default: none, or all when "
        "--for-each/--traverse is used).",
    )
    w.add_argument(
        "--max-expansion",
        type=int,
        default=10_000,
        metavar="N",
        help="run-wide leaf limit (default: 10000); preserves all input roots "
        "and reports omitted successors.",
    )
    w.add_argument(
        "--policy",
        choices=[policy.value for policy in BackendPolicy],
        default="local_first",
        help="backend policy (default: local_first).",
    )
    w.add_argument(
        "--review-policy",
        choices=[policy.value for policy in ReviewPolicy],
        default="halt",
        help="ambiguity/review policy (default: halt); "
        "allow_continue explicitly permits candidate selection.",
    )
    w.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.0,
        metavar="0..1",
        help="minimum confidence; lower results pause even with allow_continue.",
    )
    w.add_argument(
        "--param",
        action="append",
        metavar="NAME=VALUE",
        help="a capability parameter (repeatable); CAP:NAME=VALUE targets one "
        "step. See `braidworks weavers` for each capability's parameters.",
    )
    w.add_argument(
        "--references", action="store_true", help="print source citations for the route to stderr."
    )
    _add_output_flags(w)
    _add_persistence_flags(w, start=True)
    w.set_defaults(func=_cmd_weave)

    runs = sub.add_parser("runs", help="list saved runs or inspect a run's status/review choices")
    runs.add_argument("run_id", nargs="?")
    runs.add_argument("--run-db", required=True, metavar="PATH")
    runs.add_argument("--format", choices=["human", "json"], default="human")
    runs.set_defaults(func=_cmd_runs)
    resume = sub.add_parser("resume", help="continue a saved run with its original query settings")
    resume.add_argument("run_id")
    resume.add_argument(
        "--decision",
        action="append",
        metavar="ENTITY_KEY=select:INDEX|accept|reject",
        help="explicit saved review decision; select INDEX is zero-based; repeatable",
    )
    resume.add_argument("--references", action="store_true")
    _add_output_flags(resume)
    _add_persistence_flags(resume)
    resume.set_defaults(func=_cmd_resume)

    # run
    r = sub.add_parser("run", help="call ONE weaver capability directly (no routing).")
    r.add_argument("weaver", help="weaver id (see `braidworks weavers`).")
    r.add_argument("capability", help="capability id.")
    r.add_argument(
        "--want",
        metavar="TYPE[,TYPE…]",
        help="restrict outputs (default: all the capability produces).",
    )
    r.add_argument("--backend", help="backend name (required only if the capability has >1).")
    r.add_argument(
        "--param",
        action="append",
        metavar="NAME=VALUE",
        help="a capability parameter (repeatable).",
    )
    _add_input_flags(r)
    _add_output_flags(r)
    r.set_defaults(func=_cmd_run)

    # weavers
    lw = sub.add_parser("weavers", help="list installed weavers and their capabilities.")
    lw.add_argument("--format", choices=["human", "json"], default="human")
    lw.add_argument("--only", metavar="WEAVERS")
    lw.set_defaults(func=_cmd_weavers)

    # keys
    k = sub.add_parser("keys", help="list strand types and who produces / consumes them.")
    k.add_argument("--produces", metavar="TYPE", help="only show this produced type.")
    k.add_argument("--consumes", metavar="TYPE", help="only show this consumed type.")
    k.add_argument("--format", choices=["human", "json"], default="human")
    k.add_argument("--only", metavar="WEAVERS")
    k.set_defaults(func=_cmd_keys)

    # path
    pa = sub.add_parser("path", help="show the route between types without running it.")
    pa.add_argument("--from", dest="frm", metavar="TYPE[,TYPE…]", required=True)
    pa.add_argument("--to", metavar="TYPE[,TYPE…]", required=True)
    pa.add_argument("--only", metavar="WEAVERS")
    pa.add_argument(
        "--policy",
        choices=[policy.value for policy in BackendPolicy],
        default="local_first",
        help="backend policy (default: local_first).",
    )
    pa.set_defaults(func=_cmd_path)

    # references
    rf = sub.add_parser("references", help="print source citations for installed weavers.")
    rf.add_argument("--format", choices=["human", "json"], default="human")
    rf.add_argument("--only", metavar="WEAVERS")
    rf.set_defaults(func=_cmd_references)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
