"""The Python API reference renders docstrings faithfully."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gen_python_api import render_docstring


class RenderDocstringTests(unittest.TestCase):
    def test_args_become_a_list_with_continuations_joined(self):
        doc = """Do a thing.

        Args:
            ids: One value or
                many values.
            **parameters: Extra knobs.
        """
        out = render_docstring(doc)
        self.assertIn("**Args:**", out)
        self.assertIn("- `ids`: One value or many values.", out)
        self.assertIn("- `**parameters`: Extra knobs.", out)

    def test_rest_markup_and_examples_become_markdown(self):
        doc = """Use ``x`` with :class:`Result`.

        Example::

            bw.get(["P1"])
        """
        out = render_docstring(doc)
        self.assertIn("Use `x` with `Result`.", out)
        self.assertIn('```python\nbw.get(["P1"])\n```', out)


if __name__ == "__main__":
    unittest.main()
