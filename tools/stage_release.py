"""Select one validated wheel/sdist pair; require its exact package tag for publishing."""

from __future__ import annotations

import argparse
import shutil
import tomllib
from pathlib import Path


def stage_release(
    root: Path, package: str, artifacts: Path, destination: Path, *, ref: str | None = None
) -> list[Path]:
    projects = [root / name for name in ("braidworks-core", "weaverkit", "braidworks-arq")]
    projects.extend(sorted((root / "weavers").glob("*/pyproject.toml")))
    for path in projects:
        config_path = path if path.is_file() else path / "pyproject.toml"
        project = tomllib.loads(config_path.read_text())["project"]
        if project["name"] == package:
            break
    else:
        raise ValueError(f"unknown workspace package: {package}")
    expected_tag = f"refs/tags/{package}-v{project['version']}"
    if ref is not None and ref != expected_tag:
        raise ValueError(f"publishing requires {expected_tag}; got {ref}")
    stem = f"{package.replace('-', '_')}-{project['version']}"
    sources = [artifacts / f"{stem}-py3-none-any.whl", artifacts / f"{stem}.tar.gz"]
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(source)
    destination.mkdir(parents=True, exist_ok=False)
    for source in sources:
        shutil.copy2(source, destination / source.name)
    return [destination / source.name for source in sources]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--require-ref", help="exact GitHub tag ref; omitted for build-only rehearsal"
    )
    args = parser.parse_args()
    for path in stage_release(
        Path(__file__).resolve().parents[1],
        args.package,
        args.artifacts,
        args.destination,
        ref=args.require_ref,
    ):
        print(path)


if __name__ == "__main__":
    main()
