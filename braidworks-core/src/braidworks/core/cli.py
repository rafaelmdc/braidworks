"""The ``braidworks`` command-line interface — query and inspect the weaver network.

Designed for the bash-native researcher: build a strand and get results without
writing Python. Inputs come from flags, a file (one value per line, or a CSV/TSV
with type-id columns), or stdin; results print as a human table by default or as
``--json`` / ``--jsonl`` / ``--tsv`` / ``--csv`` for piping into ``jq`` / pandas.
Progress and counts go to **stderr** so stdout stays clean, pipeable data.

Subcommands
  get     look up what you WANT for IDs you HAVE, routing across all weavers
          (``braidworks get P04637 --have protein.query --want protein.name``);
          ``weave`` is an alias
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
from braidworks.core.diagnose import (
    INSTALL_ALL,
    backend_readiness,
    explain_no_route,
    workspace_weavers,
)
from braidworks.core.discovery import (
    DiscoveryPolicy,
    build_registry_from_entry_points,
    discover_registry,
)
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
from braidworks.core.persistence_options import QueryPersistence
from braidworks.core.planner import Braider
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
        _err("no sources installed: Braidworks has nothing to query yet.")
        _err(f"  From the checkout, install every source with: {INSTALL_ALL}")
        _err("  Then check the installation with: braidworks doctor")
        raise SystemExit(1)
    return registry


def _report_no_route(
    registry: BraidRegistry, have: Sequence[str], want: Sequence[str], exc: Exception
) -> None:
    """Explain a failed plan in the user's terms, with the next thing to try."""
    if isinstance(exc, NoPlanError):
        _err(f"no route: {exc}")
        return
    _err(f"no route from {', '.join(sorted(set(have)))} to {', '.join(want)}.")
    for line in explain_no_route(registry, have, want):
        _err(line)


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


def _have_items(args: argparse.Namespace) -> tuple[dict[str, str], str | None]:
    """Split ``--have`` into ``TYPE=VALUE`` constants and the bare TYPE of the ID arguments.

    Commands without ID arguments (``run``) accept only ``TYPE=VALUE``.
    """
    takes_ids = hasattr(args, "ids")
    constants: dict[str, str] = {}
    id_types: list[str] = []
    for item in args.have or []:
        if takes_ids and "=" not in item and item.strip():
            id_types.append(item.strip())
        else:
            key, value = _parse_kv(item)
            constants[key] = value
    ids = list(getattr(args, "ids", None) or [])
    if len(id_types) > 1:
        raise SystemExit(
            f"error: --have names one type for the ID arguments, got {', '.join(id_types)}. "
            "Give other inputs as --have TYPE=VALUE."
        )
    id_type = id_types[0] if id_types else None
    if ids and id_type is None:
        raise SystemExit(
            f"error: say what {ids[0]!r} is with --have TYPE (e.g. --have protein.query). "
            "Run `braidworks keys` for the types you can start from."
        )
    if id_type is not None and not ids:
        raise SystemExit(
            f"error: --have {id_type} types the ID arguments, but no IDs were given. "
            f"Pass IDs (braidworks get ID… --have {id_type}) or --have {id_type}=VALUE."
        )
    if ids and args.in_file:
        raise SystemExit("error: give IDs as arguments or --in-file, not both")
    return constants, id_type


def _collect_inputs(args: argparse.Namespace) -> list[StrandSet]:
    """Build the StrandSets to run from ID arguments, ``--have`` constants and/or a file.

    ``get ID… --have TYPE`` makes one entity per ID, named by the ID. ``--have
    TYPE=VAL`` (repeatable) are *constants* broadcast onto every entity; a ``--in-file``
    (or stdin via ``-``) supplies the per-entity strands. With neither IDs nor a file,
    the constants alone form a single entity.
    """
    constants, id_type = _have_items(args)
    sets: list[StrandSet] = []

    if id_type is not None:
        for value in args.ids:
            merged = {**constants, id_type: value}
            sets.append(StrandSet.from_strands(value, [Strand(t, v) for t, v in merged.items()]))
    elif args.in_file:
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
            raise SystemExit(
                "error: nothing to run — pass IDs with --have TYPE, "
                "--have TYPE=VALUE or --in-file PATH"
            )
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
        getattr(args, "run_id", None) if args.command in ("get", "weave") else None,
        CachePolicy(args.cache_positive_ttl, args.cache_negative_ttl, args.cache_max_bytes),
        args.lease_seconds,
    )


def _session(args, registry: BraidRegistry):
    """The same Session the Python API uses, over the CLI's (patchable) registry."""
    from braidworks._session import Session

    # `resume` has no --policy: a saved run replays the policy it was prepared with.
    return Session(registry=registry, backend=getattr(args, "policy", "local_first"))


def _saved_announcer(args):
    announced = False

    def saved(checkpoint):
        nonlocal announced
        if not announced:
            _err(f"durable run: {checkpoint.run_id} (store: {args.run_db})")
            announced = True
        if checkpoint.status in ("complete", "review"):
            _err(f"run status: {checkpoint.status}, revision {checkpoint.revision}")

    return saved


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
        prepared = store.load(args.run_id).definition.prepared
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
        with _session(args, registry) as session:
            checkpoint, outcome = session._runner().run(
                session._resume_run(
                    args.run_id,
                    _persistence_from_args(args),
                    decisions=_parse_decisions(args.decision),
                )
            )
        result = outcome.raw
        want = outcome.want
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
    want = _split_types(args.want)
    sets = _collect_inputs(args)
    # Traversal fan-out: --for-each <relationship> / --traverse <capability-id>.
    # With a traversal --want is optional — you just get the fanned entities.
    traversals = list(args.for_each or []) + list(args.traverse or [])
    if not traversals and not want:
        raise SystemExit("error: --want TYPE[,TYPE…] is required")
    with _session(args, registry) as session:
        try:
            prepared = session._prepare_sets(
                sets,
                want,
                traversals,
                expand=args.expand,
                review=args.review_policy,
                min_confidence=args.confidence_threshold,
                max_expansion=args.max_expansion,
                parameter_items=tuple(_parse_params(args.param)),
            )
        except (NoPathError, NoPlanError) as exc:
            if traversals:
                _err(f"error: {exc}")
                return 1
            have = sorted({t for ss in sets for t in ss.available_types()})
            _report_no_route(registry, have, want, exc)
            return 1
        except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
            _err(f"error: {exc}")
            return 1
        try:
            caps = {cid: registry.get_capability(wid, cid) for wid, cid in prepared.capability_ids}
            if traversals:
                plans = [{"traversals": [list(item) for item in prepared.traversals], "want": want}]
                route = " → ".join(cid for _, cid in prepared.traversals)
                progress = f"fanning through {route} over {len(sets)} input(s)…"
            else:
                plans = [braid.to_json() for braid, _ in prepared.plans]
                steps = sum(len(braid.steps) for braid, _ in prepared.plans)
                progress = f"running {steps} step(s) over {len(sets)} input(s)…"
            archive = _archive_start(args, sets, registry, plans, caps, prepared.effective_params)
            _err(progress)
            outcome = session._runner().run(
                session._execute(
                    prepared,
                    want,
                    persistence=_persistence_from_args(args),
                    on_saved=_saved_announcer(args),
                )
            )
        except (ValueError, BraidworksError, OSError, sqlite3.Error) as exc:
            _err(f"error: {exc}")
            return 1

    result = outcome.raw
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


def _cmd_run(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    manifest = registry.get_manifest(args.weaver)
    if manifest is None:
        _err(f"unknown weaver {args.weaver!r}. Try `braidworks weavers`.")
        return 1
    from braidworks.core.availability import require_capability
    from braidworks.core.exceptions import BackendUnavailable, UnsupportedCapability

    try:
        cap = require_capability(registry.get_weaver(args.weaver), args.capability)
    except (BackendUnavailable, UnsupportedCapability) as exc:
        _err(str(exc))
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
        _report_no_route(registry, frm, to, exc)
        return 1
    print(f"{', '.join(frm)}  →  {', '.join(to)}   ({len(braid.steps)} step(s))")
    for i, step in enumerate(braid.steps, start=1):
        ins = ", ".join(sorted(step.input_types))
        outs = ", ".join(sorted(step.output_types))
        print(
            f"  {i}. {step.weaver_id}.{step.capability_id} [{step.primary_backend}]: {ins} → {outs}"
        )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Check the installation and say, in plain words, what to do next."""
    import platform
    from importlib.metadata import PackageNotFoundError, version

    try:
        core_version = version("braidworks-core")
    except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
        core_version = "unknown"
    report = discover_registry(policy=DiscoveryPolicy.TOLERANT)
    registry = report.registry
    manifests = sorted(registry.declared_manifests(), key=lambda m: m.weaver_id)
    print(f"Braidworks core {core_version} · Python {platform.python_version()} · {sys.prefix}")
    print()

    problems = len(report.failures)
    print(f"{len(manifests)} source(s) installed")
    width = max(
        [len(m.weaver_id) for m in manifests] + [len(f.name) for f in report.failures] + [1]
    )
    for manifest in manifests:
        enabled, not_set_up = backend_readiness(registry, manifest.weaver_id)
        label = f"  {{mark}} {manifest.weaver_id:<{width}}  v{manifest.version:<8} "
        if not not_set_up:
            print(label.format(mark="✓") + f"ready ({', '.join(enabled)})")
        elif enabled:
            print(
                label.format(mark="!")
                + f"ready via {', '.join(enabled)}; not set up: {', '.join(not_set_up)}"
                + " (see the source's README)"
            )
        else:
            print(
                label.format(mark="○")
                + f"needs setup: {', '.join(not_set_up)} (see the source's README)"
            )
    for failure in report.failures:
        print(
            f"  ✗ {failure.name:<{width}}  failed to {failure.stage}: "
            f"{failure.exception_type}: {failure.message}"
        )

    installed = {m.weaver_id for m in manifests} | {f.name for f in report.failures}
    absent = [w for w in workspace_weavers() if w.weaver_id not in installed]
    if absent:
        print()
        print(f"Not installed from this checkout: {', '.join(w.weaver_id for w in absent)}")
        print(f"  Install every source with: {INSTALL_ALL}")

    print()
    if not manifests:
        print("Nothing to query yet. From the checkout, run: " + INSTALL_ALL)
        return 1
    print("Next:")
    print("  braidworks keys                              what you can start from and ask for")
    print("  braidworks path --from TYPE --to TYPE        preview a route without fetching")
    print("  braidworks get ID --have TYPE --want TYPE")
    return 1 if problems else 0


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
def _add_input_flags(p, *, ids: bool = False) -> None:
    """Input flags on ``p`` (a parser or an argument group)."""
    if ids:
        p.add_argument(
            "ids",
            nargs="*",
            metavar="ID",
            help="values to look up, all of the type named by a bare --have TYPE.",
        )
    p.add_argument(
        "--have",
        action="append",
        metavar="TYPE[=VALUE]" if ids else "TYPE=VALUE",
        help=(
            "TYPE of the ID arguments, or a TYPE=VALUE input strand (repeatable; "
            "broadcast onto every ID or --in-file row)."
            if ids
            else "an input strand; repeatable. Broadcast onto every --in-file row."
        ),
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


def _add_format_flag(p) -> None:
    p.add_argument(
        "--format",
        choices=["human", "json", "jsonl", "tsv", "csv"],
        default="human",
        help="output format (default: human).",
    )


def _add_only_flag(p) -> None:
    p.add_argument(
        "--only", metavar="SOURCES", help="restrict to these source ids (comma/space separated)."
    )


def _add_strict_flag(p) -> None:
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any input is unresolved or needs review.",
    )


def _add_archive_flag(p) -> None:
    p.add_argument(
        "--archive",
        metavar="PATH",
        help="save a self-contained JSON run archive (new file; no overwrite).",
    )


def _add_persistence_flags(p, *, start: bool = False) -> None:
    """Cache and saved-run flags on ``p`` (a parser or an argument group).

    ``start`` adds the flags that create a saved run (``--run-db``/``--run-id``).
    """
    p.add_argument("--cache-db", metavar="PATH", help="opt-in local SQLite lookup cache.")
    p.add_argument(
        "--cache-positive-ttl",
        type=float,
        default=3600,
        metavar="SECONDS",
        help="lifetime of found/ambiguous cache entries (default: 3600); 0 disables caching them.",
    )
    p.add_argument(
        "--cache-negative-ttl",
        type=float,
        default=300,
        metavar="SECONDS",
        help="lifetime of no-match cache entries (default: 300); 0 disables caching them.",
    )
    p.add_argument(
        "--cache-max-bytes",
        type=int,
        default=256 * 1024 * 1024,
        metavar="BYTES",
        help="cache payload budget (default: 256 MiB); the SQLite file size may differ.",
    )
    if start:  # resuming commands take --run-db as a required, first-screen flag
        p.add_argument(
            "--run-db",
            metavar="PATH",
            help="opt-in local saved-run store (makes this a resumable run).",
        )
        p.add_argument(
            "--run-id",
            metavar="ID",
            help="name for the new saved run; existing IDs are never overwritten.",
        )
    p.add_argument(
        "--lease-seconds",
        type=float,
        default=60,
        metavar="SECONDS",
        help="run owner lease, renewed while executing (default: 60).",
    )


def _examples(*lines: str) -> str:
    return "examples:\n" + "\n".join(f"  {line}" for line in lines)


def _subparser(sub, name: str, *, help: str, examples: tuple[str, ...] = (), **kwargs):
    return sub.add_parser(
        name,
        help=help,
        description=kwargs.pop("description", help[:1].upper() + help[1:]),
        epilog=_examples(*examples) if examples else None,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="braidworks",
        description="Query and inspect the Braidworks weaver network from the shell.",
        epilog=_examples(
            "braidworks doctor                     check the installation",
            "braidworks keys                       what you can start from and ask for",
            "braidworks get P04637 --have protein.query --want protein.name",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # get (alias: weave)
    w = _subparser(
        sub,
        "get",
        aliases=["weave"],
        help="look up --want for IDs (or --have TYPE=VALUE / --in-file), routing across sources.",
        description="Look up the --want types for each input, planning a route across "
        "the installed sources.",
        usage="braidworks get ID… --have TYPE --want TYPE[,TYPE…] [options]",
        examples=(
            "braidworks get P04637 --have protein.query --want protein.name",
            "braidworks get P04637 TP53 --have protein.query --param organism=9606 \\",
            "    --want protein.name,structure.pdb.ids --format tsv",
            "braidworks get --in-file ids.txt --in-type protein.query --want protein.name",
            "braidworks get --have gene.ncbi.id=7157 --for-each orthologs --want gene.symbol",
        ),
    )
    inputs = w.add_argument_group("inputs")
    _add_input_flags(inputs, ids=True)
    retrieve = w.add_argument_group("what to retrieve")
    retrieve.add_argument("--want", metavar="TYPE[,TYPE…]", help="target strand types.")
    retrieve.add_argument(
        "--for-each",
        action="append",
        metavar="RELATIONSHIP",
        dest="for_each",
        help="fan the lookup THROUGH a relationship, then get --want for each "
        "result (e.g. --for-each orthologs). Repeatable; implies --expand all.",
    )
    retrieve.add_argument(
        "--traverse",
        action="append",
        metavar="CAPABILITY",
        help="like --for-each but names a fan capability id directly "
        "(e.g. --traverse ncbi.list_orthologs); the unambiguous form.",
    )
    retrieve.add_argument(
        "--param",
        action="append",
        metavar="NAME=VALUE",
        help="a capability parameter (repeatable); CAP:NAME=VALUE targets one "
        "step. See `braidworks weavers` for each capability's parameters.",
    )
    output = w.add_argument_group("output")
    _add_format_flag(output)
    output.add_argument(
        "--references", action="store_true", help="print source citations for the route to stderr."
    )
    routing = w.add_argument_group("Advanced: sources and routing")
    _add_only_flag(routing)
    routing.add_argument(
        "--policy",
        choices=[policy.value for policy in BackendPolicy],
        default="local_first",
        help="backend policy (default: local_first).",
    )
    routing.add_argument(
        "--expand",
        default=None,
        metavar="none|all|top:K",
        help="fan out one→many set outputs (default: none, or all when "
        "--for-each/--traverse is used).",
    )
    routing.add_argument(
        "--max-expansion",
        type=int,
        default=10_000,
        metavar="N",
        help="run-wide leaf limit (default: 10000); preserves all input roots "
        "and reports omitted successors.",
    )
    review = w.add_argument_group("Advanced: review and exit status")
    review.add_argument(
        "--review-policy",
        choices=[policy.value for policy in ReviewPolicy],
        default="halt",
        help="ambiguity/review policy (default: halt); "
        "allow_continue explicitly permits candidate selection.",
    )
    review.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.0,
        metavar="0..1",
        help="minimum confidence; lower results pause even with allow_continue.",
    )
    _add_strict_flag(review)
    saved = w.add_argument_group("Advanced: cache, saved runs and archives")
    _add_persistence_flags(saved, start=True)
    _add_archive_flag(saved)
    w.set_defaults(func=_cmd_weave)

    runs = _subparser(
        sub,
        "runs",
        help="list saved runs or inspect a run's status/review choices.",
        examples=(
            "braidworks runs --run-db runs.sqlite",
            "braidworks runs p53 --run-db runs.sqlite --format json",
        ),
    )
    runs.add_argument("run_id", nargs="?", help="show one run (default: list every run).")
    runs.add_argument("--run-db", required=True, metavar="PATH", help="the saved-run store.")
    runs.add_argument("--format", choices=["human", "json"], default="human")
    runs.set_defaults(func=_cmd_runs)

    resume = _subparser(
        sub,
        "resume",
        help="continue a saved run with its original query settings.",
        usage="braidworks resume RUN_ID --run-db PATH [options]",
        examples=(
            "braidworks resume p53 --run-db runs.sqlite",
            "braidworks resume p53 --run-db runs.sqlite --decision KEY=select:0",
        ),
    )
    resume.add_argument("run_id", help="the saved run to continue (see `braidworks runs`).")
    resume.add_argument("--run-db", required=True, metavar="PATH", help="the saved-run store.")
    resume.add_argument(
        "--decision",
        action="append",
        metavar="ENTITY_KEY=select:INDEX|accept|reject",
        help="explicit saved review decision; select INDEX is zero-based; repeatable.",
    )
    _add_format_flag(resume)
    resume.add_argument(
        "--references", action="store_true", help="print source citations to stderr."
    )
    resume_advanced = resume.add_argument_group("Advanced: sources, cache and archives")
    _add_only_flag(resume_advanced)
    _add_strict_flag(resume_advanced)
    _add_persistence_flags(resume_advanced)
    _add_archive_flag(resume_advanced)
    resume.set_defaults(func=_cmd_resume)

    # run
    r = _subparser(
        sub,
        "run",
        help="call ONE weaver capability directly (no routing).",
        usage="braidworks run WEAVER CAPABILITY --have TYPE=VALUE [options]",
        examples=(
            "braidworks run uniprot resolve_protein --have protein.query=P04637",
            "braidworks run pdbe list_structures --have protein.uniprot.accession=P04637 \\",
            "    --format json",
        ),
    )
    r.add_argument("weaver", help="weaver id (see `braidworks weavers`).")
    r.add_argument("capability", help="capability id.")
    _add_input_flags(r)
    r.add_argument(
        "--want",
        metavar="TYPE[,TYPE…]",
        help="restrict outputs (default: all the capability produces).",
    )
    r.add_argument(
        "--param",
        action="append",
        metavar="NAME=VALUE",
        help="a capability parameter (repeatable).",
    )
    _add_format_flag(r)
    run_advanced = r.add_argument_group("Advanced")
    run_advanced.add_argument(
        "--backend", help="backend name (required only if the capability has >1)."
    )
    _add_only_flag(run_advanced)
    _add_strict_flag(run_advanced)
    _add_archive_flag(run_advanced)
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
    pa = _subparser(
        sub,
        "path",
        help="show the route between types without running it.",
        examples=("braidworks path --from protein.query --to structure.pdb.ids",),
    )
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

    # doctor
    dr = sub.add_parser("doctor", help="check the installation and suggest fixes.")
    dr.set_defaults(func=_cmd_doctor)

    # references
    rf = sub.add_parser("references", help="print source citations for installed weavers.")
    rf.add_argument("--format", choices=["human", "json"], default="human")
    rf.add_argument("--only", metavar="WEAVERS")
    rf.set_defaults(func=_cmd_references)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    # argparse cannot interleave a subcommand's positionals with its options, so IDs
    # written after a flag (`get P1 --want x P2`) arrive as leftovers; keep those.
    args, extra = parser.parse_known_args(argv)
    if extra and (not hasattr(args, "ids") or any(item.startswith("-") for item in extra)):
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if extra:
        args.ids = [*args.ids, *extra]
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
