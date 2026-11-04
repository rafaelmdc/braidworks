"""Check that relative links in tracked Markdown files resolve.

Every ``[text](path)`` and ``[ref]: path`` link that points inside the repository must
name an existing file or directory; a ``#anchor`` on a Markdown target must match one of
that page's headings (GitHub's slug rules). External links (``https:``, ``mailto:``) are
not fetched.

    python tools/check_links.py            # all tracked Markdown
    python tools/check_links.py docs       # only files under these paths
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"")


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, drop punctuation, spaces to hyphens."""
    text = re.sub(r"`|\*\*|__|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


@cache
def anchors(path: Path) -> frozenset[str]:
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    found = set(EXPLICIT_ANCHOR.findall(text))
    for heading in HEADING.findall(text):
        base = slug(heading)
        count = seen.get(base, 0)
        found.add(base if count == 0 else f"{base}-{count}")
        seen[base] = count + 1
    return frozenset(found)


def markdown_files(prefixes: list[str]) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md", "**/*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    files = sorted(set(out.stdout.split()))
    if prefixes:
        files = [f for f in files if any(f.startswith(p.rstrip("/")) for p in prefixes)]
    return [ROOT / f for f in files]


def check_file(path: Path) -> list[str]:
    problems = []
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), path.read_text(encoding="utf-8"))
    for match in LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if re.match(r"^[a-zA-Z][a-zA-Z+.-]*:", target) or target.startswith(("<", "/")):
            continue
        file_part, _, anchor = target.partition("#")
        line = text.count("\n", 0, match.start()) + 1
        where = f"{path.relative_to(ROOT)}:{line}"
        resolved = (path.parent / file_part).resolve() if file_part else path
        if not resolved.exists():
            problems.append(f"{where}: missing target {target}")
            continue
        if anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            problems.append(f"{where}: no heading for #{anchor} in {file_part or 'this page'}")
    return problems


def main(argv: list[str]) -> int:
    problems = [p for f in markdown_files(argv) for p in check_file(f)]
    for problem in problems:
        print(problem)
    print(f"{len(problems)} broken link(s)" if problems else "all links resolve")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
