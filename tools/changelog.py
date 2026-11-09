"""Per-package changelogs built from git history, and GitHub releases from them.

Each package (core, weaverkit, the meta-package, arq and every weaver) gets a
``CHANGELOG.md`` in its folder. Every change merged to ``main`` that touched the folder
becomes one entry (the pull request's title and number). Entries collect under
**Unreleased** until the package's version is bumped; the version's tag then closes
them into a dated version section. CI regenerates the files on each merge to ``main``
before tagging, so every tag carries its own section, then creates a GitHub release
for each new tag with that section as its notes.

    python tools/changelog.py write             # every package's CHANGELOG.md + the root one
    python tools/changelog.py notes TAG         # one version's section (release notes)
    python tools/changelog.py release           # GitHub releases for unreleased tags

The files are generated: edit pull-request titles, not the changelogs.
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/rafaelmdc/braidworks"
SKIP_SUBJECTS = ("chore(changelog)", "Merge branch ")
MERGE_PR = re.compile(r"^Merge pull request #(\d+) from \S+")


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    folder: str  # relative to the repository root


@dataclass(frozen=True)
class Section:
    title: str  # a version, or "Unreleased"
    date: str | None
    tag: str | None  # the tag closing this section, when it exists
    previous_tag: str | None
    entries: tuple[str, ...]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def packages(root: Path = ROOT) -> list[Package]:
    """Every versioned workspace package (the same set CI tags)."""
    paths = [
        root / name
        for name in ("braidworks-core", "weaverkit", "braidworks-arq", "braidworks-meta")
    ]
    paths += sorted(p.parent for p in (root / "weavers").glob("*/pyproject.toml"))
    out = []
    for path in paths:
        config = path / "pyproject.toml"
        if config.is_file():
            project = tomllib.loads(config.read_text())["project"]
            out.append(
                Package(project["name"], project["version"], path.relative_to(root).as_posix())
            )
    return out


def _version_key(version: str) -> tuple:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"[.]", version))


def _tags(root: Path, package: Package) -> list[str]:
    prefix = f"{package.name}-v"
    names = [t for t in _git(root, "tag", "-l", f"{prefix}*").split() if t.startswith(prefix)]
    return sorted(names, key=lambda tag: _version_key(tag[len(prefix) :]))


def _entry(subject: str, body: str) -> str | None:
    if subject.startswith(SKIP_SUBJECTS):
        return None
    match = MERGE_PR.match(subject)
    if match:
        title = next((line.strip() for line in body.splitlines() if line.strip()), "")
        return f"{title or subject} (#{match.group(1)})"
    return subject.strip()


def _entries(root: Path, package: Package, start: str | None, end: str) -> tuple[str, ...]:
    revisions = f"{start}..{end}" if start else end
    log = _git(
        root,
        "log",
        "--first-parent",
        "--format=%s%x1f%b%x1e",
        revisions,
        "--",
        package.folder,
        f":(exclude){package.folder}/CHANGELOG.md",
    )
    out = []
    for record in log.split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip("\n").partition("\x1f")
        entry = _entry(subject, body)
        if entry:
            out.append(entry)
    return tuple(out)


def sections(root: Path, package: Package, *, today: str | None = None) -> list[Section]:
    """Newest first. The head section is the current version when it is not tagged yet
    (CI tags it right after writing the changelog), otherwise ``Unreleased``."""
    tags = _tags(root, package)
    prefix = f"{package.name}-v"
    out: list[Section] = []
    previous = None
    for tag in tags:
        date = _git(root, "log", "-1", "--format=%cs", tag).strip()
        out.append(
            Section(tag[len(prefix) :], date, tag, previous, _entries(root, package, previous, tag))
        )
        previous = tag
    head_entries = _entries(root, package, previous, "HEAD")
    current_tag = f"{prefix}{package.version}"
    if current_tag not in tags:
        date = today or datetime.datetime.now(datetime.UTC).date().isoformat()
        out.append(Section(package.version, date, current_tag, previous, head_entries))
    else:
        out.append(Section("Unreleased", None, None, previous, head_entries))
    return list(reversed(out))


def _section_text(section: Section) -> str:
    lines = [f"- {entry}" for entry in section.entries] or ["- No changes recorded."]
    return "\n".join(lines)


def render(package: Package, items: list[Section]) -> str:
    parts = [
        f"# Changelog: {package.name}\n",
        (
            "Every change merged to `main` that touched this package, newest first. "
            "Generated by\n`tools/changelog.py` on each merge; edit pull-request titles, "
            "not this file.\n"
        ),
    ]
    for section in items:
        if section.title == "Unreleased" and not section.entries:
            continue
        heading = section.title if section.date is None else f"{section.title} ({section.date})"
        parts.append(f"## {heading}\n\n{_section_text(section)}\n")
    return "\n".join(parts)


def render_combined(per_package: list[tuple[Package, list[Section]]]) -> str:
    """One changelog for the repository: each release date, with the packages that
    released a version with changes that day; packages without changes are left out."""
    unreleased: list[tuple[Package, Section]] = []
    by_date: dict[str, list[tuple[Package, Section]]] = {}
    for package, items in per_package:
        for section in items:
            if not section.entries:
                continue
            if section.date is None:
                unreleased.append((package, section))
            else:
                by_date.setdefault(section.date, []).append((package, section))
    parts = [
        "# Changelog\n",
        (
            "Every package's changes, by release date, newest first. Each package also has\n"
            "its own `CHANGELOG.md`. Generated by `tools/changelog.py` on each merge to\n"
            "`main`; edit pull-request titles, not this file.\n"
        ),
    ]
    if unreleased:
        parts.append("## Unreleased\n")
        parts += [f"### {p.name}\n\n{_section_text(s)}\n" for p, s in unreleased]
    for date in sorted(by_date, reverse=True):
        parts.append(f"## {date}\n")
        parts += [f"### {p.name} {s.title}\n\n{_section_text(s)}\n" for p, s in by_date[date]]
    return "\n".join(parts)


def write(root: Path = ROOT, *, today: str | None = None) -> list[Path]:
    """Regenerate every package's ``CHANGELOG.md`` and the combined root one."""
    changed = []
    per_package = []
    for package in packages(root):
        items = sections(root, package, today=today)
        per_package.append((package, items))
        changed += _write_if_changed(root / package.folder / "CHANGELOG.md", render(package, items))
    changed += _write_if_changed(root / "CHANGELOG.md", render_combined(per_package))
    return changed


def _write_if_changed(path: Path, text: str) -> list[Path]:
    if path.is_file() and path.read_text() == text:
        return []
    path.write_text(text)
    return [path]


def notes(root: Path, tag: str) -> str:
    """The release notes for ``tag``: its changelog section and a compare link."""
    for package in packages(root):
        for section in sections(root, package):
            if section.tag == tag:
                text = _section_text(section)
                if section.previous_tag:
                    text += f"\n\n**Changes:** {REPO_URL}/compare/{section.previous_tag}...{tag}"
                return text + "\n"
    raise SystemExit(f"no changelog section for {tag}")


def release(root: Path = ROOT) -> list[str]:
    """Create a GitHub release for each package's current version tag that has none."""
    created = []
    remote_tags = _git(root, "ls-remote", "--tags", "origin")
    for package in packages(root):
        tag = f"{package.name}-v{package.version}"
        if f"refs/tags/{tag}" not in remote_tags:
            continue  # not tagged yet (a failed tag step); nothing to release
        exists = subprocess.run(
            ["gh", "release", "view", tag], cwd=root, capture_output=True, text=True, check=False
        )
        if exists.returncode == 0:
            continue
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--verify-tag",
                "--title",
                f"{package.name} {package.version}",
                "--notes",
                notes(root, tag),
                # The meta-package is what users install; it alone is marked latest.
                f"--latest={'true' if package.name == 'braidworks' else 'false'}",
            ],
            cwd=root,
            check=True,
        )
        created.append(tag)
        print(f"released {tag}")
    return created


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "write"
    if command == "write":
        for path in write():
            print(f"wrote {path.relative_to(ROOT)}")
        return 0
    if command == "notes" and len(argv) == 2:
        sys.stdout.write(notes(ROOT, argv[1]))
        return 0
    if command == "release":
        release()
        return 0
    print("usage: changelog.py write | notes TAG | release", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
