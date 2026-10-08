"""Regression coverage for public build safety and real CLI reporting."""

import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import tarfile
from unittest.mock import patch

import pytest
from ncbi_weaver.fixture import NAMES_DMP, NODES_DMP
from taxonomy_resolver.build import build_taxonomy_database


def write_dump(path, *, nodes=NODES_DMP, names=NAMES_DMP):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in (("nodes.dmp", nodes), ("names.dmp", names)):
            payload = content.encode()
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return path


@pytest.mark.parametrize("failure", ["nodes", "names", "validation", "publish"])
@pytest.mark.parametrize("existing", [True, False])
def test_failed_build_preserves_target_and_cleans_staging(tmp_path, failure, existing):
    dump = write_dump(tmp_path / "taxdump.tar.gz")
    target = tmp_path / "taxonomy.sqlite"
    if existing:
        build_taxonomy_database(dump, target)
    before = target.read_bytes() if existing else None
    if failure == "nodes":
        write_dump(dump, nodes="not-a-taxid\t|\t1\t|\tno rank\t|\n")
    elif failure == "names":
        write_dump(dump, names="invalid\t|\tname\t|\t\t|\tscientific name\t|\n")
    elif failure == "validation":
        write_dump(dump, nodes=NODES_DMP.replace("1\t|\t1\t|", "1\t|\t2\t|", 1))
    events = []

    def progress(stage, *_args):
        events.append(stage)

    if failure == "publish":
        with (
            patch("taxonomy_resolver.build.os.replace", side_effect=OSError("publish failed")),
            pytest.raises(OSError, match="publish failed"),
        ):
            build_taxonomy_database(dump, target, progress_callback=progress)
    else:
        with pytest.raises(ValueError):
            build_taxonomy_database(dump, target, progress_callback=progress)
    assert (target.read_bytes() if target.exists() else None) == before
    assert not list(tmp_path.glob(".taxonomy-build-*"))
    assert "done" not in events


def test_success_replaces_complete_database_and_retains_digest(tmp_path):
    dump = write_dump(tmp_path / "taxdump.tar.gz")
    target = tmp_path / "taxonomy.sqlite"
    build_taxonomy_database(dump, target)
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE old_marker (id INTEGER)")
    write_dump(dump, names=NAMES_DMP.replace("Bacteria", "Replacement bacteria"))
    summary = build_taxonomy_database(dump, target)
    assert summary.db_path == str(target)
    assert summary.source_dump_sha256 == hashlib.sha256(dump.read_bytes()).hexdigest()
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute("SELECT name_txt FROM taxon_names WHERE taxid=2").fetchone()[0]
            == "Replacement bacteria"
        )
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE name='old_marker'").fetchone()
            is None
        )
        assert (
            connection.execute(
                "SELECT value FROM metadata WHERE key='source_dump_sha256'"
            ).fetchone()[0]
            == summary.source_dump_sha256
        )
    assert not list(tmp_path.glob(".taxonomy-build-*"))


@pytest.mark.parametrize("module", ["taxonomy_tools.cli", "taxonomy_tools.build_ncbi_taxonomy"])
def test_real_cli_build_and_malformed_input(tmp_path, module):
    dump = write_dump(tmp_path / "taxdump.tar.gz")
    target = tmp_path / "taxonomy.sqlite"
    report = tmp_path / "report.json"
    command = [sys.executable, "-m", module]
    if module.endswith(".cli"):
        command.append("build-db")
    command += ["--dump", str(dump), "--db", str(target), "--report-json", str(report)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    summary = json.loads(report.read_text())
    assert summary["db_path"] == str(target)
    assert summary["taxa_count"] == 12
    assert all(summary["validation_checks"].values())
    assert f"Taxa: {summary['taxa_count']}" in result.stdout
    assert summary["source_dump_sha256"] in result.stdout
    before = target.read_bytes()
    report.unlink()
    write_dump(dump, nodes="broken\n")
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 1
    assert "Taxonomy build failed" in result.stderr
    assert "Traceback" not in result.stderr
    assert "Built taxonomy database" not in result.stdout
    assert not report.exists()
    assert target.read_bytes() == before
