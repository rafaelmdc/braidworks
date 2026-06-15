"""The ``weaverkit`` command line: ``new`` (scaffold) and ``verify`` (conform).

    weaverkit new    --spec weaver.spec.toml --dest weavers/madin_weaver
    weaverkit verify --spec weaver.spec.toml [--package madin_weaver]
    weaverkit index  [--root .] [--out weavers-index.tsv] [--keys-out keys-index.md]
    weaverkit view   [--out braidworks-view.html] [--from K --to K] [--policy local_first]

``new`` validates the spec, then stamps a package. ``verify`` validates the spec
and — if the built package is importable — checks its manifest, reachability, and
fingerprints against the spec. ``verify --strict`` is the definition-of-done: it
additionally fails while any scaffold placeholder remains (``NotImplementedError``,
``# TODO(...)``, a ``-TODO`` fingerprint) or the golden examples can't actually run.
Both exit non-zero on any problem, so they slot straight into a Makefile or CI gate.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
import tomllib
from pathlib import Path

from braidworks.core import ATTRIBUTION_REQUIRED, citation_requirement, is_known_license

from weaverkit.conformance import check_fingerprints, check_golden, check_manifest
from weaverkit.index import uncatalogued_outputs, write_index, write_key_index
from weaverkit.scaffold import ScaffoldError, scaffold
from weaverkit.spec import SpecError, WeaverSpec, load_spec, validate_spec

# Substrings the scaffold leaves at unimplemented spots; --strict fails while any
# remain. '# TODO(' / '-TODO"' are scaffold-specific (won't flag generic TODOs).
_INCOMPLETE_MARKERS = ("NotImplementedError", '-TODO"', "# TODO(")
# Unique placeholder input the scaffolded live-E2E ships with (see scaffold _TEST_E2E_API).
_E2E_PLACEHOLDER = "TODO-real-input"


def _load_validated(spec_path: str) -> tuple[WeaverSpec | None, list[str]]:
    """Load and validate a spec. Returns (spec | None, problems)."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        return None, [str(exc)]
    return spec, validate_spec(spec)


def _print_problems(header: str, problems: list[str]) -> None:
    print(header, file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)


def _provenance_warnings(spec: WeaverSpec) -> list[str]:
    """Advisory checks on a spec's reference metadata (issue #1). Non-fatal.

    Surfaces gaps that would weaken automatic references: an unrecognized license id
    (classifies as 'restricted'), or a missing citation under a license that requires
    attribution. These warn rather than fail so existing weavers keep verifying while
    the metadata is brought up to standard.
    """
    warnings: list[str] = []
    if not is_known_license(spec.license):
        warnings.append(
            f"license {spec.license!r} is not a known identifier (weaverkit treats it as "
            "'restricted'); prefer an SPDX id like 'CC-BY-4.0' / 'CC0-1.0' so references "
            "render correctly"
        )
    elif citation_requirement(spec.license) == ATTRIBUTION_REQUIRED and not spec.citation.strip():
        warnings.append(
            f"license {spec.license!r} requires attribution but [weaver].citation is empty "
            "— add the DOI / reference so a braid can credit this source"
        )
    return warnings


def _version_drift_warning(spec: WeaverSpec, spec_path: str) -> list[str]:
    """Warn when the spec version disagrees with the package's pyproject version.

    The two are independent sites that must stay in lockstep (the spec drives the
    manifest version; pyproject drives the released artifact and its git tag). Drift
    means a tag no longer identifies the manifest it shipped with. Non-fatal — read
    from the pyproject.toml next to the spec; silently skip if it isn't there.
    """
    pyproject = Path(spec_path).resolve().parent / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return []
    proj_version = str(data.get("project", {}).get("version", "")).strip()
    if proj_version and proj_version != spec.version:
        return [
            f"version drift: spec version {spec.version!r} != pyproject version "
            f"{proj_version!r} — reconcile so the released artifact matches its tag"
        ]
    return []


def cmd_new(args: argparse.Namespace) -> int:
    spec, problems = _load_validated(args.spec)
    if problems:
        _print_problems(f"spec {args.spec} is invalid:", problems)
        return 1
    assert spec is not None
    try:
        written = scaffold(
            spec,
            args.dest,
            spec_toml=Path(args.spec).read_text(),
            force=args.force,
        )
    except ScaffoldError as exc:
        print(f"cannot scaffold: {exc}", file=sys.stderr)
        return 1
    print(f"scaffolded {spec.package} into {args.dest} ({len(written)} files)")
    print("next: implement the # TODO backend fetch/fingerprint, then `make verify`")
    return 0


class BuilderNotFound(Exception):
    """The package imports, but has no ``build_<package>()`` introspection builder."""


def _build_weaver(package: str):
    """Import and call ``<package>.factory.build_<package>`` (the zero-config builder).

    Raises :class:`BuilderNotFound` (not a bare ``AttributeError``) when the builder
    is misnamed, so ``verify`` can report a fix instead of crashing with a traceback.
    """
    module = importlib.import_module(f"{package}.factory")
    builder = getattr(module, f"build_{package}", None)
    if builder is None:
        raise BuilderNotFound(
            f"{package}.factory has no build_{package}(). verify calls the zero-config "
            f"introspection builder by that exact name. fix: add (or alias) "
            f"build_{package}() that wires the backends present-but-unconfigured."
        )
    return builder()


def _completeness_problems(package: str) -> list[str]:
    """Source files still carrying scaffold placeholders (NotImplemented / TODO).

    Scans the package ``src/`` plus the sibling ``tests/test_e2e_live.py`` — the live
    drift test ships with a ``"TODO-real-input"`` placeholder that is skipped without
    ``BRAIDWORKS_RUN_LIVE=1``, so it could otherwise pass ``--strict`` un-filled.
    """
    module = importlib.import_module(package)
    if not getattr(module, "__file__", None):
        return []
    pkg_dir = Path(module.__file__).parent
    problems: list[str] = []
    for py in sorted(pkg_dir.rglob("*.py")):
        text = py.read_text()
        hit = next((m for m in _INCOMPLETE_MARKERS if m in text), None)
        if hit is not None:
            rel = py.relative_to(pkg_dir.parent)
            problems.append(f"{rel}: still a scaffold placeholder ({hit!r}) — implement it")

    # The live-E2E test lives outside src/ (weaver_root/tests/), so the rglob above
    # never sees it. Check it explicitly when present (editable/source checkout).
    e2e = pkg_dir.parent.parent / "tests" / "test_e2e_live.py"
    if e2e.is_file() and _E2E_PLACEHOLDER in e2e.read_text():
        problems.append(
            f"tests/test_e2e_live.py: still a scaffold placeholder "
            f"({_E2E_PLACEHOLDER!r}) — replace with a real known-truth example"
        )
    return problems


def _build_fixture_weaver(package: str):
    """Return a fixture-backed weaver via ``build_<package>_fixture()``, or None.

    The fixture is the deterministic substrate for ``--strict`` golden (Decision E):
    a weaver wired against a tiny, committed/synthesized dataset that needs no
    download or network. Optional — absent is fine unless no backend is otherwise
    runnable.
    """
    module = importlib.import_module(f"{package}.factory")
    builder = getattr(module, f"build_{package}_fixture", None)
    return builder() if builder is not None else None


def _first_runnable_backend(weaver, backends: tuple[str, ...]) -> str | None:
    """First backend whose fingerprint shows it's configured (so golden can run)."""
    for b in backends:
        try:
            fp = weaver.backend_fingerprint(b)
        except Exception:  # noqa: BLE001 - an unconfigured backend just isn't runnable
            continue
        text = str(fp).strip().lower()
        if fp and text not in ("", "unknown") and not text.startswith("unconfigured:"):
            return b
    return None


def _strict_problems(package: str, spec: WeaverSpec, weaver) -> list[str]:
    """Definition-of-done: no placeholders, and golden runs against deterministic data.

    Golden runs against a fixture (``build_<package>_fixture()``) when present, else
    against an already-configured backend on the introspection build (e.g. a bundled
    local dataset). It never falls back to external data, so the result is
    reproducible regardless of CI's environment (Decision E).
    """
    problems = _completeness_problems(package)
    if problems:
        return problems  # golden can't run while fetch is still a placeholder
    if not spec.golden:
        problems.append(
            "--strict: spec has no golden examples; add at least one known "
            "input -> expected output so behavior is verified, not just structure"
        )
        return problems
    candidate = _build_fixture_weaver(package) or weaver
    backend = _first_runnable_backend(candidate, spec.backends)
    if backend is None:
        problems.append(
            "--strict: golden cannot run — no configured backend and no fixture. fix: add "
            f"build_{package}_fixture() returning a weaver backed by a tiny deterministic "
            "dataset so golden runs reproducibly (see weaverkit/docs/decisions.md, Decision E)"
        )
        return problems
    try:
        problems += asyncio.run(check_golden(candidate, spec, backend=backend))
    except Exception as exc:  # noqa: BLE001 - convert any run failure into a finding
        problems.append(
            f"--strict: golden examples could not run on backend {backend!r} "
            f"({exc}); check the fixture / backend and the fetch implementation"
        )
    return problems


def cmd_verify(args: argparse.Namespace) -> int:
    spec, problems = _load_validated(args.spec)
    if problems:
        _print_problems(f"spec {args.spec} is invalid:", problems)
        return 1
    assert spec is not None

    package = args.package or spec.package
    try:
        weaver = _build_weaver(package)
    except BuilderNotFound as exc:
        _print_problems(f"{package}: cannot build to verify:", [str(exc)])
        return 1
    except ModuleNotFoundError:
        if args.strict:
            _print_problems(
                f"--strict: package {package!r} is not importable:",
                ["run from the weaver's directory, or pass --package"],
            )
            return 1
        print(
            f"spec is valid; package {package!r} is not importable, so manifest/"
            "fingerprint checks were skipped (run from the weaver's directory, or "
            "pass --package)."
        )
        return 0

    conformance = check_manifest(weaver.MANIFEST, spec)
    conformance += check_fingerprints(weaver, list(spec.backends))
    if conformance:
        _print_problems(f"{package} does not conform to {args.spec}:", conformance)
        return 1

    for w in _provenance_warnings(spec) + _version_drift_warning(spec, args.spec):
        print(f"warning: {w}", file=sys.stderr)

    if args.strict:
        incomplete = _strict_problems(package, spec, weaver)
        if incomplete:
            _print_problems(f"{package} is not done (--strict):", incomplete)
            return 1
        print(f"{package} is complete: conforms + no placeholders + golden examples pass")
        return 0

    print(f"{package} conforms to {args.spec} (spec valid, manifest + fingerprints OK)")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    rows = write_index(args.root, args.out)
    write_key_index(args.root, args.keys_out)
    weavers = sorted({r.weaver for r in rows})
    unmet = sum(1 for r in rows if r.unmet_inputs)
    print(
        f"indexed {len(rows)} capabilities across {len(weavers)} weaver(s) "
        f"-> {args.out} + key catalog -> {args.keys_out}"
    )
    if unmet:
        print(
            f"note: {unmet} capability row(s) have unmet inputs (no other weaver "
            "produces them). That's allowed — see the 'unmet_inputs' column."
        )
    uncatalogued = uncatalogued_outputs(rows)
    if uncatalogued:
        print(
            f"note: {len(uncatalogued)} produced field(s) are not in the output catalog "
            "(weaverkit.keys.OUTPUT_KEYS) or SHARED_KEYS — catalog them to keep names "
            f"consistent: {', '.join(uncatalogued)}"
        )
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    import json as _json

    from weaverkit.view import parse_policy, write_view

    from_types = frozenset(args.from_type or ())
    to_types = frozenset(args.to_type or ())
    if bool(from_types) ^ bool(to_types):
        print("--from and --to must be given together (or neither)", file=sys.stderr)
        return 1
    try:
        policy = parse_policy(args.policy)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    run: dict | None = None
    if args.run:
        try:
            run = _json.loads(Path(args.run).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"--run: cannot read {args.run!r}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(run, dict) or "resolved" not in run:
            print(
                f"--run: {args.run!r} is not an ExecutionResult.to_json() "
                "(expected a JSON object with a 'resolved' key)",
                file=sys.stderr,
            )
            return 1

    data = write_view(
        args.out,
        from_types=from_types or None,
        to_types=to_types or None,
        policy=policy,
        run=run,
    )
    net = data["network"]["stats"]
    extras = ""
    if data["paths"]:
        extras += f", {len(data['paths'])} path view"
    if data["runs"]:
        extras += f", {len(data['runs'])} run view(s)"
    print(
        f"wrote {args.out} — {net['weavers']} weaver(s), {net['types']} join key(s), "
        f"{net['edges']} link(s)" + extras
    )
    for problem in data["meta"]["problems"]:
        print(f"  note: {problem}", file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the interactive GUI server (requires the optional ``[serve]`` extra)."""
    from weaverkit.serve import serve

    try:
        serve(host=args.host, port=args.port, open_browser=not args.no_open)
    except RuntimeError as exc:  # missing [serve] extra
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print()
    return 0


def cmd_references(args: argparse.Namespace) -> int:
    """Print the citations for discovered weavers: all, a chosen set, or a braid path."""
    import json as _json

    from braidworks.core import format_references, references_for, references_for_braid
    from braidworks.core.exceptions import NoPathError, NoPlanError
    from braidworks.core.planner import Braider

    from weaverkit.view import discover_registry, parse_policy

    discovery = discover_registry()
    registry = discovery.registry

    from_types = frozenset(args.from_type or ())
    to_types = frozenset(args.to_type or ())
    if bool(from_types) ^ bool(to_types):
        print("--from and --to must be given together (or neither)", file=sys.stderr)
        return 1

    if from_types:
        try:
            policy = parse_policy(args.policy)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        try:
            braid = Braider(registry).plan(from_types, to_types, backend_policy=policy)
        except (NoPathError, NoPlanError) as exc:
            print(
                f"no braid for {sorted(from_types)} -> {sorted(to_types)}: {exc}",
                file=sys.stderr,
            )
            return 1
        refs = references_for_braid(braid, registry)
    elif args.weaver:
        refs = references_for(args.weaver, registry)
    else:
        refs = references_for([m.weaver_id for m in registry.manifests()], registry)

    if args.json:
        print(_json.dumps([r.to_json() for r in refs], indent=2))
    else:
        text = format_references(refs)
        print(text if text else "(no references — no source provenance found)")
    for problem in discovery.problems:
        print(f"note: {problem}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weaverkit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a weaver package from a spec")
    p_new.add_argument("--spec", required=True, help="path to weaver.spec.toml")
    p_new.add_argument("--dest", required=True, help="destination package directory")
    p_new.add_argument("--force", action="store_true", help="overwrite a non-empty dest")
    p_new.set_defaults(func=cmd_new)

    p_verify = sub.add_parser("verify", help="check a weaver conforms to its spec")
    p_verify.add_argument("--spec", required=True, help="path to weaver.spec.toml")
    p_verify.add_argument(
        "--package",
        default=None,
        help="importable package name (defaults to <db_name>_weaver)",
    )
    p_verify.add_argument(
        "--strict",
        action="store_true",
        help="definition-of-done: fail if any scaffold placeholder remains or golden can't run",
    )
    p_verify.set_defaults(func=cmd_verify)

    p_index = sub.add_parser(
        "index", help="build a key index (consumes/produces) across all weavers"
    )
    p_index.add_argument("--root", default=".", help="workspace root to scan (default: .)")
    p_index.add_argument(
        "--out", default="weavers-index.tsv", help="output file (.tsv or .csv; default .tsv)"
    )
    p_index.add_argument(
        "--keys-out",
        default="keys-index.md",
        help="human-readable key map (Markdown; default keys-index.md)",
    )
    p_index.set_defaults(func=cmd_index)

    p_view = sub.add_parser(
        "view", help="render an interactive HTML view of the weaver network (+ a braid path)"
    )
    p_view.add_argument(
        "--out", default="braidworks-view.html", help="output HTML file (default: braidworks-view.html)"
    )
    p_view.add_argument(
        "--from", dest="from_type", action="append", metavar="KEY",
        help="a starting/available type for the braid path (repeatable)",
    )
    p_view.add_argument(
        "--to", dest="to_type", action="append", metavar="KEY",
        help="a target type for the braid path (repeatable)",
    )
    p_view.add_argument(
        "--policy", default="local_first",
        help="backend policy for the path: local_first|api_first|local_only|api_only",
    )
    p_view.add_argument(
        "--run", metavar="RESULT.json",
        help="an ExecutionResult.to_json() file; adds a run-lineage (fan-out trace) view "
        "per originating input",
    )
    p_view.set_defaults(func=cmd_view)

    p_serve = sub.add_parser(
        "serve", help="run the interactive GUI (build/plan braids in the browser)"
    )
    p_serve.add_argument("--port", type=int, default=8765, help="port (default: 8765)")
    p_serve.add_argument("--host", default="127.0.0.1", help="bind host (default: localhost)")
    p_serve.add_argument(
        "--no-open", action="store_true", help="do not open a browser automatically"
    )
    p_serve.set_defaults(func=cmd_serve)

    p_refs = sub.add_parser(
        "references",
        help="print source citations for weavers (all, a chosen set, or a braid path)",
    )
    p_refs.add_argument(
        "--weaver", action="append", metavar="ID",
        help="restrict to this weaver id (repeatable; default: all discovered weavers)",
    )
    p_refs.add_argument(
        "--from", dest="from_type", action="append", metavar="KEY",
        help="cite only sources on the braid path from this type (repeatable; needs --to)",
    )
    p_refs.add_argument(
        "--to", dest="to_type", action="append", metavar="KEY",
        help="target type for the braid path (repeatable; needs --from)",
    )
    p_refs.add_argument(
        "--policy", default="local_first",
        help="backend policy for the path: local_first|api_first|local_only|api_only",
    )
    p_refs.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_refs.set_defaults(func=cmd_references)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
