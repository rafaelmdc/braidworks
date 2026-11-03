"""The quickstart checker must read the README's real commands and route-check them."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_quickstart import ROOT, offline_variant, quickstart_commands

README = """# X

## Try one query

```bash
git clone https://example.test/repo
cd repo
uv sync --all-extras
uv run braidworks weave --have protein.query=P04637 \\
    --want protein.name,structure.pdb.ids
```

```bash
not-this-block
```
"""


class QuickstartCheckTests(unittest.TestCase):
    def test_extracts_commands_and_joins_continuations(self):
        self.assertEqual(
            quickstart_commands(README),
            [
                "uv sync --all-extras",
                (
                    "uv run braidworks weave --have protein.query=P04637 "
                    "--want protein.name,structure.pdb.ids"
                ),
            ],
        )

    def test_offline_variant_turns_weave_into_path(self):
        self.assertEqual(
            offline_variant(
                "uv run braidworks weave --have protein.query=P04637 --want a.b,c.d --format tsv"
            ),
            "uv run braidworks path --from protein.query --to a.b,c.d",
        )
        self.assertEqual(offline_variant("uv sync --all-extras"), "uv sync --all-extras")

    def test_real_readme_has_a_runnable_quickstart(self):
        commands = quickstart_commands((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertTrue(any("braidworks weave" in c for c in commands))
        self.assertFalse(any("--package" in c for c in commands), "install every source")
        for command in commands:
            offline_variant(command)  # every weave must be route-checkable


if __name__ == "__main__":
    unittest.main()
