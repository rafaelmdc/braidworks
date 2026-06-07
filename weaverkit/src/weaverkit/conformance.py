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
from weaverkit.spec import GoldenSpec, WeaverSpec, load_spec, validate_spec

_BAD_FINGERPRINTS = {"", "unknown"}


def check_manifest(manifest: WeaverManifest, spec: WeaverSpec) -> list[str]:
    """Check a weaver's declared manifest against its spec. Empty == conformant."""
    problems: list[str] = []

    if manifest.weaver_id != spec.resolved_weaver_id:
        problems.append(
            f"manifest weaver_id {manifest.weaver_id!r} != spec weaver_id "
            f"{spec.resolved_weaver_id!r}"
        )

    declared = {c.id: c for c in manifest.capabilities}
    expected = {c.id: c for c in spec.capabilities}

    for cap_id in expected:
        if cap_id not in declared:
            problems.append(f"spec declares capability {cap_id!r} but the manifest does not")
    for cap_id in declared:
        if cap_id not in expected:
            problems.append(
                f"manifest declares capability {cap_id!r} that is not in the spec"
            )

    for cap_id, spec_cap in expected.items():
        man_cap = declared.get(cap_id)
        if man_cap is None:
            continue

        if set(man_cap.consumes) != set(spec_cap.consumes):
            problems.append(
                f"capability {cap_id!r}: manifest consumes {sorted(man_cap.consumes)} "
                f"!= spec consumes {sorted(spec_cap.consumes)}"
            )
        # Reachability re-check on the *built* manifest, independent of the spec.
        for key in man_cap.consumes:
            if not is_shared_key(key):
                problems.append(
                    f"capability {cap_id!r}: manifest consumes {key!r}, not a registered "
                    "shared key — the weaver would be unreachable"
                )

        if set(man_cap.produces) != set(spec_cap.produces):
            problems.append(
                f"capability {cap_id!r}: manifest produces {sorted(man_cap.produces)} "
                f"!= spec produces {sorted(spec_cap.produces)}"
            )

        man_groups = {g.id: set(g.outputs) for g in man_cap.output_groups}
        spec_groups = {g.id: set(g.outputs) for g in spec_cap.groups}
        if man_groups != spec_groups:
            problems.append(
                f"capability {cap_id!r}: manifest output groups {man_groups} "
                f"!= spec output groups {spec_groups}"
            )

        for b in man_cap.backends:
            if b not in spec.backends:
                problems.append(
                    f"capability {cap_id!r}: manifest backend {b!r} is not in the "
                    f"spec's backends {list(spec.backends)}"
                )

    return problems


def check_fingerprints(weaver: BaseWeaver, backends: list[str]) -> list[str]:
    """Each backend must yield a real, non-``unknown`` fingerprint. Empty == ok."""
    problems: list[str] = []
    for backend in backends:
        try:
            fp = weaver.backend_fingerprint(backend)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the check
            problems.append(f"backend {backend!r}: backend_fingerprint raised {exc!r}")
            continue
        if fp is None or str(fp).strip().lower() in _BAD_FINGERPRINTS:
            problems.append(
                f"backend {backend!r}: fingerprint is {fp!r} — must be a stable, "
                "version-specific string (never '' or 'unknown')"
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
    requested = frozenset(golden.expect)
    result = await weaver.execute(
        golden.capability,
        strand_set,
        requested_outputs=requested,
        backend=backend,
    )

    if result.status is not WeaveStatus.OK:
        return [
            f"golden ({golden.capability}, input={golden.input}): expected OK, "
            f"got {result.status.value} (errors={list(result.errors)})"
        ]

    got = {s.type_id: s.value for s in result.strands}
    problems: list[str] = []
    for key, want in golden.expect.items():
        if key not in got:
            problems.append(
                f"golden ({golden.capability}, input={golden.input}): "
                f"expected output {key!r} was not produced (got {sorted(got)})"
            )
        elif got[key] != want:
            problems.append(
                f"golden ({golden.capability}, input={golden.input}): "
                f"{key!r} = {got[key]!r}, expected {want!r}"
            )
    return problems


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
            configured = weaver.backend_fingerprint(backend) not in _BAD_FINGERPRINTS
        except Exception:  # noqa: BLE001
            configured = False
        if not configured:
            pytest.skip(f"backend {backend!r} not configured; cannot run golden examples")
        problems = await check_golden(weaver, spec, backend=backend)
        assert not problems, "golden examples failed:\n" + "\n".join(problems)
