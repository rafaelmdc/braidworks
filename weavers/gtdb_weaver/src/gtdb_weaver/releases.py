"""Pinned GTDB bundles; only small VERSION/checksum manifests are fetched here."""

import hashlib
import re
import urllib.request
from pathlib import Path

DEFAULT_RELEASE = "R232"


def release_sources(release: str) -> dict[str, str]:
    match = re.fullmatch(r"[RrvV]?(\d+)", release)
    if not match:
        raise ValueError("GTDB official release must be R<number>")
    number = match[1]
    base = f"https://data.gtdb.ecogenomic.org/releases/release{number}/{number}.0"
    return {
        "bac120": f"{base}/bac120_metadata_r{number}.tsv.gz",
        "ar53": f"{base}/ar53_metadata_r{number}.tsv.gz",
        "bac120_tree": f"{base}/bac120_r{number}.tree",
        "ar53_tree": f"{base}/ar53_r{number}.tree",
    }


def _read_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def release_bundle(release: str) -> dict:
    sources = release_sources(release)
    base = sources["bac120"].rsplit("/", 1)[0]
    number = re.search(r"release(\d+)/", base)[1]
    observed = _read_text(f"{base}/VERSION.txt").split()[0]
    if observed.lower() not in {f"v{number}", f"r{number}", number}:
        raise ValueError(
            f"GTDB release manifest mismatch: requested R{number}, observed {observed}"
        )
    sums = {}
    for line in _read_text(f"{base}/MD5SUM.txt").splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{32}", parts[0]):
            sums[parts[1].lstrip("*./")] = parts[0].lower()
    resources = {}
    for label, url in sources.items():
        name = url.rsplit("/", 1)[1]
        if name not in sums:
            raise ValueError(f"GTDB checksum manifest lacks {name}")
        resources[label] = {"url": url, "md5": sums[name]}
    return {
        "kind": "official-release",
        "release": f"R{number}",
        "version_observed": observed,
        "manifest_url": f"{base}/MD5SUM.txt",
        "resources": resources,
    }


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def verify_resource(path: Path, descriptor: dict) -> dict:
    if descriptor.get("md5") and file_hash(path, "md5") != descriptor["md5"]:
        raise ValueError(f"GTDB checksum mismatch for {path.name}")
    return {**descriptor, "sha256": file_hash(path)}
