"""ncbi.list_genomes + describe_genome against a mocked Datasets v2 genome API.

Offline (httpx.MockTransport). Exercises: taxid -> assembly accessions (the fan
dimension), filter parameters, the assembly/sequences output groups (and that the
sequences endpoint is hit only when that group is requested), and the misses.
"""

from __future__ import annotations

import httpx

from braidworks.core import Strand, StrandSet, WeaveStatus

from ncbi_weaver import build_ncbi_weaver, vocab

ASSEMBLIES = {
    "562": [
        {"accession": "GCF_000005845.2",
         "organism": {"organism_name": "Escherichia coli K-12", "tax_id": 511145},
         "assembly_info": {"assembly_level": "Complete Genome", "assembly_name": "ASM584v2",
                           "submitter": "UW", "release_date": "2013-09-26",
                           "refseq_category": "reference genome"},
         "assembly_stats": {"total_sequence_length": 4641652, "gc_percent": 51, "contig_n50": 4641652},
         "annotation_info": {"stats": {"gene_counts": {"total": 4651, "protein_coding": 4290}}}},
        {"accession": "GCA_000008865.2",
         "organism": {"organism_name": "Escherichia coli O157:H7", "tax_id": 386585},
         "assembly_info": {"assembly_level": "Complete Genome", "assembly_name": "ASM886v2",
                           "refseq_category": "na"},
         "assembly_stats": {"total_sequence_length": 5594605}},
    ],
    "999999": [],
}
SEQUENCES = {
    "GCF_000005845.2": [
        {"chr_name": "chromosome", "role": "assembled-molecule", "length": 4641652,
         "genbank_accession": "U00096.3", "refseq_accession": "NC_000913.3"},
    ],
}


def _handler(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if "/genome/taxon/" in path and path.endswith("/dataset_report"):
            taxid = path.split("/genome/taxon/", 1)[1].split("/")[0]
            rows = ASSEMBLIES.get(taxid)
            if rows is None:
                return httpx.Response(404, json={})
            # apply the reference_only filter the param maps to
            if request.url.params.get("filters.reference_only") == "true":
                rows = [r for r in rows if r["assembly_info"].get("refseq_category") == "reference genome"]
            return httpx.Response(200, json={"reports": rows, "total_count": len(rows)})
        if "/genome/accession/" in path and path.endswith("/dataset_report"):
            acc = path.split("/genome/accession/", 1)[1].split("/")[0]
            row = next((r for v in ASSEMBLIES.values() for r in v if r["accession"] == acc), None)
            return httpx.Response(200, json={"reports": [row] if row else []})
        if "/genome/accession/" in path and path.endswith("/sequence_reports"):
            acc = path.split("/genome/accession/", 1)[1].split("/")[0]
            return httpx.Response(200, json={"reports": SEQUENCES.get(acc, [])})
        return httpx.Response(404, json={})
    return handler


def _weaver(calls):
    client = httpx.AsyncClient(
        base_url="https://api.test/datasets/v2", transport=httpx.MockTransport(_handler(calls))
    )
    return build_ncbi_weaver(api_client=client)


async def _run(cap, type_id, value, outputs, *, params=None, calls=None):
    calls = calls if calls is not None else []
    out = await _weaver(calls).execute_batch(
        cap, [StrandSet.from_strands("e", [Strand(type_id, value)])],
        requested_outputs=frozenset(outputs), backend="api", params=params,
    )
    return out[0], calls


async def test_list_genomes_returns_accessions_and_count():
    r, _ = await _run(vocab.LIST_GENOMES, vocab.TAXON_ID, "562", vocab.LIST_GENOMES_OUTPUTS)
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENOME_ACCESSION] == ["GCA_000008865.2", "GCF_000005845.2"]  # sorted
    assert sm[vocab.ASSEMBLY_COUNT] == 2
    assert {a["accession"] for a in sm[vocab.ASSEMBLY_RECORDS]} == set(sm[vocab.GENOME_ACCESSION])


async def test_list_genomes_reference_only_filter():
    r, _ = await _run(vocab.LIST_GENOMES, vocab.TAXON_ID, "562", vocab.LIST_GENOMES_OUTPUTS,
                      params={"reference_only": True})
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.GENOME_ACCESSION] == ["GCF_000005845.2"]  # only the reference genome


async def test_list_genomes_empty_is_a_miss():
    r, _ = await _run(vocab.LIST_GENOMES, vocab.TAXON_ID, "999999", vocab.LIST_GENOMES_OUTPUTS)
    assert r.status is WeaveStatus.NO_MATCH


async def test_describe_genome_assembly_group_only_skips_sequences_call():
    calls: list[str] = []
    r, calls = await _run(vocab.DESCRIBE_GENOME, vocab.GENOME_ACCESSION, "GCF_000005845.2",
                          vocab.ASSEMBLY_GROUP, calls=calls)
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.ASSEMBLY_LEVEL] == "Complete Genome"
    assert sm[vocab.ASSEMBLY_TITLE] == "ASM584v2"
    assert sm[vocab.ASSEMBLY_DETAIL]["gene_counts"]["protein_coding"] == 4290
    assert vocab.SEQUENCE_RECORDS not in sm  # not requested
    assert not any(p.endswith("/sequence_reports") for p in calls)  # endpoint not hit


async def test_describe_genome_sequences_group_fetches_sequences():
    r, calls = await _run(vocab.DESCRIBE_GENOME, vocab.GENOME_ACCESSION, "GCF_000005845.2",
                          frozenset({vocab.SEQUENCE_RECORDS}))
    sm = {s.type_id: s.value for s in r.strands}
    assert sm[vocab.SEQUENCE_RECORDS][0]["refseq_accession"] == "NC_000913.3"
    assert any(p.endswith("/sequence_reports") for p in calls)


async def test_taxid_fans_into_each_genome_described():
    # organism taxid -> list_genomes -> fan -> describe_genome, end to end.
    from braidworks.core import Braider, BraidRegistry, ExpandPolicy, LocalExecutor

    calls: list[str] = []
    reg = BraidRegistry()
    reg.register(_weaver(calls))
    braid = Braider(reg).plan(
        available_types=frozenset({vocab.TAXON_ID}),
        target_types=frozenset({vocab.ASSEMBLY_LEVEL}),
    )
    sets = [StrandSet.from_strands("ecoli", [Strand(vocab.TAXON_ID, "562")])]
    result = await LocalExecutor(reg).execute(braid, sets, expand_policy=ExpandPolicy.all())
    assert len(result.resolved) == 2  # one leaf per assembly
    assert {ss.get(vocab.GENOME_ACCESSION).value for ss in result.resolved} == {
        "GCF_000005845.2", "GCA_000008865.2"}
    assert all(ss.get(vocab.ASSEMBLY_LEVEL).value == "Complete Genome" for ss in result.resolved)
    assert all(ss.parent_id == "ecoli" for ss in result.resolved)
