"""Offline api-backend tests for wikidata_weaver — rank disambiguation of homonyms.

Drives the api backend through the mock client (no network). The homonym case is
"Pholidota": an orchid genus (botany) AND the pangolin order (zoology) both carry
P225 "Pholidota". Without help the name is AMBIGUOUS; the ``expected_rank`` param
collapses it to the single rank-matching item.
"""

from __future__ import annotations

from braidworks.core import Strand, StrandSet, WeaveStatus

from wikidata_weaver import factory


def _weaver():
    return factory.build_wikidata_weaver_fixture()


async def _resolve(name: str, *, params=None):
    ss = StrandSet.from_strands("e1", [Strand("organism.scientific_name", name)])
    return (
        await _weaver().execute_batch(
            "resolve_taxon",
            [ss],
            requested_outputs=frozenset({"wikipedia.title", "organism.vernacular_names"}),
            backend="api",
            params=params,
        )
    )[0]


async def test_homonym_is_ambiguous_without_rank():
    # Both the orchid genus and the pangolin order match P225 "Pholidota".
    result = await _resolve("Pholidota")
    assert result.status is WeaveStatus.AMBIGUOUS


async def test_expected_rank_disambiguates_to_the_animal():
    # rank=order picks the pangolin order, not the orchid genus.
    result = await _resolve("Pholidota", params={"expected_rank": "order"})
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikipedia.title"] == "Pangolin"


async def test_expected_rank_with_no_unique_match_stays_ambiguous():
    # rank=family matches neither candidate (genus/order) -> left ambiguous, not forced.
    result = await _resolve("Pholidota", params={"expected_rank": "family"})
    assert result.status is WeaveStatus.AMBIGUOUS


async def test_single_match_is_unaffected_by_rank():
    # A non-homonym still resolves; the param only acts on multi-item names.
    result = await _resolve("Ursus arctos", params={"expected_rank": "species"})
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikipedia.title"] == "Brown_bear"
