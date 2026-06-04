"""Shared fixtures for taxonweaver tests: a tiny synthetic taxonomy DB."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from taxonomy_resolver.build import build_taxonomy_database

from tests.test_deterministic_resolution import NAMES_DMP, NODES_DMP, _BytesReader


def build_mini_db(directory: Path) -> Path:
    """Build the mini Faecalibacterium taxonomy DB used across weaver tests."""
    archive = directory / "mini_taxdump.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in (("nodes.dmp", NODES_DMP), ("names.dmp", NAMES_DMP)):
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=_BytesReader(data))
    db_path = directory / "mini_taxonomy.sqlite"
    build_taxonomy_database(archive, db_path)
    return db_path


@pytest.fixture(scope="session")
def mini_db_path(tmp_path_factory) -> Path:
    return build_mini_db(tmp_path_factory.mktemp("taxonweaver_db"))
