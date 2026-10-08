"""Check distributions and rehearse installation without workspace overrides.

Build first with: uv build --all-packages --out-dir /tmp/braidworks-artifacts
Then: python tools/check_artifacts.py /tmp/braidworks-artifacts --python python3.12
The temporary environment is removed on exit; nothing is published.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import os
import re
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path


def run(argv: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(argv, cwd=cwd, env=env, check=True)


def check_core_requirement(project: Path, config: dict) -> None:
    """Reject floors older than known runtime APIs, including manifest fields.

    This catches metadata regressions; clean minimum-version golden runs remain
    necessary when a new API or constructor argument is introduced.
    """
    metadata = config["project"]
    if metadata["name"] == "braidworks-core":
        return
    requirements = [
        dependency
        for dependency in metadata.get("dependencies", [])
        if dependency.startswith("braidworks-core")
    ]
    assert len(requirements) == 1, (project, "declare exactly one core dependency")
    match = re.fullmatch(r"braidworks-core>=([0-9]+\.[0-9]+\.[0-9]+)", requirements[0])
    assert match, (project, "declare a core floor without a ceiling", requirements)
    declared = tuple(map(int, match.group(1).split(".")))
    required = (0, 1, 8)  # WeaverManifest.title / always_computed_groups
    spec_path = project / "weaver.spec.toml"
    if spec_path.exists():
        spec = tomllib.loads(spec_path.read_text())
        for capability in spec.get("capability", []):
            for field, floor in (
                ("set_outputs", (0, 2, 1)),
                ("parameter", (0, 4, 0)),
                ("consumes_any", (0, 8, 0)),
            ):
                if capability.get(field):
                    required = max(required, floor)
    if metadata["name"] == "weaverkit":
        required = (0, 13, 0)  # shared batch parser and traversal progress
    if metadata["name"] == "braidworks-arq":
        required = (0, 13, 0)  # per-request budget context
    for source in (project / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "LookupRecord"
                and any(keyword.arg == "warnings" for keyword in node.keywords)
            ):
                required = max(required, (0, 12, 0))
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith("braidworks.core"):
                continue
            if node.module in {"braidworks.core.http_pacing", "braidworks.core.inputs"}:
                required = max(required, (0, 13, 0))
            for symbol in node.names:
                if symbol.name in {
                    "DiscoveryFailure",
                    "DiscoveryPolicy",
                    "DiscoveryReport",
                    "discover_registry",
                }:
                    required = max(required, (0, 21, 0))
                if symbol.name == "format_exc":
                    required = max(required, (0, 7, 1))
                if symbol.name == "map_bounded":
                    required = max(required, (0, 12, 0))
                if symbol.name == "USER_AGENT":
                    required = max(required, (0, 11, 2))
    assert declared >= required, (project, "core floor too low", declared, required)


def check_contents(root: Path, artifacts: Path) -> list[Path]:
    projects = [root / "braidworks-core", root / "braidworks-arq", root / "weaverkit"]
    projects.extend(sorted((root / "weavers").glob("*/pyproject.toml")))
    wheels = []
    for project in projects:
        if project.is_file():
            project = project.parent
        config = tomllib.loads((project / "pyproject.toml").read_text())
        check_core_requirement(project, config)
        metadata = config["project"]
        name = metadata["name"].replace("-", "_")
        version = metadata["version"]
        wheel = artifacts / f"{name}-{version}-py3-none-any.whl"
        sdist = artifacts / f"{name}-{version}.tar.gz"
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            info_dir = f"{name}-{version}.dist-info"
            parsed = Parser().parsestr(archive.read(f"{info_dir}/METADATA").decode())
            assert parsed["Version"] == version, wheel
            for label, url in metadata.get("urls", {}).items():
                assert f"{label}, {url}" in parsed.get_all("Project-URL", []), wheel
            for requirement in metadata.get("dependencies", []):
                if requirement.startswith("braidworks-core"):
                    assert requirement in parsed.get_all("Requires-Dist", []), wheel
            assert parsed["License-Expression"] == metadata["license"] == "MIT", wheel
            assert "LICENSE" in parsed.get_all("License-File", []), wheel
            assert (
                archive.read(f"{info_dir}/licenses/LICENSE") == (project / "LICENSE").read_bytes()
            )
            entry_file = f"{info_dir}/entry_points.txt"
            actual = configparser.ConfigParser()
            if entry_file in names:
                actual.read_string(archive.read(entry_file).decode())
            for group, entries in metadata.get("entry-points", {}).items():
                assert dict(actual[group]) == entries, (wheel, group)
            for command, target in metadata.get("scripts", {}).items():
                assert actual["console_scripts"][command] == target, (wheel, command)
            # Include source modules and small bundled resources, especially data/.
            for source in (project / "src").rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts:
                    relative = source.relative_to(project / "src").as_posix()
                    assert relative in names, (wheel, relative)
        with tarfile.open(sdist, "r:gz") as archive:
            names = set(archive.getnames())
            prefix = f"{name}-{version}"
            assert f"{prefix}/pyproject.toml" in names, sdist
            assert f"{prefix}/{metadata['readme']}" in names, sdist
            assert f"{prefix}/LICENSE" in names, sdist
            for source in (project / "src").rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts:
                    relative = source.relative_to(project).as_posix()
                    assert f"{prefix}/{relative}" in names, (sdist, relative)
        wheels.append(wheel)
    print(f"Verified wheel/sdist contents for {len(wheels)} packages.", flush=True)
    return wheels


SMOKE = """
import asyncio
import importlib.metadata
import json
import sys
from pathlib import Path
from braidworks.core import Strand, StrandSet, WeaveStatus
from example_weaver.factory import build_example_weaver
from weaverkit.serve import create_app

async def main():
    weaver = build_example_weaver()
    result = await weaver.execute_batch(
        "describe_traits",
        [StrandSet.from_strands("sample", [Strand("ncbi.taxon.id", "562")])],
        requested_outputs=frozenset({"microbe.trait.gram_stain"}),
        backend="local",
    )
    assert len(result) == 1 and result[0].status is WeaveStatus.OK
    assert next(s.value for s in result[0].strands if s.type_id == "microbe.trait.gram_stain") == "negative"
    import braidworks.core, weaverkit, example_weaver
    for module in (braidworks.core, weaverkit, example_weaver):
        assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
    app = create_app()
    assert any(route.path == "/api/run" for route in app.routes)
    plugins = importlib.metadata.entry_points(group="braidworks.weavers")
    assert "pdbe" in {plugin.name for plugin in plugins}
    assert "example" not in {plugin.name for plugin in plugins}  # teaching reference
    print(json.dumps({"bundled_fixture": "OK", "server": "OK", "plugins": len(plugins)}))

asyncio.run(main())
from braidworks.core import cli, BraidRegistry
registry = BraidRegistry()
registry.register(build_example_weaver())
cli.build_registry_from_entry_points = lambda only=None: registry
archive_path = Path("packaged-run.json")
assert cli.main(["run", "example", "describe_traits", "--have", "ncbi.taxon.id=562",
                 "--archive", str(archive_path), "--format", "json"]) == 0
archive = json.loads(archive_path.read_text())
assert archive["schema"] == "braidworks.run-archive.v1"
assert archive["records"][0]["status"] == "resolved"
assert archive["execution"]["direct_results"][0]["status"] == "ok"
print("Packaged CLI run archive: OK")
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--python", default="3.12")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    wheels = check_contents(root, args.artifacts.resolve())
    with tempfile.TemporaryDirectory(prefix="braidworks-artifacts-") as directory:
        scratch = Path(directory)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["BRAIDWORKS_DATA_DIR"] = str(scratch / "data")
        venv = scratch / "venv"
        run(["uv", "venv", "--python", args.python, str(venv)], cwd=scratch, env=env)
        python = venv / "bin/python"
        run(
            ["uv", "pip", "install", "--python", str(python), *map(str, wheels)],
            cwd=scratch,
            env=env,
        )
        toolkit = next(wheel for wheel in wheels if wheel.name.startswith("weaverkit-"))
        run(
            ["uv", "pip", "install", "--python", str(python), f"{toolkit}[serve]"],
            cwd=scratch,
            env=env,
        )
        run([str(python), "-c", SMOKE], cwd=scratch, env=env)
        run([str(venv / "bin/braidworks"), "keys", "--only", "pdbe"], cwd=scratch, env=env)
        run([str(venv / "bin/weaverkit"), "--help"], cwd=scratch, env=env)


if __name__ == "__main__":
    main()
