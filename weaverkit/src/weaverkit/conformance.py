"""Conformance: machine checks that a *built* weaver matches its spec.

The spec validator (``weaverkit.spec``) checks the contract on paper. This module
checks the code that was written against it:

- :func:`check_manifest` — the weaver's ``MANIFEST`` declares exactly the
  capabilities/consumes/produces/groups the spec promised, keyed on shared keys
  (reachable by construction), with backends drawn from the spec's set.
- :func:`check_fingerprints` — every backend returns a real, stable fingerprint,
  never ``""`` or ``"unknown"`` (which silently disables cache invalidation).
- :func:`run_golden` / :func:`check_golden` — actually execute the spec's golden
  examples and confirm the expected strands come back.
- :class:`WeaverConformanceTests` — a pytest mixin that runs all of the above; a
  weaver's test module subclasses it once and the contract is enforced in CI.

All ``check_*`` functions return ``list[str]`` (empty == conformant) so problems
aggregate instead of failing one at a time.
"""

from __future__ import annotations

from typing import ClassVar

from braidworks.core.capability import WeaverManifest
from braidworks.core.result import WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

from weaverkit.keys import is_shared_key
from weaverkit.spec import (
    GoldenSpec,
    WeaverSpec,
    load_spec,
    type_descriptions,
    undescribed_types,
    validate_spec,
)

_BAD_FINGERPRINTS = {"", "unknown"}


def _is_configured_fingerprint(fp: object) -> bool:
    """Whether a backend fingerprint indicates a configured, runnable backend.

    Mirrors the dispatch gate: ``BackendDispatchWeaver.backend_fingerprint`` returns
    the sentinel ``"unconfigured:<backend>"`` when ``is_configured()`` is False, so a
    fingerprint that is empty/``"unknown"`` *or* an ``"unconfigured:"`` sentinel means
    the golden examples must skip (not run and crash on ``BackendUnavailable``).
    """
    text = str(fp).strip()
    return text.lower() not in _BAD_FINGERPRINTS and not text.startswith("unconfigured:")


def check_manifest(manifest: WeaverManifest, spec: WeaverSpec) -> list[str]:
    """Check a weaver's declared manifest against its spec. Empty == conformant."""
    problems: list[str] = []

    # vocab.py is generated from the spec, so the fix for almost any mismatch is
    # the same: change the spec and re-stamp it.
    regen = "fix: edit weaver.spec.toml then regenerate vocab.py (`weaverkit new --force`)"

    if manifest.weaver_id != spec.resolved_weaver_id:
        problems.append(
            f"manifest weaver_id {manifest.weaver_id!r} != spec weaver_id "
            f"{spec.resolved_weaver_id!r} — {regen}"
        )

    declared = {c.id: c for c in manifest.capabilities}
    expected = {c.id: c for c in spec.capabilities}

    for cap_id in expected:
        if cap_id not in declared:
            problems.append(
                f"spec declares capability {cap_id!r} but the manifest does not — {regen}"
            )
    for cap_id in declared:
        if cap_id not in expected:
            problems.append(
                f"manifest declares capability {cap_id!r} that is not in the spec — "
                "fix: add it under [[capability]] in weaver.spec.toml, or remove it from vocab.py"
            )

    for cap_id, spec_cap in expected.items():
        man_cap = declared.get(cap_id)
        if man_cap is None:
            continue

        if set(man_cap.consumes) != set(spec_cap.consumes):
            problems.append(
                f"capability {cap_id!r}: manifest consumes {sorted(man_cap.consumes)} "
                f"!= spec consumes {sorted(spec_cap.consumes)} — {regen}"
            )
        # Reachability re-check on the *built* manifest, independent of the spec.
        for key in man_cap.consumes:
            if not is_shared_key(key):
                problems.append(
                    f"capability {cap_id!r}: manifest consumes {key!r}, not a registered "
                    "shared key — the weaver would be unreachable. fix: use a key from "
                    "weaverkit.keys.SHARED_KEYS, or add the new bridge key there in this PR"
                )

        if set(man_cap.produces) != set(spec_cap.produces):
            problems.append(
                f"capability {cap_id!r}: manifest produces {sorted(man_cap.produces)} "
                f"!= spec produces {sorted(spec_cap.produces)} — {regen}"
            )

        man_groups = {g.id: set(g.outputs) for g in man_cap.output_groups}
        spec_groups = {g.id: set(g.outputs) for g in spec_cap.groups}
        if man_groups != spec_groups:
            problems.append(
                f"capability {cap_id!r}: manifest output groups {man_groups} "
                f"!= spec output groups {spec_groups} — {regen}"
            )

        if set(man_cap.set_outputs) != set(spec_cap.set_outputs):
            problems.append(
                f"capability {cap_id!r}: manifest set_outputs {sorted(man_cap.set_outputs)} "
                f"!= spec set_outputs {sorted(spec_cap.set_outputs)} — {regen}"
            )

        if dict(man_cap.totals) != dict(spec_cap.totals):
            problems.append(
                f"capability {cap_id!r}: manifest totals {dict(sorted(man_cap.totals.items()))} "
                f"!= spec totals {dict(sorted(spec_cap.totals.items()))} — {regen}"
            )

        if frozenset(man_cap.lists) != frozenset(spec_cap.lists):
            problems.append(
                f"capability {cap_id!r}: manifest lists {sorted(man_cap.lists)} "
                f"!= spec lists {sorted(spec_cap.lists)} — {regen}"
            )

        if man_cap.consumes_any != spec_cap.consumes_any:
            problems.append(
                f"capability {cap_id!r}: manifest consumes_any {man_cap.consumes_any} "
                f"!= spec consumes_any {spec_cap.consumes_any} — {regen}"
            )

        man_params = {p.name: (p.type, tuple(p.enum), p.default) for p in man_cap.parameters}
        spec_params = {p.name: (p.type, tuple(p.enum), p.default) for p in spec_cap.parameters}
        if man_params != spec_params:
            problems.append(
                f"capability {cap_id!r}: manifest parameters {sorted(man_params)} "
                f"!= spec parameters {sorted(spec_params)} — {regen}"
            )

        for b in man_cap.backends:
            if b not in spec.backends:
                problems.append(
                    f"capability {cap_id!r}: manifest backend {b!r} is not in the "
                    f"spec's backends {list(spec.backends)} — fix: add {b!r} to "
                    "[weaver].backends in weaver.spec.toml, or drop it from the capability"
                )

    # Descriptions are optional while older vocab.py files are regenerated (an empty
    # manifest only warns, see description_warnings); once present they must match.
    expected_descriptions = type_descriptions(spec)
    if manifest.type_descriptions and dict(manifest.type_descriptions) != expected_descriptions:
        changed = sorted(
            t
            for t in set(manifest.type_descriptions) | set(expected_descriptions)
            if manifest.type_descriptions.get(t) != expected_descriptions.get(t)
        )
        problems.append(
            f"manifest type descriptions differ from the spec/key registry for {changed} — {regen}"
        )

    return problems


def description_warnings(manifest: WeaverManifest, spec: WeaverSpec) -> list[str]:
    """Advisory gaps in type descriptions (non-fatal, like provenance warnings)."""
    warnings = []
    if not manifest.type_descriptions and type_descriptions(spec):
        warnings.append(
            "the manifest has no type descriptions (vocab.py predates them) — "
            "regenerate vocab.py so users can find this weaver's fields by meaning"
        )
    missing = undescribed_types(spec)
    if missing:
        warnings.append(
            f"no description for {missing} — add it to weaverkit.keys (OUTPUT_KEYS / "
            "SHARED_KEYS) or to the spec's [types] table"
        )
    return warnings


def check_fingerprints(weaver: BaseWeaver, backends: list[str]) -> list[str]:
    """Each backend must yield a real, non-``unknown`` fingerprint. Empty == ok."""
    problems: list[str] = []
    for backend in backends:
        try:
            fp = weaver.backend_fingerprint(backend)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the check
            problems.append(
                f"backend {backend!r}: backend_fingerprint raised {exc!r} — "
                f"fix: implement fingerprint() in backends/{backend}.py"
            )
            continue
        if fp is None or str(fp).strip().lower() in _BAD_FINGERPRINTS:
            problems.append(
                f"backend {backend!r}: fingerprint is {fp!r} — must be a stable, "
                "version-specific string (never '' or 'unknown'). fix: return a release "
                f"tag / dump date / checksum from fingerprint() in backends/{backend}.py"
            )
    return problems


async def run_golden(
    weaver: BaseWeaver, spec: WeaverSpec, golden: GoldenSpec, *, backend: str
) -> list[str]:
    """Execute one golden example and check the expected strands come back."""
    cap = spec.capability(golden.capability)
    if cap is None:  # pragma: no cover - guarded by validate_spec upstream
        return [f"golden references undeclared capability {golden.capability!r}"]

    strand_set = StrandSet.from_strands(
        "golden",
        [Strand(type_id=k, value=v) for k, v in golden.input.items()],
    )
    # ``<list>.total`` expects a list's true size: request the list itself.
    requested = frozenset(
        k.removesuffix(".total") if k not in cap.produces else k for k in golden.expect
    )
    result = await weaver.execute(
        golden.capability,
        strand_set,
        requested_outputs=requested,
        backend=backend,
    )

    if result.status is not WeaveStatus.OK:
        return [
            (
                f"golden ({golden.capability}, input={golden.input}): expected OK, "
                f"got {result.status.value} (errors={list(result.errors)}) — fix: make "
                f"the {backend!r} backend's fetch resolve this input, or correct the golden"
            )
        ]

    got = {s.type_id: s.value for s in result.strands}
    problems: list[str] = []
    where = f"golden ({golden.capability}, input={golden.input})"
    for strand in result.strands:
        problems.extend(_size_problems(where, strand))
    sizes = {s.type_id: _known_size(s) for s in result.strands}
    for key, want in golden.expect.items():
        base = key.removesuffix(".total")
        if base != key and key not in cap.produces:
            if base not in got:
                problems.append(f"{where}: expected list {base!r} was not produced")
            elif sizes[base] != want:
                problems.append(
                    f"{where}: {base!r} has total {sizes[base]!r}, expected {want!r}, got "
                    f"{sizes[base]!r} — if the backend stopped early, return "
                    "Listing(items, total=n) or Listing(items, total=None, complete=False)"
                )
            continue
        if key not in got:
            problems.append(
                f"golden ({golden.capability}, input={golden.input}): "
                f"expected output {key!r} was not produced (got {sorted(got)}) — fix: have "
                f"fetch set record.values[{key!r}], or drop {key!r} from the golden expect"
            )
        elif got[key] != want:
            problems.append(
                f"golden ({golden.capability}, input={golden.input}): "
                f"{key!r} = {got[key]!r}, expected {want!r} — fix: correct fetch's mapping "
                "or the expected value in weaver.spec.toml"
            )
    return problems


def _known_size(strand: Strand) -> int | None:
    """A list strand's true size: its ``total``, or its length when it said nothing."""
    if strand.total is not None:
        return strand.total
    if strand.complete and isinstance(strand.value, list):
        return len(strand.value)
    return None


def _size_problems(where: str, strand: Strand) -> list[str]:
    """A list's size must agree with its items: complete ⇒ total == len; total ≥ len."""
    if strand.total is None or not isinstance(strand.value, list):
        return []
    n = len(strand.value)
    if strand.total < n or (strand.complete and strand.total != n):
        state = "complete" if strand.complete else "partial"
        return [
            (
                f"{where}: {strand.type_id!r} is {state} with total {strand.total} but has "
                f"{n} items — return a Listing so core keeps the size consistent"
            )
        ]
    return []


async def check_golden(weaver: BaseWeaver, spec: WeaverSpec, *, backend: str) -> list[str]:
    """Run every golden example in the spec. Empty == all passed (or none defined)."""
    problems: list[str] = []
    for golden in spec.golden:
        problems.extend(await run_golden(weaver, spec, golden, backend=backend))
    return problems


class WeaverConformanceTests:
    """Pytest mixin: assert a built weaver conforms to its spec.

    Subclass once per weaver and provide:
      - ``spec_path: ClassVar[str]`` — path to the weaver's ``weaver.spec.toml``.
      - ``def build_weaver(self) -> BaseWeaver`` — construct the weaver.
      - ``golden_backend: ClassVar[str]`` — backend the golden examples run on
        (default ``"local"``).

    The golden test skips itself (rather than failing) when the chosen backend is
    not configured — golden examples need real data, which CI may not have. The
    static checks (manifest, reachability, fingerprints) always run.
    """

    spec_path: ClassVar[str]
    golden_backend: ClassVar[str] = "local"

    def build_weaver(self) -> BaseWeaver:  # pragma: no cover - overridden
        raise NotImplementedError

    def _spec(self) -> WeaverSpec:
        return load_spec(self.spec_path)

    def test_spec_is_valid(self) -> None:
        problems = validate_spec(self._spec())
        assert not problems, "spec is invalid:\n" + "\n".join(problems)

    def test_manifest_matches_spec(self) -> None:
        weaver = self.build_weaver()
        problems = check_manifest(weaver.MANIFEST, self._spec())
        assert not problems, "manifest does not match spec:\n" + "\n".join(problems)

    def test_fingerprints_not_unknown(self) -> None:
        spec = self._spec()
        weaver = self.build_weaver()
        problems = check_fingerprints(weaver, list(spec.backends))
        assert not problems, "bad backend fingerprints:\n" + "\n".join(problems)

    async def test_golden_examples(self) -> None:
        import pytest

        spec = self._spec()
        if not spec.golden:
            pytest.skip("no golden examples in spec")
        weaver = self.build_weaver()
        backend = self.golden_backend
        try:
            configured = _is_configured_fingerprint(weaver.backend_fingerprint(backend))
        except Exception:  # noqa: BLE001
            configured = False
        if not configured:
            pytest.skip(f"backend {backend!r} not configured; cannot run golden examples")
        problems = await check_golden(weaver, spec, backend=backend)
        assert not problems, "golden examples failed:\n" + "\n".join(problems)
