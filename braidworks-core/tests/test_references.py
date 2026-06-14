"""Automatic references: braid + registry -> deduped, license-driven bibliography."""

from __future__ import annotations

from braidworks.core import (
    Braid,
    BraidRegistry,
    CapabilityInvocation,
    Provenance,
    Reference,
    WeaverManifest,
    format_references,
    references_for,
    references_for_braid,
)
from helpers import FakeWeaver, simple_capability


def _registry() -> BraidRegistry:
    reg = BraidRegistry()
    reg.register(
        FakeWeaver(
            WeaverManifest(
                weaver_id="uniprot",
                version="0.1.1",
                capabilities=(simple_capability("c", {"protein.query"}, {"protein.uniprot.accession"}),),
                provenance=Provenance(
                    source_url="https://www.uniprot.org",
                    license="CC-BY-4.0",
                    citation="https://doi.org/10.1093/nar/gkac1052",
                    attribution="UniProt Consortium",
                ),
            )
        )
    )
    reg.register(
        FakeWeaver(
            WeaverManifest(
                weaver_id="reactome",
                version="0.1.1",
                capabilities=(simple_capability("c", {"protein.uniprot.accession"}, {"pathway.reactome.names"}),),
                provenance=Provenance(
                    source_url="https://reactome.org",
                    license="CC0-1.0",
                    citation="https://doi.org/10.1093/nar/gkab1028",
                    attribution="Reactome",
                ),
            )
        )
    )
    # A weaver with no provenance — must contribute nothing.
    reg.register(
        FakeWeaver(
            WeaverManifest(
                weaver_id="bare",
                version="1.0.0",
                capabilities=(simple_capability("c", {"x"}, {"y"}),),
            )
        )
    )
    return reg


def test_references_for_ordered_and_deduped():
    reg = _registry()
    refs = references_for(["reactome", "uniprot", "uniprot"], reg)
    assert [r.weaver_id for r in refs] == ["reactome", "uniprot"]  # sorted, deduped


def test_references_skip_weavers_without_provenance():
    refs = references_for(["bare", "uniprot"], _registry())
    assert [r.weaver_id for r in refs] == ["uniprot"]


def test_references_unknown_weaver_ignored():
    assert references_for(["does-not-exist"], _registry()) == ()


def test_requirement_classification():
    by_id = {r.weaver_id: r for r in references_for(["uniprot", "reactome"], _registry())}
    assert by_id["uniprot"].requirement == "attribution_required"  # CC-BY
    assert by_id["reactome"].requirement == "cite_requested"  # CC0


def test_references_for_braid():
    reg = _registry()
    braid = Braid(
        steps=(
            CapabilityInvocation(
                weaver_id="uniprot",
                capability_id="c",
                input_types=frozenset({"protein.query"}),
                output_types=frozenset({"protein.uniprot.accession"}),
                primary_backend="api",
            ),
            CapabilityInvocation(
                weaver_id="reactome",
                capability_id="c",
                input_types=frozenset({"protein.uniprot.accession"}),
                output_types=frozenset({"pathway.reactome.names"}),
                primary_backend="api",
            ),
        ),
        from_types=frozenset({"protein.query"}),
        to_types=frozenset({"pathway.reactome.names"}),
    )
    refs = references_for_braid(braid, reg)
    assert [r.weaver_id for r in refs] == ["reactome", "uniprot"]


def test_render_attribution_required_mentions_cite():
    [ref] = references_for(["uniprot"], _registry())
    text = ref.render()
    assert "attribution required" in text
    assert "Cite: https://doi.org/10.1093/nar/gkac1052" in text
    assert "UniProt Consortium" in text


def test_render_cite_requested():
    [ref] = references_for(["reactome"], _registry())
    assert "citation requested" in ref.render()


def test_render_restricted_warns():
    ref = Reference("x", "https://x", "Proprietary", "", "X Corp", "restricted")
    assert "reuse terms unverified" in ref.render()


def test_format_references_bullets_and_empty():
    refs = references_for(["uniprot", "reactome"], _registry())
    text = format_references(refs)
    assert text.startswith("- ")
    assert text.count("\n") == 1  # two entries
    assert format_references([]) == ""


def test_reference_json_round_trip():
    [ref] = references_for(["uniprot"], _registry())
    assert Reference.from_json(ref.to_json()) == ref
