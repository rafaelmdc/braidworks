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
import sys
from typing import Any, Sequence

from braidworks.core.discovery import build_registry_from_entry_points
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.executor import ExpandPolicy, LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.references import (
    format_references,
    references_for,
    references_for_braid,
)
from braidworks.core.registry import BraidRegistry
from braidworks.core.strand import Strand, StrandSet


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
        if in_type:
            rows = []
            for line in handle:
                value = line.strip()
                if not value or value.startswith("#"):
                    continue
                rows.append({in_type: value})
            return rows
        delimiter = "," if path.endswith(".csv") else "\t"
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise SystemExit(f"error: {path} has no header row of type-ids")
        rows = []
        for raw in reader:
            row = {
                (k or "").strip(): (v or "").strip()
                for k, v in raw.items()
                if k and v and v.strip()
            }
            if row:
                rows.append(row)
        return rows
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
            sets.append(
                StrandSet.from_strands(ident, [Strand(t, v) for t, v in merged.items()])
            )
    else:
        if not constants:
            raise SystemExit(
                "error: nothing to run — pass --have TYPE=VALUE or --in-file PATH"
            )
        sets.append(
            StrandSet.from_strands("e1", [Strand(t, v) for t, v in constants.items()])
        )
    return sets


# --------------------------------------------------------------------------- #
# output: one record per entity, rendered per --format
# --------------------------------------------------------------------------- #
def _record(entity_id: str, status: str, ss: StrandSet, want: list[str]) -> dict[str, Any]:
    # If --want is empty (e.g. `run` with no filter), show everything produced.
    types = want or sorted(ss.available_types())
    values = {t: ss.get(t).value for t in types if ss.get(t) is not None}
    rec: dict[str, Any] = {"entity": entity_id, "status": status, "values": values}
    if ss.parent_id is not None:
        rec["parent"] = ss.parent_id
    return rec


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
        # Stable column set: entity, [parent], then the union of value keys (want order first).
        cols = ["entity"]
        if any("parent" in r for r in records):
            cols.append("parent")
        value_cols = list(want)
        for rec in records:
            for k in rec["values"]:
                if k not in value_cols:
                    value_cols.append(k)
        cols += value_cols
        writer = csv.writer(sys.stdout, delimiter=delimiter, lineterminator="\n")
        writer.writerow(cols)
        for rec in records:
            row = [rec["entity"]] + (
                [rec.get("parent", "")] if "parent" in cols else []
            )
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


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def _cmd_weave(args: argparse.Namespace) -> int:
    registry = _load_registry(args.only)
    want = _split_types(args.want)
    if not want:
        raise SystemExit("error: --want TYPE[,TYPE…] is required")
    have_types = frozenset(
        [k for k, _ in (_parse_kv(i) for i in (args.have or []))]
        + ([args.in_type] if args.in_type else [])
    )
    if not have_types:
        # CSV/TSV header supplies the types; peek so planning has them.
        sets_preview = _collect_inputs(args)
        have_types = frozenset().union(*(s.available_types() for s in sets_preview))

    try:
        braid = Braider(registry).plan(
            available_types=have_types, target_types=frozenset(want)
        )
    except (NoPathError, NoPlanError) as exc:
        _err(f"no route: {exc}")
        _err("try `braidworks keys` to see what's produced, or `braidworks path --from … --to …`.")
        return 1

    sets = _collect_inputs(args)
    _err(f"running {len(braid.steps)} step(s) over {len(sets)} input(s)…")
    result = asyncio.run(
        LocalExecutor(registry).execute(
            braid, sets, expand_policy=_expand_policy(args.expand)
        )
    )

    records: list[dict[str, Any]] = []
    for ss in result.resolved:
        records.append(_record(ss.entity_id, "resolved", ss, want))
    for ss, _wr in result.unresolved:
        records.append(_record(ss.entity_id, "unresolved", ss, want))
    for item in result.review_queue:
        records.append(_record(item.strand_set.entity_id, "review", item.strand_set, want))

    _emit(records, args.format, want)
    if args.references:
        refs = format_references(references_for_braid(braid, registry))
        if refs:
            _err("\nSources:\n" + refs)
    _summary(
        {
            "resolved": len(result.resolved),
            "unresolved": len(result.unresolved),
            "review": len(result.review_queue),
        }
    )
    if args.strict and (result.unresolved or result.review_queue):
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
            _err(f"--backend is required ({args.weaver}.{args.capability} has: "
                 f"{', '.join(cap.backends)})")
            return 1

    want = _split_types(args.want) or sorted(cap.produces)
    sets = _collect_inputs(args)
    weaver = registry.get_weaver(args.weaver)
    _err(f"running {args.weaver}.{args.capability} over {len(sets)} input(s)…")
    results = asyncio.run(
        weaver.execute_batch(
            args.capability, sets,
            requested_outputs=frozenset(want), backend=backend,
        )
    )

    records: list[dict[str, Any]] = []
    counts = {"resolved": 0, "unresolved": 0}
    for ss, wr in zip(sets, results):
        merged = ss.clone()
        merged.merge_result(wr)
        status = "resolved" if wr.status.name == "OK" else "unresolved"
        counts[status] = counts.get(status, 0) + 1
        records.append(_record(ss.entity_id, status, merged, want))
    _emit(records, args.format, want)
    _summary(counts)
    if args.strict and counts.get("unresolved"):
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
            k: {"produced_by": sorted(producers.get(k, [])),
                "consumed_by": sorted(consumers.get(k, []))}
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
            available_types=frozenset(frm), target_types=frozenset(to)
        )
    except (NoPathError, NoPlanError) as exc:
        _err(f"no route from {frm} to {to}: {exc}")
        return 1
    print(f"{', '.join(frm)}  →  {', '.join(to)}   ({len(braid.steps)} step(s))")
    for i, step in enumerate(braid.steps, start=1):
        ins = ", ".join(sorted(step.input_types))
        outs = ", ".join(sorted(step.output_types))
        print(f"  {i}. {step.weaver_id}.{step.capability_id} "
              f"[{step.primary_backend}]: {ins} → {outs}")
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
    p.add_argument("--have", action="append", metavar="TYPE=VALUE",
                   help="an input strand; repeatable. Broadcast onto every --in-file row.")
    p.add_argument("--in-file", metavar="PATH",
                   help="batch input: a CSV/TSV with type-id columns, or (with --in-type) "
                        "one value per line. Use '-' for stdin.")
    p.add_argument("--in-type", metavar="TYPE",
                   help="treat --in-file as one VALUE per line of this strand type.")


def _add_output_flags(p: argparse.ArgumentParser, *, strict: bool = True) -> None:
    p.add_argument("--format", choices=["human", "json", "jsonl", "tsv", "csv"],
                   default="human", help="output format (default: human).")
    p.add_argument("--only", metavar="WEAVERS",
                   help="restrict to these weaver ids (comma/space separated).")
    if strict:
        p.add_argument("--strict", action="store_true",
                       help="exit non-zero if any input is unresolved or needs review.")


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
    w.add_argument("--expand", default="none", metavar="none|all|top:K",
                   help="fan out one→many set outputs (default: none = keep the best one).")
    w.add_argument("--references", action="store_true",
                   help="print source citations for the route to stderr.")
    _add_output_flags(w)
    w.set_defaults(func=_cmd_weave)

    # run
    r = sub.add_parser("run", help="call ONE weaver capability directly (no routing).")
    r.add_argument("weaver", help="weaver id (see `braidworks weavers`).")
    r.add_argument("capability", help="capability id.")
    r.add_argument("--want", metavar="TYPE[,TYPE…]",
                   help="restrict outputs (default: all the capability produces).")
    r.add_argument("--backend", help="backend name (required only if the capability has >1).")
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
