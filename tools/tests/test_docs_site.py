"""The docs site: every public page is in the navigation, and off-site links go to GitHub."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/mkdocs"))
from github_links import github_url


class NavigationTests(unittest.TestCase):
    def test_every_public_page_is_in_the_navigation(self):
        config = (ROOT / "mkdocs.yml").read_text()
        nav = set(re.findall(r"^\s*-\s+(?:[^:\n]+:\s+)?([\w./-]+\.md)\s*$", config, re.MULTILINE))
        pages = {
            path.relative_to(ROOT / "docs").as_posix()
            for path in (ROOT / "docs").rglob("*.md")
            if path.relative_to(ROOT / "docs").parts[0]
            not in {"internal", "superpowers", "diagrams"}
        }
        self.assertEqual(pages - nav, set(), "add these pages to the nav in mkdocs.yml")
        self.assertEqual(nav - pages, set(), "the nav names pages that do not exist")

    def test_the_four_diataxis_types_are_the_top_level(self):
        config = (ROOT / "mkdocs.yml").read_text()
        top = re.findall(r"^  - ([^:\n]+):", config.split("\nnav:\n", 1)[1], re.MULTILINE)
        self.assertEqual(top, ["Home", "Tutorials", "How-to guides", "Reference", "Explanation"])


class GithubLinkTests(unittest.TestCase):
    def url(self, page, target):
        return github_url(page, target)

    def test_published_pages_and_assets_stay_relative(self):
        self.assertIsNone(self.url("how-to/run-queries.md", "install.md"))
        self.assertIsNone(self.url("how-to/run-queries.md", "../reference/sources.md#backends"))
        self.assertIsNone(self.url("index.md", "network/braidworks-network.html"))
        self.assertIsNone(self.url("index.md", "#learn-through-a-tutorial"))
        self.assertIsNone(self.url("index.md", "https://example.org/x.md"))
        # a missing page stays relative, so the strict build reports it
        self.assertIsNone(self.url("how-to/index.md", "no-such-page.md"))

    def test_files_outside_docs_go_to_github(self):
        self.assertEqual(
            self.url("reference/sources.md", "../../weavers/pdbe_weaver/README.md#usage"),
            "https://github.com/rafaelmdc/braidworks/blob/main/weavers/pdbe_weaver/README.md#usage",
        )
        self.assertEqual(
            self.url("index.md", "../notebooks/getting-started.ipynb"),
            "https://github.com/rafaelmdc/braidworks/blob/main/notebooks/getting-started.ipynb",
        )

    def test_unpublished_records_and_folders_go_to_github(self):
        self.assertEqual(
            self.url("index.md", "internal/NEXT.md"),
            "https://github.com/rafaelmdc/braidworks/blob/main/docs/internal/NEXT.md",
        )
        self.assertEqual(
            self.url("how-to/implement-a-weaver.md", "../../weavers/ncbi_weaver/src/ncbi_weaver/"),
            "https://github.com/rafaelmdc/braidworks/tree/main/weavers/ncbi_weaver/src/ncbi_weaver",
        )


if __name__ == "__main__":
    unittest.main()
