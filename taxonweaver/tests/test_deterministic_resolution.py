"""Integration checks for deterministic taxonomy resolution."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from taxonomy_resolver.build import build_taxonomy_database
from taxonomy_resolver.policy import MatchType, ResolutionStatus, WarningCode
from taxonomy_resolver.schemas import ResolveRequest
from taxonomy_resolver.service import TaxonomyResolverService


NODES_DMP = """1\t|\t1\t|\tno rank\t|\t\t|\t8\t|\t0\t|\t1\t|\t0\t|\t1\t|\t0\t|\t0\t|\t0\t|\troot\t|
2\t|\t1\t|\tsuperkingdom\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1224\t|\t2\t|\tphylum\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1236\t|\t1224\t|\tclass\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186801\t|\t1236\t|\torder\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186803\t|\t186801\t|\tfamily\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
239934\t|\t186803\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
853\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
854\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
855\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
856\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
857\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
"""

NAMES_DMP = """1\t|\troot\t|\t\t|\tscientific name\t|
2\t|\tBacteria\t|\tBacteria <prokaryote>\t|\tscientific name\t|
1224\t|\tBacillota\t|\t\t|\tscientific name\t|
1236\t|\tClostridia\t|\t\t|\tscientific name\t|
186801\t|\tClostridiales\t|\t\t|\tscientific name\t|
186803\t|\tOscillospiraceae\t|\t\t|\tscientific name\t|
239934\t|\tFaecalibacterium\t|\t\t|\tscientific name\t|
853\t|\tFaecalibacterium prausnitzii\t|\t\t|\tscientific name\t|
853\t|\tF. prausnitzii\t|\t\t|\tsynonym\t|
854\t|\tFaecalibacterium altus\t|\t\t|\tscientific name\t|
854\t|\tShared synonym\t|\t\t|\tsynonym\t|
855\t|\tFaecalibacterium minor\t|\t\t|\tscientific name\t|
855\t|\tShared synonym\t|\t\t|\tsynonym\t|
856\t|\tFaecalibacterium prausnitzii alpha\t|\t\t|\tscientific name\t|
857\t|\tFaecalibacterium prausnitzii beta\t|\t\t|\tscientific name\t|
"""


class DeterministicResolutionTests(unittest.TestCase):
    """Verify deterministic resolution behavior against a tiny synthetic taxonomy DB."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        tmpdir_path = Path(self._tmpdir.name)
        dump_path = tmpdir_path / "mini_taxdump.tar.gz"
        self.db_path = tmpdir_path / "mini_taxonomy.sqlite"
        self._write_taxdump_archive(dump_path)
        build_taxonomy_database(dump_path, self.db_path)
        self.service = TaxonomyResolverService(self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_resolves_exact_scientific_name(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterium prausnitzii",
                provided_level="species",
                allow_fuzzy=False,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC)
        self.assertEqual(result.match_type, MatchType.EXACT_SCIENTIFIC)
        self.assertTrue(result.auto_accept)
        self.assertEqual(result.matched_taxid, 853)
        self.assertEqual(result.lineage[-1].name, "Faecalibacterium prausnitzii")

    def test_resolves_exact_synonym(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="F. prausnitzii",
                provided_level="species",
                allow_fuzzy=False,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.RESOLVED_EXACT_SYNONYM)
        self.assertEqual(result.match_type, MatchType.EXACT_SYNONYM)
        self.assertIn(WarningCode.SYNONYM_MATCHED, result.warnings)
        self.assertEqual(result.matched_name, "Faecalibacterium prausnitzii")

    def test_resolves_normalized_exact_name(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="faecalibacterium_prausnitzii",
                provided_level="species",
                allow_fuzzy=False,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.RESOLVED_NORMALIZED)
        self.assertEqual(result.match_type, MatchType.NORMALIZED)
        self.assertIn(WarningCode.NORMALIZED_MATCHED, result.warnings)
        self.assertEqual(result.matched_taxid, 853)

    def test_surfaces_level_conflict_for_deterministic_match(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterium prausnitzii",
                provided_level="genus",
                allow_fuzzy=False,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.LEVEL_CONFLICT)
        self.assertTrue(result.review_required)
        self.assertFalse(result.auto_accept)
        self.assertIn(WarningCode.PROVIDED_LEVEL_CONFLICT, result.warnings)

    def test_requires_manual_review_for_ambiguous_exact_synonym(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Shared synonym",
                provided_level="species",
                allow_fuzzy=False,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(result.match_type, MatchType.EXACT_SYNONYM)
        self.assertTrue(result.review_required)
        self.assertEqual(len(result.candidates), 2)
        self.assertIn(WarningCode.MULTIPLE_EXACT_CANDIDATES, result.warnings)

    def test_get_lineage_returns_cached_entries(self) -> None:
        lineage = self.service.get_lineage(853)

        self.assertEqual(lineage[-1]["taxid"], 853)
        self.assertEqual(lineage[-1]["rank"], "species")
        self.assertEqual(lineage[-1]["name"], "Faecalibacterium prausnitzii")

    def test_returns_unique_fuzzy_candidate_for_typo(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterim prausnitzii",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.SUGGESTED_FUZZY_UNIQUE)
        self.assertEqual(result.match_type, MatchType.FUZZY)
        self.assertTrue(result.review_required)
        self.assertFalse(result.auto_accept)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].taxid, 853)

    def test_returns_multiple_fuzzy_candidates_when_scores_are_close(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterium prausnitzii gam",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE)
        self.assertEqual(result.match_type, MatchType.FUZZY)
        self.assertGreaterEqual(len(result.candidates), 2)
        self.assertIn(WarningCode.MULTIPLE_FUZZY_CANDIDATES, result.warnings)

    def test_returns_unresolved_for_unrelated_name(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Zzzzzzz organism",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.UNRESOLVED_NO_MATCH)

    def test_transformed_placeholder_suffix_recovers_base_taxon(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterium sp.",
                provided_level="species",
                allow_fuzzy=True,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.LEVEL_CONFLICT)
        self.assertTrue(result.review_required)
        self.assertFalse(result.auto_accept)
        self.assertEqual(result.matched_taxid, 239934)
        self.assertEqual(result.matched_rank, "genus")
        self.assertIn(WarningCode.TRANSFORM_APPLIED, result.warnings)
        self.assertIn(WarningCode.VAGUE_LABEL_DETECTED, result.warnings)
        self.assertIn(WarningCode.PLACEHOLDER_LABEL_DETECTED, result.warnings)
        self.assertEqual(result.metadata["transform_rule"], "strip_placeholder_suffix")
        self.assertEqual(result.metadata["transformed_name"], "Faecalibacterium")

    def test_transformed_exact_hit_stays_manual_review_when_no_level_conflict(self) -> None:
        result = self.service.resolve_name(
            ResolveRequest(
                original_name="Faecalibacterium spp.",
                provided_level="genus",
                allow_fuzzy=True,
            )
        )

        self.assertEqual(result.status, ResolutionStatus.MANUAL_REVIEW_REQUIRED)
        self.assertTrue(result.review_required)
        self.assertFalse(result.auto_accept)
        self.assertEqual(result.matched_taxid, 239934)
        self.assertIn(WarningCode.TRANSFORM_APPLIED, result.warnings)

    def test_service_initialization_skips_taxonomy_index_creation_on_open(self) -> None:
        taxonomy_connection = MagicMock()
        cache_connection = MagicMock()

        with (
            patch("taxonomy_resolver.service.initialize_database") as initialize_database,
            patch(
                "taxonomy_resolver.service.connect",
                side_effect=[taxonomy_connection, cache_connection],
            ) as connect,
            patch(
                "taxonomy_resolver.service.fetch_all_metadata",
                return_value={"taxonomy_build_version": "mini-build"},
            ),
        ):
            service = TaxonomyResolverService("taxonomy.sqlite", cache_db_path="cache.sqlite")
            service.close()

        self.assertEqual(
            initialize_database.call_args_list,
            [
                call(Path("taxonomy.sqlite"), create_indexes=False),
                call(Path("cache.sqlite")),
            ],
        )
        self.assertEqual(
            connect.call_args_list,
            [call(Path("taxonomy.sqlite")), call(Path("cache.sqlite"))],
        )
        taxonomy_connection.close.assert_called_once()
        cache_connection.close.assert_called_once()

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


class _BytesReader:
    """Small file-like wrapper used to write tar members in tests."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        """Read bytes from the in-memory tar member payload."""

        if size == -1:
            size = len(self._data) - self._offset
        start = self._offset
        end = min(len(self._data), self._offset + size)
        self._offset = end
        return self._data[start:end]
