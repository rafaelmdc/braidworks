"""The ``weaverkit`` command line: ``new`` (scaffold) and ``verify`` (conform).

    weaverkit new    --spec weaver.spec.toml --dest weavers/madinweaver
    weaverkit verify --spec weaver.spec.toml [--package madinweaver]
    weaverkit index  [--root .] [--out weavers-index.tsv]

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
from pathlib import Path

from weaverkit.conformance import check_fingerprints, check_golden, check_manifest
from weaverkit.index import write_index
from weaverkit.scaffold import ScaffoldError, scaffold
from weaverkit.spec import SpecError, WeaverSpec, load_spec, validate_spec

# Substrings the scaffold leaves at unimplemented spots; --strict fails while any
# remain. '# TODO(' / '-TODO"' are scaffold-specific (won't flag generic TODOs).
_INCOMPLETE_MARKERS = ("NotImplementedError", '-TODO"', "# TODO(")


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
    """Source files still carrying scaffold placeholders (NotImplemented / TODO)."""
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
    weavers = sorted({r.weaver for r in rows})
    unmet = sum(1 for r in rows if r.unmet_inputs)
    print(f"indexed {len(rows)} capabilities across {len(weavers)} weaver(s) -> {args.out}")
    if unmet:
        print(
            f"note: {unmet} capability row(s) have unmet inputs (no other weaver "
            "produces them). That's allowed — see the 'unmet_inputs' column."
        )
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
        help="importable package name (defaults to <db_name>weaver)",
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
    p_index.set_defaults(func=cmd_index)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
