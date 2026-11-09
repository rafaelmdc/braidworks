"""The getting-started notebook stays runnable: valid, clean, and on the public API."""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "notebooks/getting-started.ipynb"


def _code(cell: dict) -> str:
    return "".join(cell["source"])


class GettingStartedNotebookTests(unittest.TestCase):
    def setUp(self):
        self.notebook = json.loads(NOTEBOOK.read_text())
        self.code = [cell for cell in self.notebook["cells"] if cell["cell_type"] == "code"]

    def test_is_a_v4_notebook_saved_without_outputs(self):
        self.assertEqual(self.notebook["nbformat"], 4)
        for cell in self.code:
            self.assertEqual(cell["outputs"], [], _code(cell))
            self.assertIsNone(cell["execution_count"])

    def test_first_step_installs_the_package_index_release(self):
        self.assertEqual(_code(self.code[0]), '%pip install -q "braidworks[pandas]"')

    def test_colab_badge_points_at_this_file(self):
        intro = "".join(self.notebook["cells"][0]["source"])
        path = NOTEBOOK.relative_to(ROOT).as_posix()
        self.assertIn(
            f"colab.research.google.com/github/rafaelmdc/braidworks/blob/main/{path}", intro
        )

    def test_code_compiles_and_uses_only_public_braidworks_names(self):
        import braidworks as bw

        for cell in self.code[1:]:
            source = _code(cell)
            tree = ast.parse(source)  # no IPython magics after the install step
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "bw"
                ):
                    self.assertIn(node.attr, bw.__all__, source)

    def test_covers_install_find_get_review_and_export(self):
        text = "\n".join(_code(cell) for cell in self.code)
        for step in (r"bw\.find\(", r"bw\.get\(", r"\.choose\(", r"\.resume\(\)", r"\.to_csv\("):
            self.assertRegex(text, re.compile(step))


if __name__ == "__main__":
    unittest.main()
