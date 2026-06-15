"""Per-package release tags: list / check / create `<name>-v<version>` tags.

Every workspace package is tagged at the commit that released its current version
(see the versioning policy). This derives the expected tag for each package from its
``pyproject.toml`` and can report or create the ones that are missing — so the manual
"remember to tag the bump" step (build-notes finding #21) can't be silently skipped.

Usage:
    python tools/release_tags.py list      # print every expected <name>-v<version>
    python tools/release_tags.py missing   # print tags not present locally; exit 1 if any
    python tools/release_tags.py create     # create annotated + push the missing tags

The CI workflow runs ``create`` on push to main; ``make tag`` and humans can run any.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _package_dirs(root: Path) -> list[str]:
    """The uv workspace members that ship as versioned packages."""
    return ["braidworks-core", "weaverkit", "braidworks-arq", *sorted(
        str(p.parent.relative_to(root)) for p in (root / "weavers").glob("*/pyproject.toml")
    )]


def expected_tags(root: Path = ROOT) -> list[tuple[str, Path]]:
    """(tag, package_dir) for every package that declares a [project] name+version."""
    tags: list[tuple[str, Path]] = []
    for rel in _package_dirs(root):
        pyproject = root / rel / "pyproject.toml"
        if not pyproject.is_file():
            continue
        project = tomllib.loads(pyproject.read_text()).get("project", {})
        name, version = project.get("name"), project.get("version")
        if name and version:
            tags.append((f"{name}-v{version}", root / rel))
    return tags


def _local_tags() -> set[str]:
    out = subprocess.run(
        ["git", "tag", "-l"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return set(out.stdout.split())


def _parse_ls_remote(text: str) -> set[str]:
    """Tag names from ``git ls-remote --tags`` output (drops ``^{}`` peeled refs)."""
    tags: set[str] = set()
    for line in text.splitlines():
        ref = line.split()[-1] if line.split() else ""
        if ref.startswith("refs/tags/"):
            name = ref[len("refs/tags/") :]
            tags.add(name[:-3] if name.endswith("^{}") else name)
    return tags


def _remote_tags() -> set[str]:
    """Tags already on ``origin``. Tolerant: returns empty if the remote is unreachable
    (offline / no remote), so the caller falls back to local-only behaviour."""
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--tags", "origin"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return set()
    return _parse_ls_remote(out.stdout)


def _existing_tags() -> set[str]:
    """Tags that exist locally *or* on the remote — so an already-pushed tag from a
    prior run is never re-created (the idempotency the CI workflow needs)."""
    return _local_tags() | _remote_tags()


def _missing() -> list[str]:
    have = _existing_tags()
    return [tag for tag, _ in expected_tags() if tag not in have]


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        for tag, _ in expected_tags():
            print(tag)
        return 0
    if cmd == "missing":
        missing = _missing()
        for tag in missing:
            print(tag)
        return 1 if missing else 0
    if cmd == "create":
        missing = _missing()
        if not missing:
            print("all package versions are already tagged")
            return 0
        local = _local_tags()
        for tag in missing:
            if tag not in local:
                subprocess.run(
                    ["git", "tag", "-a", tag, "-m", tag.replace("-v", " ")],
                    cwd=ROOT, check=True,
                )
            push = subprocess.run(
                ["git", "push", "origin", tag], cwd=ROOT, capture_output=True, text=True
            )
            if push.returncode != 0:
                # A concurrent merge may have pushed it between our check and now — that
                # is success, not failure. Anything else is a real error.
                blob = push.stderr + push.stdout
                if "already exists" in blob or "[rejected]" in blob:
                    print(f"{tag} already on remote; skipping")
                    continue
                print(blob.strip(), file=sys.stderr)
                raise SystemExit(f"failed to push {tag}")
            print(f"created + pushed {tag}")
        return 0
    print(f"unknown command {cmd!r}; use list | missing | create", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
