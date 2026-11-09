"""`pip install braidworks` must keep pulling in every public source and the browser."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _project(path: Path) -> dict:
    return tomllib.loads(path.read_text())["project"]


def _version(text: str) -> tuple[int, ...]:
    return tuple(map(int, text.split(".")))


class MetaPackageTests(unittest.TestCase):
    def setUp(self):
        self.meta = _project(ROOT / "braidworks-meta/pyproject.toml")
        self.floors = {}
        for requirement in self.meta["dependencies"]:
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)(\[[a-z,]+\])?>=([0-9.]+)", requirement)
            self.assertIsNotNone(match, f"use a floor without a ceiling: {requirement}")
            self.floors[match.group(1)] = (match.group(2), match.group(3))
        self.packages = {
            project["name"]: project
            for project in map(
                _project,
                [
                    ROOT / "braidworks-core/pyproject.toml",
                    ROOT / "weaverkit/pyproject.toml",
                    *(ROOT / "weavers").glob("*/pyproject.toml"),
                ],
            )
        }

    def test_every_public_source_and_the_browser_are_included(self):
        expected = set(self.packages) - {"example_weaver"}  # teaching reference only
        self.assertEqual(set(self.floors), expected)
        self.assertEqual(self.floors["weaverkit"][0], "[serve]")

    def test_floors_are_released_workspace_versions(self):
        for name, (_, floor) in self.floors.items():
            with self.subTest(package=name):
                self.assertLessEqual(_version(floor), _version(self.packages[name]["version"]))

    def test_the_command_is_installed_by_the_meta_package_too(self):
        core = self.packages["braidworks-core"]
        self.assertEqual(self.meta["name"], "braidworks")
        self.assertEqual(self.meta["scripts"]["braidworks"], core["scripts"]["braidworks"])

    def test_every_dependency_resolves_to_the_workspace(self):
        sources = tomllib.loads((ROOT / "braidworks-meta/pyproject.toml").read_text())
        self.assertEqual(set(sources["tool"]["uv"]["sources"]), set(self.floors))


if __name__ == "__main__":
    unittest.main()
