"""Shared fixtures for taxon_weaver tests: a tiny synthetic taxonomy DB.

The mini dump + build live in the package (``taxon_weaver.fixture``) so the same
deterministic fixture backs both the tests and ``weaverkit verify --strict``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from taxon_weaver.fixture import build_fixture_db


def build_mini_db(directory: Path) -> Path:
    """Build the mini Faecalibacterium taxonomy DB used across weaver tests."""
    return build_fixture_db(directory)


@pytest.fixture(scope="session")
def mini_db_path(tmp_path_factory) -> Path:
    return build_mini_db(tmp_path_factory.mktemp("taxon_weaver_db"))
