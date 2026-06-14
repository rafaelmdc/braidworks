"""The scaffold generator: stamp a whole weaver package from a validated spec.

This is the "deterministic 80%". Given a ``WeaverSpec``, :func:`scaffold` writes a
complete, importable weaver package whose ``MANIFEST`` already matches the spec
exactly (so ``weaverkit.conformance.check_manifest`` passes by construction) and
whose tests already wire up :class:`~weaverkit.conformance.WeaverConformanceTests`.

What it deliberately does *not* do is the novel ~20%: the backend ``fetch`` methods
raise ``NotImplementedError`` and the fingerprints are ``-TODO`` placeholders. Those
are the only spots an agent must edit, and they are marked ``# TODO``. Until they
are filled in, the static conformance checks pass and the golden test skips, giving
a green baseline to build from.

Templates are plain strings using ``{{TOKEN}}`` placeholders (Python's own braces
in the rendered code never collide, since they are single braces). ``vocab.py`` is
generated programmatically from the spec's capabilities rather than from a template,
because it is structured code, not boilerplate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from weaverkit.spec import WeaverSpec


class ScaffoldError(Exception):
    """The destination is unsafe to write (exists and ``force`` was not set)."""


def _camel(db_name: str) -> str:
    """``ncbi_gene`` -> ``NcbiGene`` (for class names like ``NcbiGeneWeaver``)."""
    return "".join(part.capitalize() for part in db_name.split("_"))


def _id_camel(name: str) -> str:
    """``resolve_traits`` / ``ncbi.resolve_name`` -> ``ResolveTraits`` / ``NcbiResolveName``."""
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[^0-9a-zA-Z]+", name) if p)


def _frozenset_literal(items: tuple[str, ...]) -> str:
    """Render a deterministic ``frozenset({...})`` literal (sorted)."""
    inner = ", ".join(repr(x) for x in sorted(items))
    return f"frozenset({{{inner}}})"


def _backend_needs_key(spec: WeaverSpec, backend: str) -> bool:
    """Whether ``backend`` should get API-key plumbing.

    The weaver declares an ``api_key`` need (``optional``/``required``), and the
    backend is a remote one — i.e. not the bundled ``local`` backend (a local file
    source never needs a key). The bulk backend is handled separately upstream.
    """
    return spec.api_key in ("optional", "required") and backend != "local"


def _api_key_tokens(api_key: str, env_var: str) -> dict[str, str]:
    """Render the api-key-dependent bits of the API backend stub."""
    if api_key == "required":
        return {
            "API_KEY_ENV": env_var,
            "API_KEY_PHRASE": "requires an API key",
            "API_KEY_CONFIGURED_EXPR": "self._api_key is not None",
            "API_KEY_CONFIGURED_COMMENT": (
                f"Requires the key: unconfigured until {env_var} is set "
                "(golden tests skip until then)."
            ),
        }
    # optional: the public API works without a key; one just unlocks more.
    return {
        "API_KEY_ENV": env_var,
        "API_KEY_PHRASE": "can use an optional API key",
        "API_KEY_CONFIGURED_EXPR": "True",
        "API_KEY_CONFIGURED_COMMENT": (
            f"Optional key: the API works without it; set {env_var} for higher "
            "rate limits / private data."
        ),
    }


def _vocab_source(spec: WeaverSpec) -> str:
    """Generate ``vocab.py`` from the spec — the manifest matches the spec exactly."""
    lines: list[str] = [
        '"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.',
        "",
        "The manifest is the machine-readable mirror of the spec; keep them in sync",
        "(``weaverkit verify`` checks this). Edit the spec and regenerate rather than",
        "hand-editing capabilities here.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from braidworks.core import Capability, OutputGroup, Provenance, WeaverManifest",
        "",
        f"WEAVER_ID = {spec.resolved_weaver_id!r}",
        f"WEAVER_VERSION = {spec.version!r}",
        "",
        "# Source/license/citation for automatic references — mirrors weaver.spec.toml.",
        "PROVENANCE = Provenance(",
        f"    source_url={spec.source_url!r},",
        f"    license={spec.license!r},",
        f"    citation={spec.citation!r},",
        f"    attribution={spec.attribution!r},",
        ")",
        "",
        "",
        "def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:",
        '    """Declare every capability for the wired-in backends."""',
        "    return WeaverManifest(",
        "        weaver_id=WEAVER_ID,",
        "        version=WEAVER_VERSION,",
        "        provenance=PROVENANCE,",
        "        capabilities=(",
    ]
    for cap in spec.capabilities:
        # Capability.backends is a tuple. If the spec pins per-capability backends,
        # emit a tuple literal; otherwise use the ``backends`` parameter.
        if cap.backends:
            cap_backends = "(" + ", ".join(repr(b) for b in cap.backends) + ",)"
        else:
            cap_backends = "backends"
        lines += [
            "            Capability(",
            f"                id={cap.id!r},",
            f"                consumes={_frozenset_literal(cap.consumes)},",
            f"                produces={_frozenset_literal(cap.produces)},",
            "                output_groups=(",
        ]
        for g in cap.groups:
            lines.append(
                f"                    OutputGroup(id={g.id!r}, outputs={_frozenset_literal(g.outputs)}),"
            )
        lines += [
            "                ),",
            f"                backends={cap_backends},",
        ]
        if cap.max_batch_size is not None:
            lines.append(f"                max_batch_size={cap.max_batch_size},")
        if cap.cost != 1.0:
            lines.append(f"                cost={cap.cost},")
        # Groups always computed internally — the shared mapper unions these into
        # WeaveResult.computed_groups so the cache key isn't under-reported.
        if cap.always_computed_groups:
            lines.append(
                f"                always_computed_groups="
                f"{_frozenset_literal(cap.always_computed_groups)},"
            )
        lines.append("            ),")
    lines += [
        "        ),",
        "    )",
        "",
    ]
    return "\n".join(lines)


def _contract_test_source(spec: WeaverSpec) -> str:
    """Generate ``tests/test_contract.py`` — order/length + cache-key contracts.

    Wires core's ``WeaverOrderContractTests`` (one per backend) and
    ``CacheFingerprintTests`` (one per capability with >=2 output groups) from the
    spec. The order tests *execute* the weaver, so they skip until a backend is
    configured (keeping a fresh scaffold green); the cache-key tests are pure and
    run immediately. Sample inputs are seeded from the spec's golden examples and
    padded with synthesized ones — replace them with real inputs.
    """
    pkg = spec.package
    backends_repr = repr(tuple(spec.backends))
    first_cap = spec.capabilities[0]
    minimal_output = sorted(first_cap.produces)[0]

    golden_by_cap: dict[str, list[dict]] = {}
    for g in spec.golden:
        golden_by_cap.setdefault(g.capability, []).append(dict(g.input))

    # Order-contract sample inputs: real golden inputs first, padded to >=5.
    samples: list[dict] = list(golden_by_cap.get(first_cap.id, []))
    n = 0
    while len(samples) < 5:
        samples.append({k: f"sample-{n}" for k in first_cap.consumes})
        n += 1

    lines: list[str] = [
        '"""Contract tests for {pkg} — execute_batch order/length + cache-key rules.'.format(
            pkg=pkg
        ),
        "",
        "Generated by weaverkit. The order tests execute the weaver and SKIP until a",
        "backend is configured; the cache-key tests are pure and run immediately. Do not",
        "weaken these — they are the framework contract. Replace the synthesized sample",
        "inputs below with real, distinct inputs from the source.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "from braidworks.core import Strand, StrandSet",
        "from braidworks.testing.contract import CacheFingerprintTests, WeaverOrderContractTests",
        "",
        f"from {pkg} import factory, vocab",
        "",
        f"_MANIFEST = vocab.build_manifest(backends={backends_repr})",
        "",
        "",
        "def _build_weaver():",
        "    # Prefer the offline fixture builder once you add it, so these run",
        "    # deterministically; until then fall back to the introspection builder",
        "    # (the order test then skips while the backend is unconfigured).",
        f"    builder = getattr(factory, 'build_{pkg}_fixture', None) or factory.build_{pkg}",
        "    return builder()",
        "",
    ]

    # One order contract per backend (exercising the first capability).
    for b in spec.backends:
        lines += [
            "",
            f"class Test{_camel(b)}Order(WeaverOrderContractTests):",
            f"    capability_id = {first_cap.id!r}",
            f"    minimal_outputs = frozenset({{{minimal_output!r}}})",
            f"    backend = {b!r}",
            "",
            "    def make_weaver(self):",
            "        weaver = _build_weaver()",
            "        strat = weaver._backends.get(self.backend)",
            "        if strat is None or not strat.is_configured():",
            "            pytest.skip(f'backend {self.backend!r} not configured')",
            "        return weaver",
            "",
            "    def sample_strand_sets(self):",
            "        # TODO: replace with >=5 real, distinct inputs from the source.",
            f"        samples = {samples!r}",
            "        return [",
            "            StrandSet.from_strands(",
            "                f'e{i}', [Strand(t, v) for t, v in values.items()]",
            "            )",
            "            for i, values in enumerate(samples)",
            "        ]",
        ]

    # One cache-fingerprint contract per capability that has >=2 output groups
    # (the subset/superset cache semantics require two distinct groups).
    for cap in spec.capabilities:
        if len(cap.groups) < 2:
            lines += [
                "",
                "",
                f"# NOTE: capability {cap.id!r} has <2 output groups, so CacheFingerprintTests",
                "# (which exercise group subset/superset cache lookups) are not generated for it.",
            ]
            continue
        values_a = {k: f"sample-a-{k}" for k in cap.consumes}
        for golden_input in golden_by_cap.get(cap.id, [])[:1]:
            values_a.update(golden_input)
        values_b = {k: f"sample-b-{k}" for k in cap.consumes}
        lines += [
            "",
            "",
            f"class Test{_id_camel(cap.id)}CacheFingerprint(CacheFingerprintTests):",
            f"    capability = _MANIFEST.capability({cap.id!r})",
            f"    consumed_values_a = {values_a!r}",
            f"    consumed_values_b = {values_b!r}",
            f"    group_subset = {cap.groups[0].id!r}",
            f"    group_superset = {cap.groups[1].id!r}",
        ]

    return "\n".join(lines) + "\n"


def _implementation_md_source(spec: WeaverSpec) -> str:
    """Generate IMPLEMENTATION.md — the ordered worklist for finishing the weaver.

    The SDD ``tasks.md`` analog: it enumerates exactly which ``# TODO``s to fill,
    in which files, with the command that verifies each, ending at the
    ``verify --strict`` definition-of-done — so the agent doesn't re-derive the
    plan from the scattered code markers.
    """
    pkg = spec.package
    bulk = spec.bulk
    lines: list[str] = [
        f"# Implementing {pkg}",
        "",
        "Generated worklist — do these in order. Each step maps to `# TODO` markers in",
        "the code. **Definition of done:**",
        "",
        "```bash",
        "make test",
        f"weaverkit verify --spec weaver.spec.toml --package {pkg} --strict",
        "```",
        "",
        "Per-function contracts: [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).  ",
        "Common mistakes: [../../weaverkit/docs/PITFALLS.md](../../weaverkit/docs/PITFALLS.md).  ",
        "Worked example to copy: `../example_weaver/src/example_weaver/backends/local.py`.",
        "",
        "## 1. Implement the backend(s)",
        "",
    ]
    for b in spec.backends:
        is_bulk = bulk is not None and b == bulk.backend
        suffix = " (reads the bulk DB — see step 2 first)" if is_bulk else ""
        lines.append(
            f"- [ ] `src/{pkg}/backends/{b}.py` — fill `is_configured`, `fingerprint`, "
            f"and `fetch`{suffix} "
            "([#fingerprint](../../weaverkit/docs/implementing-backends.md#fingerprint), "
            "[#fetch](../../weaverkit/docs/implementing-backends.md#fetch))"
        )
    lines.append("")

    if bulk is not None:
        lines += [
            "## 2. Wire the bulk local DB",
            "",
            f"- [ ] `src/{pkg}/setup.py` — implement `_build` (download "
            f"`{bulk.archive_url}` + parse into the DB) and tighten `db_is_valid`. "
            "The generic plumbing (consent/lock/disk/atomic publish) is inherited from "
            "`braidworks.core.localdb`; you only fill those two.",
            f"- [ ] build it locally: `uv run {pkg}-ensure`",
            f"- [ ] add `build_{pkg}_fixture()` in `factory.py` returning a weaver on a "
            "*tiny deterministic* dataset, so `--strict` can run golden without the full "
            "download (see implementing-backends.md; taxon_weaver's `fixture.py` is the model)",
            "",
        ]

    next_n = 3 if bulk is not None else 2
    if not spec.golden:
        lines += [
            f"## {next_n}. Add golden examples",
            "",
            "- [ ] add at least one real `[[golden]]` (input -> expected) to "
            "`weaver.spec.toml`; `--strict` requires them",
            "",
        ]
        next_n += 1

    keyless_api = "api" in spec.backends and spec.api_key == "none"
    if keyless_api:
        lines += [
            f"## {next_n}. Keep the api tests offline (the fixture)",
            "",
            f"- [ ] fill `src/{pkg}/fixture.py` `_handler` with canned responses your "
            "`fetch` parses (an `httpx.MockTransport`, no network).",
            "- [ ] a keyless API is *always configured*, so once your `fetch` works the "
            "generated golden/order tests stop skipping and would hit the live service. "
            f"Point `tests/test_conformance.py`'s `build_weaver` and "
            f"`tests/test_contract.py`'s `make_weaver` at `build_{pkg}_fixture()` so they "
            "run offline (the manifest/fingerprint are identical to the live build).",
            "- [ ] fill `tests/test_e2e_live.py` with a known-truth example; run it with "
            "`make test-live` (`BRAIDWORKS_RUN_LIVE=1`) after api-touching changes.",
            "",
        ]
        next_n += 1

    lines += [
        f"## {next_n}. Verify (definition of done)",
        "",
        "- [ ] `make test` — conformance + contract + golden all green",
        f"- [ ] `weaverkit verify --spec weaver.spec.toml --package {pkg} --strict` "
        "— no placeholders left, golden runs",
        "- [ ] register the weaver where the app assembles its `WeaverFactory` (see README)",
        f"- [ ] after merge, tag the release `{pkg}-v{spec.version}` — `make tags` does this "
        "for every bumped package (CI also auto-tags on merge to main)",
        "",
    ]
    return "\n".join(lines)


def _contributing_md_source(spec: WeaverSpec) -> str:
    """Generate CONTRIBUTING.md — how to *extend/maintain* this weaver over time.

    Distinct from IMPLEMENTATION.md (the one-time "finish the stubs" worklist): this
    is the ongoing "how to add a trait / capability / backend" guide, spec-aware so
    it names this weaver's actual capabilities and the spec-driven loop. Authors fill
    the "Expansion notes" section with weaver-specific TODOs.
    """
    pkg = spec.package
    produced = sorted({o for c in spec.capabilities for o in c.produces})
    cap_list = ", ".join(f"`{c.id}`" for c in spec.capabilities)
    lines = [
        f"# Contributing to {pkg}",
        "",
        f"{spec.title}. Source: {spec.source_url} ({spec.license}). "
        f"Kind: `{spec.kind}`. Capabilities: {cap_list}.",
        "",
        "This weaver is **spec-driven**: `weaver.spec.toml` is the source of truth and",
        "`vocab.py` is generated from it — never hand-edit `vocab.py`. The repo-wide loop",
        "and boundaries are in [../../AGENTS.md](../../AGENTS.md); the spec field reference",
        "is in [../../weaverkit/README.md](../../weaverkit/README.md); per-backend contracts",
        "are in [../../weaverkit/docs/implementing-backends.md](../../weaverkit/docs/implementing-backends.md).",
        "",
        "After any change, re-verify:",
        "",
        "```bash",
        f"weaverkit verify --spec weaver.spec.toml --package {pkg} --strict",
        "```",
        "",
        "## Add an output to an existing capability",
        "",
        "1. Add the `type_id` to the relevant `[[capability.group]].outputs` in `weaver.spec.toml`",
        "   (or add a new group).",
        "2. If it's a new *leaf* output, catalog it in `weaverkit.keys.OUTPUT_KEYS`; if it's a",
        "   genuine *join key* others will consume, add it to `SHARED_KEYS` instead.",
        "3. Regenerate vocab: `weaverkit new --spec weaver.spec.toml --dest . --force`",
        "   (this only re-stamps generated files; your backend code is yours to edit).",
        "4. Map it in each backend's `fetch` (`record.values[<type_id>] = ...`).",
        "5. Add/adjust a `[[golden]]` example so the new output is verified.",
        "",
        "## Add a capability or a backend",
        "",
        "- **Capability:** add a `[[capability]]` block (consume a registered shared key),",
        "  regenerate, and handle it in `fetch` (branch on `capability_id` if needed).",
        "- **Backend:** add its name to `[weaver].backends`, regenerate, and implement the",
        "  new `src/" + pkg + "/backends/<name>.py` (`is_configured` / `fingerprint` / `fetch`).",
        "",
        "## Keep the fixture & golden honest",
        "",
        f"- Golden inputs must resolve in whatever `--strict` runs against (a `build_{pkg}_fixture()`",
        "  or a configured backend). When the source data changes, bump the backend `fingerprint`",
        "  and refresh the fixture/golden.",
        "",
        "## Current outputs",
        "",
        "This weaver currently produces: " + (", ".join(f"`{o}`" for o in produced) or "(none yet)") + ".",
        "",
        "## Expansion notes",
        "",
        "<!-- Weaver-specific notes: what's intentionally left out, what's easy to add next,",
        "     data quirks, columns not yet mapped, etc. Fill this in as you build. -->",
        "- TODO: record this weaver's specific expansion ideas and known limitations here.",
        "",
    ]
    return "\n".join(lines)


# --- string templates (rendered with {{TOKEN}} replacement) ------------------

_PYPROJECT = """\
[project]
name = "{{DBWEAVER}}"
version = "{{VERSION}}"
description = "{{TITLE}} — a Braidworks weaver."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [{{DEPS}}]

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.23", "weaverkit"]

# Registers this weaver for entry-point discovery (weaverkit view / references,
# arq workers, any registry-from-entry-points loader).
[project.entry-points."braidworks.weavers"]
{{WEAVER_ID}} = "{{DBWEAVER}}.factory:build_{{DBWEAVER}}"
{{SCRIPTS_BLOCK}}
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{DBWEAVER}}"]

[tool.uv.sources]
braidworks-core = { workspace = true }
weaverkit = { workspace = true }

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
"""

_README = """\
# {{DBWEAVER}}

{{TITLE}} weaver for Braidworks.

- **Source:** {{SOURCE_URL}}
- **License:** {{LICENSE}}
- **Cite:** {{CITATION}}

The contract lives in [`weaver.spec.toml`](weaver.spec.toml). The package structure
was generated by `weaverkit new`; the only places to implement are marked `# TODO`
in `src/{{DBWEAVER}}/backends/` (each backend's `fetch`, `fingerprint`, and the
`is_configured` flag). Each TODO links to the relevant section of
`weaverkit/docs/implementing-backends.md`, which has the full contract and an example.

Also add real **golden examples** to `weaver.spec.toml` (known input → expected
output); the conformance suite runs them once a backend is configured.

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import {{DBWEAVER}}

factory = WeaverFactory()
{{DBWEAVER}}.register(factory)        # makes "{{WEAVER_ID}}" buildable
```
"""

_MAKEFILE = """\
.PHONY: help test verify lint fmt
help:
\t@echo "test    - run conformance + golden tests"
\t@echo "verify  - check the weaver conforms to weaver.spec.toml"
\t@echo "lint    - ruff check"
\t@echo "fmt     - ruff format"

test:
\tuv run --extra test python -m pytest -q
{{LIVE_TARGET}}
verify:
\tuv run --extra test weaverkit verify --spec weaver.spec.toml --package {{DBWEAVER}}
{{ENSURE_TARGET}}
lint:
\tuv run ruff check .

fmt:
\tuv run ruff format .
"""

_INIT = '''\
"""{{DBWEAVER}} — {{TITLE}} weaver for Braidworks."""

from {{DBWEAVER}}.factory import build_{{DBWEAVER}}
from {{DBWEAVER}}.provider import {{CLASS}}WeaverProvider, register
from {{DBWEAVER}}.weaver import {{CLASS}}Weaver

__all__ = [
    "build_{{DBWEAVER}}",
    "register",
    "{{CLASS}}Weaver",
    "{{CLASS}}WeaverProvider",
]
'''





# Per-kind body of the backend stub's fetch TODO (spliced in as {{FETCH_HINT}}).
_FETCH_HINT_LOOKUP = """\
        #   - on a hit:   record.found=True, record.values={produced_type_id: value, ...}
        #                 (only keys this capability produces; the mapper filters
        #                  to the requested subset);
        #   - on a miss:  record.found=False (a normal data outcome, not an error);
        #   - on failure: record.error="..." (per-entity; do not raise for data
        #                 problems — failures are values)."""

_FETCH_HINT_RESOLVER = """\
        #   - resolved:   record.status=MatchStatus.RESOLVED, record.values={...};
        #   - fuzzy:      MatchStatus.FUZZY_UNIQUE + record.score (one low-confidence
        #                 guess; the mapper flags requires_review);
        #   - ambiguous:  MatchStatus.AMBIGUOUS + record.candidates=[Candidate(values=...,
        #                 score=...), ...] (no single answer);
        #   - miss:       MatchStatus.NO_MATCH;
        #   - failure:    MatchStatus.ERROR + record.error (per-entity; don't raise)."""

_BACKENDS_INIT = '''\
"""Backends — one per data source. Each normalizes into a {{RECORD_CLASS}}."""
'''


_BACKEND_STUB = '''\
"""The {{BACKEND}} backend for {{DBWEAVER}} — IMPLEMENT ME.

This is the novel ~20% the scaffold cannot write for you: the actual lookup
against the {{BACKEND}} source, normalized into ``{{RECORD_CLASS}}``s. Everything
else (manifest, dispatch, mapper) is generated and wired. Implement the three
``# TODO`` spots below; each links to the section of the guide with the full
contract and an example.

Guide: weaverkit/docs/implementing-backends.md
Worked example (copy this shape): weavers/example_weaver/src/example_weaver/backends/local.py
"""

from __future__ import annotations

from typing import Any

from braidworks.core import BackendBase
{{RECORD_IMPORT}}


class {{BACKEND_CLASS}}(BackendBase):
    """{{BACKEND}} backend. Not configured until you wire its data source."""

    name = "{{BACKEND}}"

    def __init__(self) -> None:
        # TODO(configured): set True once the data source is actually wired (DB
        # file opened / API key present). While False, the dispatch raises
        # BackendUnavailable and conformance golden tests skip this backend.
        # See: weaverkit/docs/implementing-backends.md#is_configured
        self._configured = False

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        # TODO(fingerprint): return a STABLE, version-specific string for the data
        # this backend serves — a release tag, dump date, or content checksum.
        # It is part of the cache key, so it must change when the data changes and
        # be identical for identical data. NEVER return "" or "unknown" (that
        # silently disables cache invalidation; conformance rejects it).
        # Spec's declared source of truth for the version: {{FINGERPRINT_SOURCE}}.
        # See: weaverkit/docs/implementing-backends.md#fingerprint
        return "{{DBWEAVER}}-{{BACKEND}}-TODO"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[{{RECORD_CLASS}}]:
        # TODO(fetch): look the inputs up in the {{BACKEND}} source and return one
        # {{RECORD_CLASS}} PER input query, IN THE SAME ORDER (the dispatch relies
        # on positional alignment — never drop, reorder, or merge).
        #   - each ``query`` is {consumed_type_id: value} for one entity;
{{FETCH_HINT}}
        # ``capability_id`` tells you which capability is running if the backend
        # serves more than one; ``requested_outputs`` lets you skip expensive
        # fields nobody asked for; ``groups_to_compute`` is the resolved set of
        # triggered group ids — gate expensive paths on membership in it.
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement {{BACKEND}} fetch for {{DBWEAVER}}")
'''

_BACKEND_STUB_BULK = '''\
"""The {{BACKEND}} backend for {{DBWEAVER}} — reads the bulk local DB. IMPLEMENT ME.

Auto-configures once the DB built by ``{{DBWEAVER}}-ensure`` exists at the default
cache path. Fill in ``fingerprint`` (read the version recorded at build time) and
``fetch`` (query the DB), normalizing each result into a ``{{RECORD_CLASS}}``.

Guide: weaverkit/docs/implementing-backends.md
Worked example (copy this shape): weavers/example_weaver/src/example_weaver/backends/local.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braidworks.core import BackendBase
{{RECORD_IMPORT}}
from {{DBWEAVER}}.setup import db_is_valid, default_db_path


class {{BACKEND_CLASS}}(BackendBase):
    """{{BACKEND}} backend over the bulk local DB built by ``{{DBWEAVER}}-ensure``."""

    name = "{{BACKEND}}"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._configured = db_is_valid(self._db_path)

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        # TODO(fingerprint): read the version recorded when the DB was built (e.g.
        # a metadata row) and return it. Never "" or "unknown".
        # Spec's declared source of truth: {{FINGERPRINT_SOURCE}}.
        # See: weaverkit/docs/implementing-backends.md#fingerprint
        return "{{DBWEAVER}}-{{BACKEND}}-TODO"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[{{RECORD_CLASS}}]:
        # TODO(fetch): open self._db_path and look up each query. Return one
        # {{RECORD_CLASS}} PER input query, IN THE SAME ORDER.
{{FETCH_HINT}}
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement {{BACKEND}} fetch for {{DBWEAVER}}")
'''

_BACKEND_STUB_API = '''\
"""The {{BACKEND}} backend for {{DBWEAVER}} — calls a remote API. IMPLEMENT ME.

This backend talks to a remote API that {{API_KEY_PHRASE}}. The key is read from
the ``{{API_KEY_ENV}}`` environment variable (or passed to ``__init__``); everything
else (manifest, dispatch, mapper) is generated and wired. Implement the three
``# TODO`` spots below; each links to the section of the guide with the full contract.

Guide: weaverkit/docs/implementing-backends.md
Worked example (copy this shape): weavers/example_weaver/src/example_weaver/backends/local.py
"""

from __future__ import annotations

import os
from typing import Any

from braidworks.core import BackendBase
{{RECORD_IMPORT}}

# Environment variable holding the API key for the {{BACKEND}} backend.
API_KEY_ENV = "{{API_KEY_ENV}}"


class {{BACKEND_CLASS}}(BackendBase):
    """{{BACKEND}} backend — calls the remote API ({{API_KEY_PHRASE}})."""

    name = "{{BACKEND}}"

    def __init__(self, api_key: str | None = None) -> None:
        # Key precedence: explicit arg > environment. Keep this cheap and
        # side-effect-free — it may be called just to decide routing.
        self._api_key = api_key or os.environ.get(API_KEY_ENV)

    def is_configured(self) -> bool:
        # {{API_KEY_CONFIGURED_COMMENT}}
        # See: weaverkit/docs/implementing-backends.md#is_configured
        return {{API_KEY_CONFIGURED_EXPR}}

    def fingerprint(self) -> str:
        # TODO(fingerprint): return a STABLE, version-specific string for this API's
        # data/contract. A live API with no version surface: name the contract, not
        # "live"-of-now, e.g. "{{DBWEAVER}}-{{BACKEND}}-v1". NEVER "" or "unknown".
        # Spec's declared source of truth for the version: {{FINGERPRINT_SOURCE}}.
        # See: weaverkit/docs/implementing-backends.md#fingerprint
        return "{{DBWEAVER}}-{{BACKEND}}-TODO"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[{{RECORD_CLASS}}]:
        # TODO(fetch): call the API for each input and return one {{RECORD_CLASS}}
        # PER input query, IN THE SAME ORDER (the dispatch relies on positional
        # alignment — never drop, reorder, or merge). Send the key with each request,
        # e.g. headers={"Authorization": f"Bearer {self._api_key}"} (use the scheme
        # the API expects). If results come back keyed by id, re-expand to input order.
{{FETCH_HINT}}
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement {{BACKEND}} fetch for {{DBWEAVER}}")
'''

_BACKEND_STUB_API_KEYLESS = '''\
"""The {{BACKEND}} backend for {{DBWEAVER}} — a keyless remote HTTP API. IMPLEMENT ME.

The API needs no key (api_key = "none"), so the backend is usable as-is. The HTTP
client is **injectable** (``client=``) so tests drive it with an ``httpx.MockTransport``
offline — see ``fixture.py`` / ``build_{{DBWEAVER}}_fixture``. Implement the three
``# TODO`` spots; everything else (manifest, dispatch, mapper) is generated.

> A keyless API is *always configured*, so once you flip ``_configured`` to True the
> generated golden/order tests stop skipping and would hit the live network. Point
> them at ``build_{{DBWEAVER}}_fixture()`` (see IMPLEMENTATION.md) to keep them offline.

Guide: weaverkit/docs/implementing-backends.md
Worked example: weavers/taxon_weaver/src/taxon_weaver/backends/datasets_v2.py
"""

from __future__ import annotations

from typing import Any

import httpx

from braidworks.core import BackendBase
{{RECORD_IMPORT}}

# Base URL of the {{BACKEND}} service.
BASE_URL = "{{SOURCE_URL}}"


class {{BACKEND_CLASS}}(BackendBase):
    """{{BACKEND}} backend — calls a keyless remote HTTP API."""

    name = "{{BACKEND}}"

    def __init__(
        self, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        # TODO(configured): a keyless API is usable as-is — return True for the real
        # backend. Left False so a fresh scaffold's golden/order tests SKIP until you
        # implement fetch; an injected client (the fixture) already counts as configured.
        self._configured = False

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    def _http(self) -> httpx.AsyncClient:
        """The HTTP client, lazily created if none was injected."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return self._client

    def fingerprint(self) -> str:
        # TODO(fingerprint): a STABLE id for this API's contract/version, e.g.
        # "{{DBWEAVER}}-{{BACKEND}}-v1". NEVER "" or "unknown" (conformance rejects it).
        # Spec's declared source of truth for the version: {{FINGERPRINT_SOURCE}}.
        # See: weaverkit/docs/implementing-backends.md#fingerprint
        return "{{DBWEAVER}}-{{BACKEND}}-TODO"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[{{RECORD_CLASS}}]:
        # TODO(fetch): call ``self._http()`` for each input and return one
        # {{RECORD_CLASS}} PER input query, IN THE SAME ORDER (the dispatch relies on
        # positional alignment — never drop, reorder, or merge).
{{FETCH_HINT}}
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement {{BACKEND}} fetch for {{DBWEAVER}}")
'''

_FIXTURE_API = '''\
"""A tiny, deterministic stand-in for the api backend — for offline tests.

A keyless API backend is *always configured*, so golden/order tests would hit the
live service. This module serves canned responses via ``httpx.MockTransport`` so
``build_{{DBWEAVER}}_fixture()`` (in factory.py) yields a weaver you can run offline
and reproducibly (the substrate for ``weaverkit verify --strict`` golden).

Fill ``_handler`` with the real request → canned-response shapes your fetch expects.
"""

from __future__ import annotations

import json

import httpx


def _handler(request: httpx.Request) -> httpx.Response:
    # TODO: match request.url.path and return canned JSON your fetch parses, e.g.
    #   if request.url.path.endswith("/lookup/ABC"):
    #       return httpx.Response(200, content=json.dumps({"...": "..."}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://{{DB}}.test", transport=httpx.MockTransport(_handler)
    )
'''

_TEST_E2E_API = '''\
"""Live end-to-end test for {{DBWEAVER}} against the real {{FIRST_BACKEND}} API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from {{DBWEAVER}} import build_{{DBWEAVER}}

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def test_live_known_example():
    weaver = build_{{DBWEAVER}}()
    # TODO: a real consumed input that resolves against the live API.
    ss = StrandSet.from_strands("e1", [Strand({{CONSUMED_REPR}}, "TODO-real-input")])
    result = (
        await weaver.execute_batch(
            {{FIRST_CAP_REPR}},
            [ss],
            requested_outputs=frozenset({{{MINIMAL_OUTPUT_REPR}}}),
            backend={{FIRST_BACKEND_REPR}},
        )
    )[0]
    # TODO: assert known-truth outputs (or NO_MATCH for a deliberately-absent input).
    assert result.status in (WeaveStatus.OK, WeaveStatus.NO_MATCH)
'''

_SETUP = '''\
"""Local DB setup for {{DBWEAVER}} — fetch/build the bulk source into the user cache.

The {{BULK_BACKEND}} backend reads a large local DB built from the source archive.
It is multi-GB and must not be committed; ``ensure_{{DB}}_db`` downloads and builds
it into the per-user cache on first use. The generic plumbing — consent gate,
download, MD5 check, disk precheck, cross-process lock, and atomic publish — lives
in ``braidworks.core.localdb``; you implement only the two domain TODOs below
(``db_is_valid`` and ``_build``). Model on taxon_weaver's ``setup.py``.

See: weaverkit/docs/implementing-backends.md#bulk-file-sources-setuppy
"""

from __future__ import annotations

from pathlib import Path

from braidworks.core.localdb import default_db_path as _default_db_path
from braidworks.core.localdb import ensure_local_db

_NAMESPACE = "{{DB}}"
_DB_FILENAME = "{{BULK_FILENAME}}"
ARCHIVE_URL = "{{ARCHIVE_URL}}"


def default_db_path() -> Path:
    """Per-user default DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _default_db_path(_NAMESPACE, _DB_FILENAME)


def db_is_valid(path: Path) -> bool:
    """Whether ``path`` is a usable built DB."""
    # TODO: tighten this — check the expected tables/metadata exist, not just the file.
    return path.exists() and path.stat().st_size > 0


def _consent_message(db_path: Path) -> str:
    return (
        f"{{DBWEAVER}}'s local DB is not present at {db_path}.\\n"
        f"Build it from {ARCHIVE_URL} by running `{{DBWEAVER}}-ensure`, or pass "
        "auto=True / set BRAIDWORKS_AUTO_DOWNLOAD=1 to allow automatic download."
    )


def _build(target: Path) -> None:
    """Download ARCHIVE_URL and build the DB at ``target``. IMPLEMENT ME.

    ``ensure_local_db`` calls this inside a temp dir on the DB's filesystem and
    publishes ``target`` atomically only if ``db_is_valid(target)`` — so just build
    into ``target``; don't worry about locking or atomic rename.
    """
    # TODO: build the DB into ``target``. Typically:
    #   from braidworks.core.localdb import download, md5_file, fetch_remote_md5
    #   archive = target.parent / "source.archive"
    #   download(ARCHIVE_URL, archive)          # stream + progress
    #   ... verify, parse the archive, and write the DB to ``target`` ...
    # Record the source version so the backend's fingerprint() can read it back.
    raise NotImplementedError("TODO: build the {{DBWEAVER}} DB from " + ARCHIVE_URL)


def ensure_{{DB}}_db(
    target: str | Path | None = None, *, auto: bool = False, refresh: bool = False
) -> Path:
    """Ensure the local DB exists (default cache path), building it if needed.

    Delegates orchestration (consent, lock, disk precheck, atomic publish) to
    ``braidworks.core.localdb.ensure_local_db``; this module supplies only the
    domain pieces (``db_is_valid`` / ``_build`` / the consent message).
    """
    db_path = Path(target) if target is not None else default_db_path()
    return ensure_local_db(
        db_path,
        is_valid=db_is_valid,
        build=_build,
        consent_message=_consent_message(db_path),
        auto=auto,
        refresh=refresh,
    )
'''

_ENSURE_CLI = '''\
"""``{{DBWEAVER}}-ensure`` — build/refresh the local {{DBWEAVER}} DB in the user cache."""

from __future__ import annotations

import argparse

from {{DBWEAVER}}.setup import default_db_path, ensure_{{DB}}_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="{{DBWEAVER}}-ensure", description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="rebuild even if present")
    args = parser.parse_args(argv)
    target = default_db_path()
    print(f"ensuring {{DBWEAVER}} DB at {target} ...")
    # Running ensure is itself consent to download/build.
    path = ensure_{{DB}}_db(target, auto=True, refresh=args.refresh)
    print(f"ready: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
'''


_WEAVER = '''\
"""{{CLASS}}Weaver — the concrete Braidworks weaver for {{TITLE}}.

The routing/batching/mapping runtime is shared: this subclasses core's
``BackendDispatchWeaver`` and only declares its MANIFEST (from the generated vocab)
and which shared mapper to use (``{{MAPPER}}``). The novel work is in the backends.
"""

from __future__ import annotations

from braidworks.core import BackendBase, BackendDispatchWeaver, WeaverManifest, {{MAPPER}}

from {{DBWEAVER}} import vocab


class {{CLASS}}Weaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    MAPPER = staticmethod({{MAPPER}})

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(
            backends=tuple(sorted(backends))
        )
'''

_FACTORY = '''\
"""Builders for {{DBWEAVER}} — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_{{DBWEAVER}}()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. It wires every declared backend present (possibly
  unconfigured), so the manifest is complete and fingerprint/golden checks can run.
  It never raises for missing data.
- a CONFIGURED builder (you write it, usually domain-named) — takes real config
  (db paths, API keys, injected clients) and may raise if nothing is usable. See
  ``taxon_weaver``'s ``build_ncbi_weaver`` for a worked example; a commented
  skeleton is at the bottom of this file.
"""

from __future__ import annotations

from typing import Any

from braidworks.core import BaseWeaver

{{BACKEND_IMPORTS}}
from {{DBWEAVER}}.weaver import {{CLASS}}Weaver


def build_{{DBWEAVER}}(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    Wires every declared backend present-but-possibly-unconfigured. For real use,
    add a configured builder (see the module docstring / the commented skeletons).
    """
    backends = {
{{BACKEND_WIRING}}
    }
    return {{CLASS}}Weaver(backends)

{{FIXTURE_BUILDER}}
# --- Optional builders (uncomment + fill in for real use) -----------------------
#
# A CONFIGURED builder — takes real config and raises if nothing is usable:
#
# from braidworks.core import BackendConfigurationError
#
# def build_{{DBWEAVER}}_configured(**config: Any) -> BaseWeaver:
#     backends = {}
#     # ... wire backends from real config (paths / keys / clients) ...
#     if not backends:
#         raise BackendConfigurationError("configure at least one backend")
#     return {{CLASS}}Weaver(backends)
{{FIXTURE_SKELETON}}'''

_PROVIDER = '''\
"""{{CLASS}}WeaverProvider — the Layer 1 conformance wrapper, plus registration.

A weaver only becomes reachable to the braider once its provider is registered in
the application's ``WeaverFactory``. ``register(factory)`` is the one-liner that
does it; call it from wherever you assemble the factory (see the README).
"""

from __future__ import annotations

from typing import Any, Mapping

from braidworks.core import BaseWeaver, WeaverFactory

from {{DBWEAVER}} import vocab
from {{DBWEAVER}}.factory import build_{{DBWEAVER}}


class {{CLASS}}WeaverProvider:
    """WeaverProvider (Layer 1); delegates to build_{{DBWEAVER}}."""

    weaver_id = vocab.WEAVER_ID

    def build(self, config: Mapping[str, Any]) -> BaseWeaver:
        return build_{{DBWEAVER}}(**dict(config))


def register(factory: WeaverFactory) -> None:
    """Register this weaver's provider so the braider can build "{{WEAVER_ID}}"."""
    factory.register({{CLASS}}WeaverProvider())
'''

_TEST_CONFORMANCE = '''\
"""Conformance tests for {{DBWEAVER}} — the weaver must match its spec.

This wires up weaverkit's WeaverConformanceTests, which checks the manifest,
reachability, and fingerprints, and runs the spec's golden examples (skipping when
the backend is not configured). Do not weaken these — they are the contract.
"""

from __future__ import annotations

from pathlib import Path

from weaverkit import WeaverConformanceTests

from {{DBWEAVER}} import factory

SPEC = str(Path(__file__).resolve().parent.parent / "weaver.spec.toml")


class TestConformance(WeaverConformanceTests):
    spec_path = SPEC
    golden_backend = "{{FIRST_BACKEND}}"

    def build_weaver(self):
        # Prefer the offline fixture builder so golden examples run in CI; fall
        # back to the zero-config introspection builder when no fixture exists.
        builder = getattr(factory, "build_{{DBWEAVER}}_fixture", None) or factory.build_{{DBWEAVER}}
        return builder()
'''


def _render(template: str, tokens: dict[str, str]) -> str:
    out = template
    for key, value in tokens.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def _ruff_format(paths: list[Path]) -> None:
    """Best-effort ``ruff format`` of generated files; silently skip if absent.

    The generator emits readable-but-not-perfectly-wrapped code; letting ruff do
    the final wrapping/quoting means a fresh scaffold is already format-clean,
    without the templates having to predict ruff's line breaks.
    """
    argvs = [[sys.executable, "-m", "ruff", "format", "-q"]]
    ruff = shutil.which("ruff")
    if ruff:
        argvs.append([ruff, "format", "-q"])
    for argv in argvs:
        try:
            subprocess.run(
                [*argv, *(str(p) for p in paths)],
                check=True,
                capture_output=True,
            )
            return
        except (OSError, subprocess.CalledProcessError):
            continue


def scaffold(
    spec: WeaverSpec,
    dest: Path | str,
    *,
    spec_toml: str,
    force: bool = False,
    format_output: bool = True,
) -> list[Path]:
    """Generate a full weaver package for ``spec`` under ``dest``. Returns files written.

    ``spec_toml`` is the raw text of the spec, copied verbatim into the package as
    ``weaver.spec.toml`` (the contract travels with the code). Set ``force`` to
    overwrite an existing destination. ``format_output`` runs a best-effort
    ``ruff format`` over the result so it is lint/format-clean from the start.
    """
    dest = Path(dest)
    pkg = spec.package
    cls = _camel(spec.db_name)
    first_backend = spec.backends[0]

    if dest.exists() and any(dest.iterdir()) and not force:
        raise ScaffoldError(f"{dest} already exists and is not empty (use force=True)")

    tokens = {
        "DBWEAVER": pkg,
        "CLASS": cls,
        "WEAVER_ID": spec.resolved_weaver_id,
        "TITLE": spec.title,
        "VERSION": spec.version,
        "LICENSE": spec.license,
        "CITATION": spec.citation or "(none — see source)",
        "SOURCE_URL": spec.source_url,
        "FINGERPRINT_SOURCE": spec.fingerprint_source,
        "FIRST_BACKEND": first_backend,
        "DB": spec.db_name,
    }

    # The records/mapper/dispatch/backend-ABC runtime is shared from braidworks-core;
    # only the per-kind names + imports are stamped into the thin generated glue.
    is_resolver = spec.kind == "resolver"
    fetch_hint = _FETCH_HINT_RESOLVER if is_resolver else _FETCH_HINT_LOOKUP
    tokens["MAPPER"] = "map_resolver" if is_resolver else "map_lookup"
    tokens["RECORD_CLASS"] = "ResolverRecord" if is_resolver else "LookupRecord"
    tokens["RECORD_IMPORT"] = (
        "from braidworks.core import Candidate, MatchStatus, ResolverRecord"
        if is_resolver
        else "from braidworks.core import LookupRecord"
    )

    # Dependencies: always braidworks-core; an api backend's fetch will make HTTP
    # calls, so declare httpx up front (the workspace already uses it) rather than
    # making every api-weaver author add it by hand.
    has_api = "api" in spec.backends
    deps = ['"braidworks-core"']
    if has_api:
        deps.append('"httpx>=0.27"')
    tokens["DEPS"] = ", ".join(deps)

    # A keyless HTTP API backend (named "api", api_key="none") is always configured,
    # so it gets an http-aware injectable stub + an offline fixture so tests don't hit
    # the live service. Keyed APIs (optional/required) skip in CI when unconfigured.
    bulk_is_api = spec.bulk is not None and spec.bulk.backend == "api"
    keyless_api = has_api and not _backend_needs_key(spec, "api") and not bulk_is_api

    # Bulk-source tokens: a local DB built from a download (setup.py + ensure CLI).
    bulk = spec.bulk
    if bulk is not None:
        tokens["SCRIPTS_BLOCK"] = f'[project.scripts]\n{pkg}-ensure = "{pkg}.ensure:main"\n'
        tokens["ENSURE_TARGET"] = "\nensure:\n\tuv run {pkg}-ensure\n".replace("{pkg}", pkg)
        tokens["ARCHIVE_URL"] = bulk.archive_url
        tokens["BULK_FILENAME"] = bulk.filename
        tokens["BULK_BACKEND"] = bulk.backend
    else:
        tokens["SCRIPTS_BLOCK"] = ""
        tokens["ENSURE_TARGET"] = ""

    # Live-E2E Makefile target — only when there's an api backend to test live.
    tokens["LIVE_TARGET"] = (
        "\ntest-live:\n"
        "\tBRAIDWORKS_RUN_LIVE=1 uv run --extra test python -m pytest tests/test_e2e_live.py -v\n"
        if has_api
        else ""
    )
    # Tokens for the generated live-E2E stub (first capability's shapes).
    _e2e_cap = spec.capabilities[0]
    tokens["CONSUMED_REPR"] = repr(sorted(_e2e_cap.consumes)[0])
    tokens["FIRST_CAP_REPR"] = repr(_e2e_cap.id)
    tokens["MINIMAL_OUTPUT_REPR"] = repr(sorted(_e2e_cap.produces)[0])
    tokens["FIRST_BACKEND_REPR"] = repr(first_backend)

    backend_imports = "\n".join(
        f"from {pkg}.backends.{b} import {cls}{_camel(b)}Backend" for b in spec.backends
    )
    backend_wiring = "\n".join(f'        "{b}": {cls}{_camel(b)}Backend(),' for b in spec.backends)
    # For a keyless api weaver, emit a real (uncommented) fixture builder wired to the
    # MockTransport client from fixture.py — the offline substrate for --strict golden.
    # Otherwise leave a commented skeleton so the author can add one (e.g. a bulk DB).
    if keyless_api:
        fixture_builder = (
            f"def build_{pkg}_fixture() -> BaseWeaver:\n"
            f'    """Fixture-backed weaver for ``verify --strict`` — canned API, no network.\n\n'
            f"    The keyless api backend is always configured, so without this golden would\n"
            f"    hit the live service. Wires the api backend to an ``httpx.MockTransport``\n"
            f"    (see ``fixture.py`` — fill in its canned responses).\n"
            f'    """\n'
            f"    from {pkg}.fixture import mock_client\n\n"
            f'    return {cls}Weaver({{"api": {cls}ApiBackend(client=mock_client())}})\n'
        )
        fixture_skeleton = ""
    else:
        fixture_builder = ""
        fixture_skeleton = (
            "#\n"
            "# A FIXTURE builder — only if no backend reads bundled/committed data; lets\n"
            "# `weaverkit verify --strict` run golden against a tiny deterministic dataset\n"
            f"# (see decisions.md E and taxon_weaver's build_{pkg}_fixture):\n"
            "#\n"
            f"# def build_{pkg}_fixture() -> BaseWeaver:\n"
            "#     ...  # return a weaver wired against a small synthesized/committed dataset\n"
        )
    factory_tokens = {
        **tokens,
        "BACKEND_IMPORTS": backend_imports,
        "BACKEND_WIRING": backend_wiring,
        "FIXTURE_BUILDER": fixture_builder,
        "FIXTURE_SKELETON": fixture_skeleton,
    }

    src = dest / "src" / pkg
    files: dict[Path, str] = {
        dest / "pyproject.toml": _render(_PYPROJECT, tokens),
        dest / "README.md": _render(_README, tokens),
        dest / "IMPLEMENTATION.md": _implementation_md_source(spec),
        dest / "CONTRIBUTING.md": _contributing_md_source(spec),
        dest / "Makefile": _render(_MAKEFILE, tokens),
        dest / "weaver.spec.toml": spec_toml,
        src / "__init__.py": _render(_INIT, tokens),
        src / "vocab.py": _vocab_source(spec),
        src / "weaver.py": _render(_WEAVER, tokens),
        src / "factory.py": _render(_FACTORY, factory_tokens),
        src / "provider.py": _render(_PROVIDER, tokens),
        src / "backends" / "__init__.py": _render(_BACKENDS_INIT, tokens),
        dest / "tests" / "test_conformance.py": _render(_TEST_CONFORMANCE, tokens),
        dest / "tests" / "test_contract.py": _contract_test_source(spec),
    }

    # api weavers get a gated live-E2E stub; keyless api weavers also get an offline
    # MockTransport fixture (build_<pkg>_fixture wires it in factory.py).
    if has_api:
        files[dest / "tests" / "test_e2e_live.py"] = _render(_TEST_E2E_API, tokens)
    if keyless_api:
        files[src / "fixture.py"] = _render(_FIXTURE_API, tokens)

    if bulk is not None:
        files[src / "setup.py"] = _render(_SETUP, tokens)
        files[src / "ensure.py"] = _render(_ENSURE_CLI, tokens)

    api_key_env = f"{spec.db_name.upper()}_API_KEY"
    for b in spec.backends:
        bt = {
            **tokens,
            "BACKEND": b,
            "BACKEND_CLASS": f"{cls}{_camel(b)}Backend",
            "FETCH_HINT": fetch_hint,
        }
        is_bulk = bulk is not None and b == bulk.backend
        if is_bulk:
            stub = _BACKEND_STUB_BULK
        elif _backend_needs_key(spec, b):
            stub = _BACKEND_STUB_API
            bt.update(_api_key_tokens(spec.api_key, api_key_env))
        elif b == "api":
            # Keyless HTTP API ("api" backend, api_key="none"): an http-aware,
            # injectable stub (so the offline fixture can drive it).
            stub = _BACKEND_STUB_API_KEYLESS
        else:
            stub = _BACKEND_STUB
        files[src / "backends" / f"{b}.py"] = _render(stub, bt)

    written: list[Path] = []
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if content.endswith("\n") else content + "\n")
        written.append(path)

    if format_output:
        py_files = [p for p in written if p.suffix == ".py"]
        if py_files:
            _ruff_format(py_files)

    return sorted(written)
