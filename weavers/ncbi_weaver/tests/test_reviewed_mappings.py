"""Integration checks for reviewed mapping persistence and reuse."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from taxonomy_resolver.build import build_taxonomy_database
from taxonomy_resolver.policy import MatchType, ResolutionStatus
from taxonomy_resolver.schemas import DecisionAction, DecisionRecord, ResolveRequest
from taxonomy_resolver.service import TaxonomyResolverService

from tests.test_deterministic_resolution import NAMES_DMP, NODES_DMP, _BytesReader


class ReviewedMappingTests(unittest.TestCase):
    """Verify conservative reviewed mapping persistence and reuse rules."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        tmpdir_path = Path(self._tmpdir.name)
        dump_path = tmpdir_path / "mini_taxdump.tar.gz"
        self.db_path = tmpdir_path / "mini_taxonomy.sqlite"
        self.cache_db_path = tmpdir_path / "review_cache.sqlite"
        self._write_taxdump_archive(dump_path)
        summary = build_taxonomy_database(dump_path, self.db_path)
        self.taxonomy_build_version = summary.taxonomy_build_version
        self.service = TaxonomyResolverService(
            self.db_path,
            cache_db_path=self.cache_db_path,
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_confirmed_reviewed_mapping_is_reused(self) -> None:
        self.service.record_decision(
            DecisionRecord(
                action=DecisionAction.CONFIRM,
                original_name="Faecalibacterim prausnitzii",
                normalized_name="faecalibacterim prausnitzii",
                provided_level="species",
                taxonomy_build_version=self.taxonomy_build_version,
                reviewer="tester",
                resolved_taxid=853,
                matched_scientific_name="Faecalibacterium prausnitzii",
                match_type=MatchType.USER_SELECTED,
                status=ResolutionStatus.CONFIRMED_BY_USER,
                score=99.0,
            )
        )

        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterim prausnitzii",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertTrue(result.cache_applied)
        self.assertEqual(result.match_type, MatchType.CACHED)
        self.assertEqual(result.status, ResolutionStatus.CONFIRMED_BY_USER)
        self.assertEqual(result.matched_taxid, 853)

    def test_cache_is_not_reused_for_different_level(self) -> None:
        self.service.record_decision(
            DecisionRecord(
                action=DecisionAction.CONFIRM,
                original_name="Faecalibacterim prausnitzii",
                normalized_name="faecalibacterim prausnitzii",
                provided_level="species",
                taxonomy_build_version=self.taxonomy_build_version,
                reviewer="tester",
                resolved_taxid=853,
                matched_scientific_name="Faecalibacterium prausnitzii",
                match_type=MatchType.USER_SELECTED,
                status=ResolutionStatus.CONFIRMED_BY_USER,
                score=99.0,
            )
        )

        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterim prausnitzii",
                provided_level="genus",
                allow_fuzzy=True,
            )
        )

        self.assertFalse(result.cache_applied)
        self.assertNotEqual(result.match_type, MatchType.CACHED)

    def test_cache_is_not_reused_for_rejected_decision(self) -> None:
        self.service.record_decision(
            DecisionRecord(
                action=DecisionAction.REJECT,
                original_name="Faecalibacterim prausnitzii",
                normalized_name="faecalibacterim prausnitzii",
                provided_level="species",
                taxonomy_build_version=self.taxonomy_build_version,
                reviewer="tester",
                resolved_taxid=None,
                matched_scientific_name=None,
                match_type=MatchType.NONE,
                status=ResolutionStatus.REJECTED_BY_USER,
            )
        )

        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterim prausnitzii",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertFalse(result.cache_applied)
        self.assertEqual(result.status, ResolutionStatus.SUGGESTED_FUZZY_UNIQUE)

    def _write_taxdump_archive(self, archive_path: Path) -> None:
        """Create a small tar.gz archive matching the builder's expectations."""

        with tarfile.open(archive_path, "w:gz") as archive:
            self._add_text_member(archive, "nodes.dmp", NODES_DMP)
            self._add_text_member(archive, "names.dmp", NAMES_DMP)

    def _add_text_member(self, archive: tarfile.TarFile, name: str, content: str) -> None:
        """Add one UTF-8 text member to a tar archive."""

        data = content.encode("utf-8")
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        archive.addfile(info, fileobj=_BytesReader(data))
