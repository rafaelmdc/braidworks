"""Integration-style checks for the unified taxonomy CLI helpers."""

from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from taxonomy_resolver.build import build_taxonomy_database
from taxonomy_tools import cli

from tests.test_deterministic_resolution import NAMES_DMP, NODES_DMP, _BytesReader


class TaxonomyCliTests(unittest.TestCase):
    """Verify the unified CLI command surface against a tiny synthetic DB."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        tmpdir_path = Path(self._tmpdir.name)
        dump_path = tmpdir_path / "mini_taxdump.tar.gz"
        self.db_path = tmpdir_path / "mini_taxonomy.sqlite"
        self.cache_db_path = tmpdir_path / "review_cache.sqlite"
        self._write_taxdump_archive(dump_path)
        summary = build_taxonomy_database(dump_path, self.db_path)
        self.taxonomy_build_version = summary.taxonomy_build_version

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_build_info_command_prints_metadata(self) -> None:
        payload = self._run_cli("build-info", "--db", str(self.db_path))

        self.assertEqual(payload["taxonomy_build_version"], self.taxonomy_build_version)
        self.assertIn("taxa_count", payload)

    def test_resolve_batch_command_writes_output(self) -> None:
        input_path = Path(self._tmpdir.name) / "resolve_input.json"
        output_path = Path(self._tmpdir.name) / "resolve_output.json"
        input_path.write_text(
            json.dumps(
                {
                    "batch_id": "batch-001",
                    "items": [
                        {
                            "original_name": "Faecalibacterium prausnitzii",
                            "provided_level": "species",
                            "allow_fuzzy": False,
                        },
                        {
                            "original_name": "Faecalibacterim prausnitzii",
                            "provided_level": "species",
                            "allow_fuzzy": True,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        self._run_cli(
            "resolve-batch",
            "--db",
            str(self.db_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            expect_stdout=False,
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["batch_id"], "batch-001")
        self.assertEqual(len(payload["results"]), 2)

    def test_apply_decisions_command_persists_cache(self) -> None:
        input_path = Path(self._tmpdir.name) / "decisions.json"
        input_path.write_text(
            json.dumps(
                [
                    {
                        "action": "confirm",
                        "original_name": "Faecalibacterim prausnitzii",
                        "normalized_name": "faecalibacterim prausnitzii",
                        "provided_level": "species",
                        "taxonomy_build_version": self.taxonomy_build_version,
                        "reviewer": "tester",
                        "resolved_taxid": 853,
                        "matched_scientific_name": "Faecalibacterium prausnitzii",
                        "match_type": "user_selected",
                        "status": "confirmed_by_user",
                        "score": 99.0,
                        "warnings": [],
                    }
                ]
            ),
            encoding="utf-8",
        )

        summary = self._run_cli(
            "apply-decisions",
            "--db",
            str(self.db_path),
            "--cache-db",
            str(self.cache_db_path),
            "--input",
            str(input_path),
        )

        self.assertEqual(summary["applied_count"], 1)

        result = self._run_cli(
            "resolve-name",
            "Faecalibacterim prausnitzii",
            "--db",
            str(self.db_path),
            "--cache-db",
            str(self.cache_db_path),
            "--level",
            "species",
        )
        self.assertTrue(result["cache_applied"])
        self.assertEqual(result["match_type"], "cached")

    def test_inspect_lineage_command_returns_lineage(self) -> None:
        payload = self._run_cli(
            "inspect-lineage",
            "--db",
            str(self.db_path),
            "--taxid",
            "853",
        )

        self.assertEqual(payload["taxid"], 853)
        self.assertEqual(payload["lineage"][-1]["name"], "Faecalibacterium prausnitzii")

    def _run_cli(self, *args: str, expect_stdout: bool = True) -> dict[str, object]:
        """Run the unified CLI and parse its JSON stdout when expected."""

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            parser = cli.build_parser()
            parsed_args = parser.parse_args(list(args))
            parsed_args.func(parsed_args)
        if not expect_stdout:
            return {}
        return json.loads(stdout.getvalue())

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
