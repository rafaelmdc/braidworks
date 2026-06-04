"""Integration checks for the Phase 2 taxonomy DB builder."""

from __future__ import annotations

import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from taxonomy_resolver.build import build_taxonomy_database


NODES_DMP = """1\t|\t1\t|\tno rank\t|\t\t|\t8\t|\t0\t|\t1\t|\t0\t|\t1\t|\t0\t|\t0\t|\t0\t|\troot\t|
2\t|\t1\t|\tsuperkingdom\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1224\t|\t2\t|\tphylum\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1236\t|\t1224\t|\tclass\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186801\t|\t1236\t|\torder\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186803\t|\t186801\t|\tfamily\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
239934\t|\t186803\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
853\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
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
"""

RANKEDLINEAGE_DMP = """853\t|\tFaecalibacterium prausnitzii\t|\tFaecalibacterium prausnitzii\t|\tFaecalibacterium\t|\tOscillospiraceae\t|\tClostridiales\t|\tClostridia\t|\tBacillota\t|\t\t|\tBacteria\t|
"""


class BuildNcbiTaxonomyTests(unittest.TestCase):
    """Exercise the builder with a tiny deterministic taxdump fixture."""

    def test_build_populates_reference_tables_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            dump_path = tmpdir_path / "mini_taxdump.tar.gz"
            db_path = tmpdir_path / "mini_taxonomy.sqlite"
            self._write_taxdump_archive(dump_path)

            summary = build_taxonomy_database(dump_path, db_path)

            self.assertEqual(summary.taxa_count, 8)
            self.assertEqual(summary.name_count, 9)
            self.assertEqual(summary.scientific_name_count, 8)
            self.assertEqual(summary.synonym_count, 1)
            self.assertEqual(summary.lineage_cache_count, 8)
            self.assertTrue(all(summary.validation_checks.values()))
            self.assertTrue(summary.rankedlineage_present)

            with sqlite3.connect(db_path) as connection:
                taxa_count = connection.execute("SELECT COUNT(*) FROM taxa").fetchone()[0]
                names_count = connection.execute("SELECT COUNT(*) FROM taxon_names").fetchone()[0]
                lineage_row = connection.execute(
                    """
                    SELECT lineage_json
                    FROM lineage_cache
                    WHERE taxid = 853
                    """
                ).fetchone()
                metadata_value = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'taxonomy_build_version'"
                ).fetchone()[0]
                sqlite_optimized = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'sqlite_post_build_optimized'"
                ).fetchone()[0]

            self.assertEqual(taxa_count, 8)
            self.assertEqual(names_count, 9)
            lineage_json = json.loads(lineage_row[0])
            self.assertEqual(lineage_json[1][2], "Bacteria")
            self.assertEqual(lineage_json[2][2], "Bacillota")
            self.assertEqual(lineage_json[3][2], "Clostridia")
            self.assertEqual(lineage_json[4][2], "Clostridiales")
            self.assertEqual(lineage_json[5][2], "Oscillospiraceae")
            self.assertEqual(lineage_json[6][2], "Faecalibacterium")
            self.assertEqual(lineage_json[7][2], "Faecalibacterium prausnitzii")
            self.assertEqual(lineage_json[-1][0], 853)
            self.assertEqual(metadata_value, summary.taxonomy_build_version)
            self.assertEqual(sqlite_optimized, "true")

    def test_build_emits_progress_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            dump_path = tmpdir_path / "mini_taxdump.tar.gz"
            db_path = tmpdir_path / "mini_taxonomy.sqlite"
            self._write_taxdump_archive(dump_path)
            events: list[tuple[str, str, int | None, int | None, bool]] = []

            build_taxonomy_database(
                dump_path,
                db_path,
                progress_callback=lambda stage, message, current, total, final: events.append(
                    (stage, message, current, total, final)
                ),
            )

            self.assertTrue(any(stage == "nodes" for stage, *_ in events))
            self.assertTrue(any(stage == "names" for stage, *_ in events))
            self.assertTrue(any(stage == "lineage" for stage, *_ in events))
            self.assertTrue(any(stage == "optimize" for stage, *_ in events))
            self.assertTrue(any(event[0] == "done" and event[4] for event in events))

    def _write_taxdump_archive(self, archive_path: Path) -> None:
        """Create a minimal tar.gz archive matching the builder's expectations."""

        with tarfile.open(archive_path, "w:gz") as archive:
            self._add_text_member(archive, "nodes.dmp", NODES_DMP)
            self._add_text_member(archive, "names.dmp", NAMES_DMP)
            self._add_text_member(archive, "rankedlineage.dmp", RANKEDLINEAGE_DMP)

    def _add_text_member(self, archive: tarfile.TarFile, name: str, content: str) -> None:
        """Add one UTF-8 text member to a tar archive."""

        data = content.encode("utf-8")
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        archive.addfile(info, fileobj=_BytesReader(data))


class _BytesReader:
    """Small file-like wrapper used to write tar members in the test fixture."""

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


if __name__ == "__main__":
    unittest.main()
