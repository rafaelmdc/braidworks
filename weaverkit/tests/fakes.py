"""Fake weavers for conformance tests.

A conforming fake (matches ``valid.weaver.spec.toml``) and helpers to derail it,
so each conformance check can be shown to fire on the corresponding defect.
"""

from __future__ import annotations

from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

# Mirrors tests/fixtures/valid.weaver.spec.toml exactly.
_CONFORMING_MANIFEST = WeaverManifest(
    weaver_id="madin",
    version="0.1.0",
    capabilities=(
        Capability(
            id="resolve_traits",
            consumes=frozenset({"ncbi.taxon.id"}),
            produces=frozenset(
                {
                    "microbe.trait.metabolism",
                    "microbe.trait.gram_stain",
                    "microbe.trait.optimum_temp",
                }
            ),
            output_groups=(
                OutputGroup(
                    id="traits.core",
                    outputs=frozenset({"microbe.trait.metabolism", "microbe.trait.gram_stain"}),
                ),
                OutputGroup(
                    id="traits.growth",
                    outputs=frozenset({"microbe.trait.optimum_temp"}),
                ),
            ),
            backends=("local",),
        ),
    ),
)


class ConformingFakeWeaver(BaseWeaver):
    """A weaver whose manifest matches the valid fixture and that answers golden."""

    MANIFEST = _CONFORMING_MANIFEST

    def backend_fingerprint(self, backend: str) -> str:
        return f"madin-fake-{backend}-v1"

    async def execute(
        self,
        capability_id: str,
        strand_set: StrandSet,
        *,
        requested_outputs: frozenset[str],
        backend: str,
    ) -> WeaveResult:
        # Golden: ncbi.taxon.id 562 -> gram_stain negative.
        taxid = strand_set.get("ncbi.taxon.id")
        strands: tuple[Strand, ...] = ()
        if taxid is not None and str(taxid.value) == "562":
            strands = (Strand(type_id="microbe.trait.gram_stain", value="negative"),)
        return WeaveResult(
            capability_id=capability_id,
            weaver_version=self.MANIFEST.version,
            backend_used=backend,
            computed_groups=frozenset({"traits.core"}),
            status=WeaveStatus.OK if strands else WeaveStatus.NO_MATCH,
            strands=strands,
        )


class UnknownFingerprintWeaver(ConformingFakeWeaver):
    """Conforming manifest but returns the forbidden 'unknown' fingerprint."""

    def backend_fingerprint(self, backend: str) -> str:
        return "unknown"
