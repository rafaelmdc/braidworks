"""Local backend behavior, strand mapping, and the shipped contract mixins."""

from __future__ import annotations

import pytest

from braidworks.core import BackendConfigurationError, Strand, StrandSet, WeaveStatus
from braidworks.testing.contract import CacheFingerprintTests, WeaverOrderContractTests

from taxonweaver import build_ncbi_weaver, vocab

SAMPLE_NAMES = [
    "Faecalibacterium prausnitzii",
    "Faecalibacterium altus",
    "Faecalibacterium minor",
    "Faecalibacterium prausnitzii alpha",
    "Faecalibacterium",
    "Bacteria",
]


def _ss(name: str, entity_id: str = "e"):
    return StrandSet.from_strands(entity_id, [Strand(vocab.ORGANISM_NAME, name)])


def _strand_map(result):
    return {s.type_id: s.value for s in result.strands}


async def _resolve_one(weaver, name, outputs):
    out = await weaver.execute_batch(
        vocab.RESOLVE_NAME, [_ss(name)], requested_outputs=frozenset(outputs), backend="local"
    )
    return out[0]


async def test_exact_core_only_no_lineage(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    r = await _resolve_one(w, "Faecalibacterium prausnitzii", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.OK
    sm = _strand_map(r)
    assert sm[vocab.TAXON_ID] == 853
    assert sm[vocab.SCIENTIFIC_NAME] == "Faecalibacterium prausnitzii"
    assert sm[vocab.TAXON_RANK] == "species"
    assert sm[vocab.PARENT_ID] == 239934  # Faecalibacterium genus
    assert vocab.LINEAGE not in sm
    assert r.computed_groups == frozenset({"core"})


async def test_lineage_request_adds_lineage_group(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    r = await _resolve_one(w, "Faecalibacterium prausnitzii", {vocab.LINEAGE})
    assert r.status is WeaveStatus.OK
    sm = _strand_map(r)
    lineage = sm[vocab.LINEAGE]
    assert lineage[-1]["name"] == "Faecalibacterium prausnitzii"
    assert lineage[0]["name"] == "root"
    assert {"taxid", "rank", "name"} <= set(lineage[-1])
    assert r.computed_groups == frozenset({"core", "lineage"})


async def test_synonym_resolves(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    r = await _resolve_one(w, "F. prausnitzii", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.OK
    assert _strand_map(r)[vocab.TAXON_ID] == 853


async def test_no_match_is_no_match_status(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    r = await _resolve_one(w, "Zzqq Nonexistent organism", {vocab.TAXON_ID})
    assert r.status is WeaveStatus.NO_MATCH
    assert r.strands == ()


async def test_batch_order_and_length(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    sets = [_ss(n, f"e{i}") for i, n in enumerate(SAMPLE_NAMES)]
    out = await w.execute_batch(
        vocab.RESOLVE_NAME, sets, requested_outputs=frozenset({vocab.TAXON_ID}), backend="local"
    )
    assert len(out) == len(sets)
    assert _strand_map(out[0])[vocab.TAXON_ID] == 853
    assert _strand_map(out[-1])[vocab.SCIENTIFIC_NAME] == "Bacteria"


async def test_resolve_taxid_capability(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    ss = StrandSet.from_strands("e", [Strand(vocab.TAXON_ID, 853)])
    out = await w.execute_batch(
        vocab.RESOLVE_TAXID,
        [ss],
        requested_outputs=frozenset({vocab.SCIENTIFIC_NAME, vocab.LINEAGE}),
        backend="local",
    )
    r = out[0]
    assert r.status is WeaveStatus.OK
    sm = _strand_map(r)
    assert sm[vocab.SCIENTIFIC_NAME] == "Faecalibacterium prausnitzii"
    assert sm[vocab.TAXON_RANK] == "species"
    assert sm[vocab.LINEAGE][-1]["taxid"] == 853


def test_bad_db_path_raises_backend_configuration_error(tmp_path):
    with pytest.raises(BackendConfigurationError):
        build_ncbi_weaver(db_path=tmp_path / "does-not-exist.sqlite")


def test_backend_fingerprint_local_is_build_version(mini_db_path):
    w = build_ncbi_weaver(db_path=mini_db_path)
    fp = w.backend_fingerprint("local")
    assert fp and fp != "unknown"


# --- shipped contract mixins -------------------------------------------------


class TestLocalOrderContract(WeaverOrderContractTests):
    capability_id = vocab.RESOLVE_NAME
    minimal_outputs = frozenset({vocab.TAXON_ID})
    backend = "local"

    @pytest.fixture(autouse=True)
    def _wire_db(self, mini_db_path):
        self._dbp = mini_db_path

    def make_weaver(self):
        return build_ncbi_weaver(db_path=self._dbp)

    def sample_strand_sets(self):
        return [_ss(n, f"e{i}") for i, n in enumerate(SAMPLE_NAMES)]


class TestLocalCacheFingerprint(CacheFingerprintTests):
    capability = vocab.resolve_name_capability(backends=("local",))
    consumed_values_a = {vocab.ORGANISM_NAME: "Faecalibacterium prausnitzii"}
    consumed_values_b = {vocab.ORGANISM_NAME: "Bacteria"}
    group_subset = "core"
    group_superset = "lineage"
