"""Header discovery explores long fragments without coordinate extraction."""

import io
import tarfile

import pytest
from alphafold_weaver.backends.archive import (
    AlphafoldArchiveBackend,
    ArchiveFormatError,
    index_archive,
)
from braidworks.core import BackendConfigurationError


def archive(path, names):
    with tarfile.open(path, "w") as stream:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 100_000
            stream.addfile(member, io.BytesIO(b"x" * member.size))
    return path


def names():
    return [f"AF-Q8WZ42-F{n}-model_v6.cif.gz" for n in range(1, 13)] + [
        "AF-Q8WZ42-2-F1-model_v6.cif.gz",
        "AF-Q8WZ42-F1-model_v5.cif.gz",
    ]


async def fetch(backend, capability, query):
    return (
        await backend.fetch(
            capability,
            [query],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"full"}),
        )
    )[0]


async def test_full_fragments_isoforms_versions_and_capped_display(tmp_path):
    path = archive(tmp_path / "proteome.tar", names())
    backend = AlphafoldArchiveBackend([path])
    record = await fetch(backend, "list_models", {"protein.uniprot.accession": "Q8WZ42"})
    values = record.values
    assert len(values["structure.alphafold.model_id"]) == 14
    assert len(values["structure.alphafold.models"]) == 10
    coverage = values["structure.alphafold.model_coverage"]
    assert coverage["source_complete"] is True
    assert coverage["sources"][0]["header_bytes_read"] < 20_000
    assert path.stat().st_size > 1_000_000
    described = await fetch(
        backend, "describe_prediction", {"structure.alphafold.model_id": "AF-Q8WZ42-F12@v6"}
    )
    assert described.values["structure.alphafold.records"]["fragment_number"] == 12
    assert described.values["structure.alphafold.records"]["coverage"]["status"] == "unknown"
    assert "structure.alphafold.model_url" not in described.values
    isoform = await fetch(backend, "list_models", {"protein.uniprot.accession": "Q8WZ42-2"})
    assert isoform.values["structure.alphafold.model_id"] == ["AF-Q8WZ42-2-F1@v6"]


async def test_incomplete_scan_warns_and_unobserved_is_error(tmp_path):
    path = archive(tmp_path / "proteome.tar", names())
    backend = AlphafoldArchiveBackend([path], max_members=1)
    record = await fetch(backend, "list_models", {"protein.uniprot.accession": "Q8WZ42"})
    assert (
        record.warnings
        and record.values["structure.alphafold.model_coverage"]["source_complete"] is False
    )
    miss = await fetch(
        backend, "describe_prediction", {"structure.alphafold.model_id": "AF-Q8WZ42-F12@v6"}
    )
    assert miss.error
    bounded = index_archive(path, max_header_bytes=511)
    assert not bounded["complete"] and bounded["reason"] == "header_byte_cap"


async def test_duplicate_artifact_conflicts_and_archive_mutation_errors(tmp_path):
    path = archive(tmp_path / "proteome.tar", names())
    backend = AlphafoldArchiveBackend([path])
    old = backend.fingerprint()
    archive(path, ["AF-P04637-F1-model_v6.cif.gz"])
    changed = await fetch(backend, "list_models", {"protein.uniprot.accession": "Q8WZ42"})
    assert changed.error and old
    with pytest.raises(BackendConfigurationError, match="source identity"):
        backend.fingerprint()
    duplicate = archive(tmp_path / "duplicate.tar", ["AF-P04637-F1-model_v6.cif.gz"] * 2)
    error = await fetch(
        AlphafoldArchiveBackend([duplicate]), "list_models", {"protein.uniprot.accession": "P04637"}
    )
    assert "Conflicting" in error.error


def test_unsafe_member_is_never_extracted_and_compressed_outer_rejected(tmp_path):
    path = archive(tmp_path / "unsafe.tar", ["../AF-P04637-F1-model_v6.cif.gz"])
    with pytest.raises(ArchiveFormatError, match="Unsafe"):
        index_archive(path)
    import gzip

    compressed = tmp_path / "outer.tar.gz"
    compressed.write_bytes(gzip.compress(path.read_bytes()))
    with pytest.raises(ArchiveFormatError, match="uncompressed"):
        index_archive(compressed)
