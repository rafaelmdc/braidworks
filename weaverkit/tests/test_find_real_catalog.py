"""Plain-language search over the real weaver catalogue (specs + key registry).

Builds the same catalogue the installed weavers ship (#309) from the workspace specs,
then checks that common words a researcher would type find the intended field first.
Guards against description edits that quietly break ``braidworks.find``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from braidworks.core.catalog import FieldInfo, rank_fields
from weaverkit.spec import load_spec, type_descriptions

ROOT = Path(__file__).resolve().parents[2]


def _catalog() -> dict[str, FieldInfo]:
    descriptions: dict[str, str] = {}
    sources: dict[str, set[str]] = {}
    inputs: dict[str, set[str]] = {}
    consumers: dict[str, int] = {}
    for path in sorted(ROOT.glob("weavers/*/weaver.spec.toml")):
        spec = load_spec(path)
        descriptions.update(type_descriptions(spec))
        for cap in spec.capabilities:
            for type_id in cap.consumes:
                sources.setdefault(type_id, set()).add(spec.resolved_weaver_id)
                consumers[type_id] = consumers.get(type_id, 0) + 1
            for type_id in cap.produces:
                sources.setdefault(type_id, set()).add(spec.resolved_weaver_id)
                inputs.setdefault(type_id, set()).update(cap.consumes)
    return {
        type_id: FieldInfo(
            type_id,
            descriptions.get(type_id, ""),
            tuple(sorted(found)),
            tuple(sorted(inputs.get(type_id, ()))),
            consumers.get(type_id, 0),
        )
        for type_id, found in sources.items()
    }


CATALOG = _catalog()


@pytest.mark.parametrize(
    "query,expected",
    [
        ("pdb structures", "structure.pdb.ids"),
        ("experimental structures", "structure.pdb.ids"),
        ("taxon", "ncbi.taxon.id"),
        ("taxonomy id", "ncbi.taxon.id"),
        ("biological process", "go.biological_process"),
        ("interaction partners", "protein.interaction.partners"),
        ("gene symbol", "gene.symbol"),
        ("protein name", "protein.name"),
        ("uniprot accession", "protein.uniprot.accession"),
        ("gram stain", "microbe.trait.gram_stain"),
    ],
)
def test_common_words_find_the_intended_field_first(query, expected):
    assert rank_fields(query, CATALOG)[0].type_id == expected


@pytest.mark.parametrize("query,prefix", [("pathways", "pathway."), ("disease", "disease.")])
def test_topic_words_find_that_topic(query, prefix):
    top = [m.type_id for m in rank_fields(query, CATALOG, limit=3)]
    assert all(type_id.startswith(prefix) for type_id in top), top


def test_every_field_is_described():
    assert [t for t, info in CATALOG.items() if not info.description] == []
