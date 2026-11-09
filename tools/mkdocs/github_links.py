"""MkDocs hook: links that leave the published docs point at GitHub instead.

The Markdown under docs/ is written to read correctly on GitHub, where a link such as
``../../weavers/pdbe_weaver/README.md`` resolves inside the repository. The site only
publishes docs/ (minus project records), so such links would break there. This hook
rewrites each relative link whose target is outside the published pages to the same
path on GitHub, leaving the source files unchanged.
"""

from __future__ import annotations

import posixpath
import re

REPO = "https://github.com/rafaelmdc/braidworks"
BRANCH = "main"
# Markdown inline links and images: ](target) or ](target "title")
LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
# Folders under docs/ that are project records, not published.
UNPUBLISHED = ("internal/", "superpowers/", "diagrams/")


def _is_relative(target: str) -> bool:
    return not re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", target, re.IGNORECASE)


def github_url(page_path: str, target: str) -> str | None:
    """The GitHub URL for ``target`` linked from ``page_path`` (docs-relative) when it
    leaves the published pages; ``None`` keeps the link for MkDocs to resolve."""
    path, _, anchor = target.partition("#")
    if not path or not _is_relative(target):
        return None
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(page_path), path))
    if not resolved.startswith("..") and not resolved.startswith(UNPUBLISHED):
        # A published page or asset; a missing one is left for MkDocs to report.
        return None
    repo_path = posixpath.normpath(posixpath.join("docs", resolved))
    kind = "tree" if path.endswith("/") or "." not in posixpath.basename(repo_path) else "blob"
    url = f"{REPO}/{kind}/{BRANCH}/{repo_path}"
    return f"{url}#{anchor}" if anchor else url


def on_page_markdown(markdown, page, config, files):
    def rewrite(match: re.Match) -> str:
        url = github_url(page.file.src_uri, match.group(2))
        return match.group(0) if url is None else f"{match.group(1)}{url}{match.group(3)}"

    out, fenced = [], False
    for line in markdown.splitlines(keepends=True):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        out.append(line if fenced else LINK.sub(rewrite, line))
    return "".join(out)
