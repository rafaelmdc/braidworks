"""The CLI reference must have one generated page per command, and --check catches drift."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_cli_docs


class GenCliDocsTests(unittest.TestCase):
    def test_one_page_per_command_plus_index(self):
        pages = gen_cli_docs.pages()
        names = {path.name for path in pages}
        for command in ("get", "run", "resume", "runs", "find", "serve", "keys", "path"):
            self.assertIn(f"{command}.md", names)
        self.assertIn("index.md", names)
        self.assertNotIn("weave.md", names)  # an alias, noted on get's page

    def test_pages_render_the_real_help(self):
        get = gen_cli_docs.pages()[gen_cli_docs.OUT / "get.md"]
        self.assertTrue(get.startswith("# braidworks get\n"))
        self.assertIn("Also available as `braidworks weave`", get)
        self.assertIn("usage: braidworks get ID… --have TYPE", get)
        self.assertIn("do not edit by hand", get)

    def test_check_passes_on_the_committed_pages(self):
        self.assertEqual(gen_cli_docs.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
