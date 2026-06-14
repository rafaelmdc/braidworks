"""Large-scale end-to-end test against a real NCBI taxonomy DB.

Opt-in and heavy: set ``BRAIDWORKS_RUN_LIVE=1`` to enable. On first run it
downloads the real NCBI taxdump (~70 MB) and builds the SQLite DB (~1.2 GB,
~1 min) into the per-user cache via ``ensure_taxonomy_db``; later runs reuse it
instantly. It then resolves ~1,000 real organism names end-to-end through the
weaver and asserts exact, deterministic resolution, plus a couple of known-truth
lineages. This is the live counterpart to the synthetic mini-DB suites.
"""

from __future__ import annotations

import os
import random
import sqlite3
from pathlib import Path

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus
from braidworks.testing.contract import WeaverOrderContractTests

from ncbi_weaver import build_ncbi_weaver, vocab
from ncbi_weaver.setup import db_is_valid, default_db_path, ensure_taxonomy_db

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason="live NCBI E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (downloads ~70 MB, builds ~1.2 GB)",
)

SAMPLE_SIZE = 1000
SAMPLE_SEED = 20260606


@pytest.fixture(scope="session")
def real_db_path() -> Path:
    """Ensure a real NCBI DB exists (reuse the user cache, else download + build)."""
    target = default_db_path()
    if db_is_valid(target):
        return target
    return ensure_taxonomy_db(target, auto=True)


def _sample_unique_scientific_names(db_path: Path, n: int, seed: int) -> dict[str, int]:
    """Return ``{scientific_name: taxid}`` for n random species with a unique name.

    Homonyms (a name shared by two taxa as a scientific name) are skipped so that
    exact resolution has a single unambiguous expected taxid.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        taxids = [row[0] for row in con.execute("SELECT taxid FROM taxa WHERE rank = 'species'")]
        random.Random(seed).shuffle(taxids)
        out: dict[str, int] = {}
        for taxid in taxids:
            if len(out) >= n:
                break
            row = con.execute(
                "SELECT name_txt FROM taxon_names "
                "WHERE taxid = ? AND name_class = 'scientific name'",
                (taxid,),
            ).fetchone()
            if not row:
                continue
            name = row[0]
            (count,) = con.execute(
                "SELECT COUNT(*) FROM taxon_names "
                "WHERE name_txt = ? AND name_class = 'scientific name'",
                (name,),
            ).fetchone()
            if count == 1:
                out[name] = taxid
        return out
    finally:
        con.close()


@pytest.fixture(scope="session")
def sampled_names(real_db_path) -> dict[str, int]:
    names = _sample_unique_scientific_names(real_db_path, SAMPLE_SIZE, SAMPLE_SEED)
    assert len(names) >= SAMPLE_SIZE * 0.9, "could not sample enough unique species names"
    return names


def _strand_map(result) -> dict:
    return {s.type_id: s.value for s in result.strands}


async def _resolve_names(weaver, names, outputs):
    sets = [
        StrandSet.from_strands(str(i), [Strand(vocab.ORGANISM_NAME, name)])
        for i, name in enumerate(names)
    ]
    return await weaver.execute_batch(
        vocab.RESOLVE_NAME, sets, requested_outputs=frozenset(outputs), backend="local"
    )


async def test_e2e_bulk_exact_resolution(real_db_path, sampled_names):
    weaver = build_ncbi_weaver(db_path=real_db_path)
    names = list(sampled_names)
    out = await _resolve_names(weaver, names, {vocab.TAXON_ID})

    assert len(out) == len(names)
    assert all(r.status is not WeaveStatus.ERROR for r in out), "no entity should hard-error"

    exact = sum(
        1
        for name, result in zip(names, out)
        if result.status is WeaveStatus.OK
        and _strand_map(result).get(vocab.TAXON_ID) == sampled_names[name]
    )
    rate = exact / len(names)
    assert rate >= 0.99, f"exact resolution rate too low: {rate:.3%} ({exact}/{len(names)})"


async def test_e2e_batch_is_deterministic(real_db_path, sampled_names):
    weaver = build_ncbi_weaver(db_path=real_db_path)
    subset = list(sampled_names)[:200]
    forward = await _resolve_names(weaver, subset, {vocab.TAXON_ID})
    reverse = await _resolve_names(weaver, list(reversed(subset)), {vocab.TAXON_ID})

    fwd_ids = [_strand_map(r).get(vocab.TAXON_ID) for r in forward]
    rev_ids = [_strand_map(r).get(vocab.TAXON_ID) for r in reversed(reverse)]
    assert fwd_ids == rev_ids


async def test_e2e_known_lineage_homo_sapiens(real_db_path):
    weaver = build_ncbi_weaver(db_path=real_db_path)
    out = await _resolve_names(weaver, ["Homo sapiens"], {vocab.TAXON_ID, vocab.LINEAGE})
    sm = _strand_map(out[0])

    assert out[0].status is WeaveStatus.OK
    assert sm[vocab.TAXON_ID] == 9606
    assert sm[vocab.PARENT_ID] == 9605  # genus Homo
    lineage_ids = [entry["taxid"] for entry in sm[vocab.LINEAGE]]
    assert 9605 in lineage_ids   # Homo
    assert 9604 in lineage_ids   # Hominidae
    assert 40674 in lineage_ids  # Mammalia
    assert lineage_ids[-1] == 9606  # the taxon itself is last


async def test_e2e_describe_taxon_known(real_db_path):
    weaver = build_ncbi_weaver(db_path=real_db_path)
    ss = StrandSet.from_strands("h", [Strand(vocab.TAXON_ID, 9606)])
    out = await weaver.execute_batch(
        vocab.DESCRIBE_TAXON,
        [ss],
        requested_outputs=frozenset({vocab.SCIENTIFIC_NAME, vocab.TAXON_RANK}),
        backend="local",
    )
    sm = _strand_map(out[0])
    assert sm[vocab.SCIENTIFIC_NAME] == "Homo sapiens"
    assert sm[vocab.TAXON_RANK] == "species"


class TestLocalContractLive(WeaverOrderContractTests):
    """Run the shipped order contract against the real DB (memory-note intent)."""

    capability_id = vocab.RESOLVE_NAME
    minimal_outputs = frozenset({vocab.TAXON_ID})
    backend = "local"

    @pytest.fixture(autouse=True)
    def _wire(self, real_db_path, sampled_names):
        self._db = real_db_path
        self._names = list(sampled_names)[:8]

    def make_weaver(self):
        return build_ncbi_weaver(db_path=self._db)

    def sample_strand_sets(self):
        return [
            StrandSet.from_strands(str(i), [Strand(vocab.ORGANISM_NAME, name)])
            for i, name in enumerate(self._names)
        ]


async def test_live_list_children_genus_to_species():
    """API-only drift check: a real genus -> its species taxids (no DB build)."""
    weaver = build_ncbi_weaver(enable_api=True)
    # Faecalibacterium (216851) -> its species (the fan dimension).
    out = await weaver.execute_batch(
        vocab.LIST_CHILDREN,
        [StrandSet.from_strands("g", [Strand(vocab.TAXON_ID, "216851")])],
        requested_outputs=vocab.CHILDREN_OUTPUTS,
        backend="api",
    )
    r = out[0]
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    ids = sm[vocab.TAXON_ID]
    assert isinstance(ids, list) and 853 in ids  # F. prausnitzii is a species child
    assert sm[vocab.CHILDREN_COUNT] == len(ids)
    assert all(c["rank"] == "species" for c in sm[vocab.CHILDREN_RECORDS])
    assert ids == sorted(set(ids))  # deduped + deterministic (ascending)


async def test_live_list_genomes_and_describe():
    """API-only drift check: E. coli (562) -> reference genome -> its detail."""
    weaver = build_ncbi_weaver(enable_api=True)
    lst = await weaver.execute_batch(
        vocab.LIST_GENOMES,
        [StrandSet.from_strands("e", [Strand(vocab.TAXON_ID, "562")])],
        requested_outputs=vocab.LIST_GENOMES_OUTPUTS,
        backend="api",
        params={"reference_only": True},
    )
    r = lst[0]
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    accs = sm[vocab.GENOME_ACCESSION]
    assert "GCF_000005845.2" in accs  # the E. coli K-12 reference assembly
    assert sm[vocab.ASSEMBLY_COUNT] == len(accs)

    desc = await weaver.execute_batch(
        vocab.DESCRIBE_GENOME,
        [StrandSet.from_strands("g", [Strand(vocab.GENOME_ACCESSION, "GCF_000005845.2")])],
        requested_outputs=vocab.ASSEMBLY_GROUP | vocab.SEQUENCES_GROUP,
        backend="api",
    )
    d = {s.type_id: s.value for s in desc[0].strands}
    assert d[vocab.ASSEMBLY_LEVEL] == "Complete Genome"
    assert "Escherichia coli" in d[vocab.ASSEMBLY_ORGANISM]
    assert any(s["refseq_accession"] == "NC_000913.3" for s in d[vocab.SEQUENCE_RECORDS])
