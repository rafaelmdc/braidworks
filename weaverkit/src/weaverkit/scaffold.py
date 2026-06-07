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
        "from braidworks.core import Capability, OutputGroup, WeaverManifest",
        "",
        f"WEAVER_ID = {spec.resolved_weaver_id!r}",
        f"WEAVER_VERSION = {spec.version!r}",
        "",
        "",
        "def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:",
        '    """Declare every capability for the wired-in backends."""',
        "    return WeaverManifest(",
        "        weaver_id=WEAVER_ID,",
        "        version=WEAVER_VERSION,",
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
        f"from {pkg} import vocab",
        f"from {pkg}.factory import build_{pkg}",
        "",
        f"_MANIFEST = vocab.build_manifest(backends={backends_repr})",
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
            f"        weaver = build_{pkg}()",
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


# --- string templates (rendered with {{TOKEN}} replacement) ------------------

_PYPROJECT = """\
[project]
name = "{{DBWEAVER}}"
version = "{{VERSION}}"
description = "{{TITLE}} — a Braidworks weaver."
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["braidworks-core"]

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.23", "weaverkit"]

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

verify:
\tuv run --extra test weaverkit verify --spec weaver.spec.toml --package {{DBWEAVER}}

lint:
\tuv run ruff check .

fmt:
\tuv run ruff format .
"""

_INIT = '''\
"""{{DBWEAVER}} — {{TITLE}} weaver for Braidworks."""

from {{DBWEAVER}}.factory import build_{{DBWEAVER}}
from {{DBWEAVER}}.intermediate import {{CLASS}}Record
from {{DBWEAVER}}.provider import {{CLASS}}WeaverProvider, register
from {{DBWEAVER}}.weaver import {{CLASS}}Weaver

__all__ = [
    "build_{{DBWEAVER}}",
    "register",
    "{{CLASS}}Record",
    "{{CLASS}}Weaver",
    "{{CLASS}}WeaverProvider",
]
'''

_INTERMEDIATE = '''\
"""Neutral record every backend normalizes into before the single mapper runs.

Keeping one intermediate is what guarantees every backend emits identical strand
shapes. ``values`` maps a produced ``type_id`` to its value; the mapper only emits
the externally-requested subset. This type is weaver-specific — never leak it into
``braidworks-core``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class {{CLASS}}Record:
    """One backend's resolution of one input. Backend-neutral."""

    query: dict[str, Any]
    found: bool = False
    values: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
'''

_MAPPER = '''\
"""The single ``{{CLASS}}Record -> WeaveResult`` mapper.

Every backend feeds results through this one function, so all backends emit
identical strand shapes. It emits exactly the externally-requested outputs and
reports ``computed_groups`` as the groups actually triggered.
"""

from __future__ import annotations

from braidworks.core import Capability, Strand, WeaveResult, WeaveStatus

from {{DBWEAVER}}.intermediate import {{CLASS}}Record


def map_record(
    record: {{CLASS}}Record,
    *,
    capability: Capability,
    requested_outputs: frozenset[str],
    backend: str,
    weaver_version: str,
) -> WeaveResult:
    """Map a neutral record to a ``WeaveResult`` for the requested outputs."""
    computed_groups = capability.triggered_groups(requested_outputs)
    allowed = capability.outputs_to_compute(requested_outputs)
    provenance = (f"{{WEAVER_ID}}:{backend}",)

    strands: list[Strand] = []
    errors: tuple[str, ...] = ()

    if record.error is not None:
        status = WeaveStatus.ERROR
        errors = (record.error,)
    elif not record.found:
        status = WeaveStatus.NO_MATCH
    else:
        status = WeaveStatus.OK
        for type_id, value in record.values.items():
            if type_id in allowed and value is not None:
                strands.append(Strand(type_id, value, provenance=provenance))

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=computed_groups,
        status=status,
        strands=tuple(strands),
        errors=errors,
    )
'''

_BACKENDS_INIT = '''\
"""Backends — one per data source. Each normalizes into a {{CLASS}}Record."""
'''

_BACKEND_BASE = '''\
"""{{CLASS}}Backend — the domain backend interface for this weaver.

Implements core's generic ``BackendStrategy`` (``name`` / ``is_configured`` /
``fingerprint``) and adds one operation: fetch a batch of consumed inputs into
``{{CLASS}}Record`` objects, in input order. The dispatch weaver calls this; core
never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from {{DBWEAVER}}.intermediate import {{CLASS}}Record


class {{CLASS}}Backend(ABC):
    """A `BackendStrategy` plus a batch `fetch` operation."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this backend is usable here (else the dispatch raises BackendUnavailable)."""

    @abstractmethod
    def fingerprint(self) -> str:
        """Per-backend data-state fingerprint for the cache key. Never ``"unknown"``."""

    @abstractmethod
    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
    ) -> list[{{CLASS}}Record]:
        """Resolve consumed inputs into records — exactly one per input, in order."""
'''

_BACKEND_STUB = '''\
"""The {{BACKEND}} backend for {{DBWEAVER}} — IMPLEMENT ME.

This is the novel ~20% the scaffold cannot write for you: the actual lookup
against the {{BACKEND}} source, normalized into ``{{CLASS}}Record``s. Everything
else (manifest, dispatch, mapper) is generated and wired. Implement the three
``# TODO`` spots below; each links to the section of the guide with the full
contract and an example.

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

from typing import Any

from {{DBWEAVER}}.backends.base import {{CLASS}}Backend
from {{DBWEAVER}}.intermediate import {{CLASS}}Record


class {{BACKEND_CLASS}}({{CLASS}}Backend):
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
    ) -> list[{{CLASS}}Record]:
        # TODO(fetch): look the inputs up in the {{BACKEND}} source and return one
        # {{CLASS}}Record PER input query, IN THE SAME ORDER (the dispatch relies
        # on positional alignment — never drop, reorder, or merge).
        #   - each ``query`` is {consumed_type_id: value} for one entity;
        #   - on a hit:   record.found=True, record.values={produced_type_id: value, ...}
        #                 (only keys this capability produces; the mapper filters
        #                  to the requested subset);
        #   - on a miss:  record.found=False (a normal data outcome, not an error);
        #   - on failure: record.error="..." (per-entity; do not raise for data
        #                 problems — failures are values).
        # ``capability_id`` tells you which capability is running if the backend
        # serves more than one; ``requested_outputs`` lets you skip expensive
        # fields nobody asked for.
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement {{BACKEND}} fetch for {{DBWEAVER}}")
'''

_DISPATCH = '''\
"""BackendDispatchWeaver — routes a capability to a named backend, then maps.

Generated boilerplate; you should not need to edit this. It pulls each consumed
input off the StrandSet, hands the batch to the selected backend's ``fetch``, and
runs the single shared mapper over the results.
"""

from __future__ import annotations

from typing import Any

from braidworks.core import (
    BackendUnavailable,
    BaseWeaver,
    UnsupportedCapability,
    WeaveResult,
)

from {{DBWEAVER}}.backends.base import {{CLASS}}Backend
from {{DBWEAVER}}.mapper import map_record


class BackendDispatchWeaver(BaseWeaver):
    """Routes each capability call to a named backend, then runs the shared mapper."""

    def __init__(self, backends: dict[str, {{CLASS}}Backend]) -> None:
        self._backends = dict(backends)

    def _strategy(self, backend: str) -> {{CLASS}}Backend:
        strat = self._backends.get(backend)
        if strat is None or not strat.is_configured():
            raise BackendUnavailable(
                f"backend {backend!r} is not configured for {self.MANIFEST.weaver_id!r}"
            )
        return strat

    def backend_fingerprint(self, backend: str) -> str:
        strat = self._backends.get(backend)
        return strat.fingerprint() if strat is not None else f"unconfigured:{backend}"

    async def execute(
        self, capability_id, strand_set, *, requested_outputs, backend
    ) -> WeaveResult:
        results = await self.execute_batch(
            capability_id, [strand_set], requested_outputs=requested_outputs, backend=backend
        )
        return results[0]

    async def execute_batch(
        self, capability_id, strand_sets, *, requested_outputs, backend
    ) -> list[WeaveResult]:
        cap = self.MANIFEST.capability(capability_id)
        if cap is None:
            raise UnsupportedCapability(
                f"{self.MANIFEST.weaver_id!r} has no capability {capability_id!r}"
            )
        strategy = self._strategy(backend)  # raises BackendUnavailable
        consumed = tuple(sorted(cap.consumes))
        queries: list[dict[str, Any]] = [
            {t: (ss.get(t).value if ss.get(t) is not None else None) for t in consumed}
            for ss in strand_sets
        ]
        records = await strategy.fetch(
            capability_id, queries, requested_outputs=requested_outputs
        )
        return [
            map_record(
                r,
                capability=cap,
                requested_outputs=requested_outputs,
                backend=backend,
                weaver_version=self.MANIFEST.version,
            )
            for r in records
        ]
'''

_WEAVER = '''\
"""{{CLASS}}Weaver — the concrete Braidworks weaver for {{TITLE}}."""

from __future__ import annotations

from braidworks.core import WeaverManifest

from {{DBWEAVER}} import vocab
from {{DBWEAVER}}.backends.base import {{CLASS}}Backend
from {{DBWEAVER}}.dispatch import BackendDispatchWeaver


class {{CLASS}}Weaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    def __init__(self, backends: dict[str, {{CLASS}}Backend]) -> None:
        if not backends:
            raise ValueError("{{CLASS}}Weaver requires at least one backend")
        super().__init__(backends)
        self.MANIFEST: WeaverManifest = vocab.build_manifest(
            backends=tuple(sorted(backends))
        )
'''

_FACTORY = '''\
"""build_{{DBWEAVER}} — the Layer 2 builder (only this package knows its backends)."""

from __future__ import annotations

from typing import Any

from braidworks.core import BaseWeaver

{{BACKEND_IMPORTS}}
from {{DBWEAVER}}.weaver import {{CLASS}}Weaver


def build_{{DBWEAVER}}(**config: Any) -> BaseWeaver:
    """Construct a configured {{CLASS}}Weaver with every declared backend wired in."""
    backends = {
{{BACKEND_WIRING}}
    }
    return {{CLASS}}Weaver(backends)
'''

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

from {{DBWEAVER}}.factory import build_{{DBWEAVER}}

SPEC = str(Path(__file__).resolve().parent.parent / "weaver.spec.toml")


class TestConformance(WeaverConformanceTests):
    spec_path = SPEC
    golden_backend = "{{FIRST_BACKEND}}"

    def build_weaver(self):
        return build_{{DBWEAVER}}()
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
        "SOURCE_URL": spec.source_url,
        "FINGERPRINT_SOURCE": spec.fingerprint_source,
        "FIRST_BACKEND": first_backend,
    }

    backend_imports = "\n".join(
        f"from {pkg}.backends.{b} import {cls}{_camel(b)}Backend" for b in spec.backends
    )
    backend_wiring = "\n".join(f'        "{b}": {cls}{_camel(b)}Backend(),' for b in spec.backends)
    factory_tokens = {
        **tokens,
        "BACKEND_IMPORTS": backend_imports,
        "BACKEND_WIRING": backend_wiring,
    }

    src = dest / "src" / pkg
    files: dict[Path, str] = {
        dest / "pyproject.toml": _render(_PYPROJECT, tokens),
        dest / "README.md": _render(_README, tokens),
        dest / "Makefile": _render(_MAKEFILE, tokens),
        dest / "weaver.spec.toml": spec_toml,
        src / "__init__.py": _render(_INIT, tokens),
        src / "vocab.py": _vocab_source(spec),
        src / "intermediate.py": _render(_INTERMEDIATE, tokens),
        src / "mapper.py": _render(_MAPPER, tokens),
        src / "dispatch.py": _render(_DISPATCH, tokens),
        src / "weaver.py": _render(_WEAVER, tokens),
        src / "factory.py": _render(_FACTORY, factory_tokens),
        src / "provider.py": _render(_PROVIDER, tokens),
        src / "backends" / "__init__.py": _render(_BACKENDS_INIT, tokens),
        src / "backends" / "base.py": _render(_BACKEND_BASE, tokens),
        dest / "tests" / "test_conformance.py": _render(_TEST_CONFORMANCE, tokens),
        dest / "tests" / "test_contract.py": _contract_test_source(spec),
    }

    for b in spec.backends:
        bt = {**tokens, "BACKEND": b, "BACKEND_CLASS": f"{cls}{_camel(b)}Backend"}
        files[src / "backends" / f"{b}.py"] = _render(_BACKEND_STUB, bt)

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
