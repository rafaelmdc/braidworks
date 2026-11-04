"""Bounded header-only discovery in caller-acquired, uncompressed proteome TARs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tarfile
from copy import deepcopy
from pathlib import Path, PurePosixPath
from threading import RLock

from braidworks.core import BackendBase, BackendConfigurationError, LookupRecord

_MODEL_NAME = re.compile(
    r"(AF-([A-Z0-9]+(?:-[0-9]+)?)-F([1-9][0-9]*))-model_v([1-9][0-9]*)\.(cif|pdb)\.gz"
)


class ArchiveFormatError(ValueError):
    """Archive identity/format cannot establish a model listing."""


class _HeaderLimit(ValueError):
    """The explicitly configured header byte budget was exhausted."""


class _HeaderReader:
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
        self.observed = 0
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        remaining = self.limit - self.observed
        if remaining < 0:
            raise _HeaderLimit("archive header byte cap")
        data = self.stream.read(min(size, remaining + 1) if size >= 0 else remaining + 1)
        self.observed += len(data)
        if self.observed > self.limit:
            raise _HeaderLimit("archive header byte cap")
        self.digest.update(data)
        return data

    def seek(self, *args):
        return self.stream.seek(*args)

    def tell(self):
        return self.stream.tell()


def _state(path):
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]


def index_archive(path: str | Path, *, max_members=100_000, max_header_bytes=64 * 1024 * 1024):
    """Read headers, seeking over model bodies; never decompress/extract coordinates."""
    path = Path(path).resolve()
    before = _state(path)
    entries, scanned, reason = [], 0, None
    with path.open("rb") as stream:
        reader = _HeaderReader(stream, max_header_bytes)
        try:
            # Official proteome archives have an uncompressed outer TAR. Do not turn
            # a compressed outer archive into a silent multi-GB decompression pass.
            with tarfile.open(fileobj=reader, mode="r:") as archive:
                while scanned < max_members:
                    member = archive.next()
                    if member is None:
                        break
                    scanned += 1
                    if not member.isfile():
                        continue
                    name = PurePosixPath(member.name)
                    if name.is_absolute() or ".." in name.parts:
                        raise ArchiveFormatError("Unsafe archive member path")
                    match = _MODEL_NAME.fullmatch(name.name)
                    if match:
                        if member.offset_data + member.size > before[0]:
                            raise ArchiveFormatError("Truncated model member")
                        entries.append(
                            {
                                "entry_id": match[1],
                                "accession": match[2],
                                "fragment_number": int(match[3]),
                                "version": int(match[4]),
                                "format": match[5],
                                "member": member.name,
                                "size_bytes": member.size,
                                "offset_bytes": member.offset_data,
                            }
                        )
                else:
                    reason = "member_cap"
        except _HeaderLimit:
            reason = "header_byte_cap"
        except tarfile.TarError as exc:
            raise ArchiveFormatError("Expected an intact uncompressed proteome TAR") from exc
    if _state(path) != before:
        raise ArchiveFormatError("Archive changed during indexing")
    return {
        "archive_path": str(path),
        "file_state": before,
        "header_sha256": reader.digest.hexdigest(),
        "header_bytes_read": reader.observed,
        "members_scanned": scanned,
        "complete": reason is None,
        "reason": reason,
        "models": entries,
        "scope": "matching UniProt fragment/isoform model filenames in this supplied archive; no archive-wide coordinate hash or global catalogue completeness claim",
    }


class AlphafoldArchiveBackend(BackendBase):
    name = "archive"

    def __init__(
        self, archive_paths=None, *, max_members=100_000, max_header_bytes=64 * 1024 * 1024
    ):
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in (max_members, max_header_bytes)
        ):
            raise BackendConfigurationError(
                "Archive member/header byte limits must be positive integers"
            )
        self._paths = tuple(Path(path).resolve() for path in archive_paths or ())
        self._max_members, self._max_header_bytes = max_members, max_header_bytes
        self._sources = None
        self._models = None
        self._lock = RLock()

    def is_configured(self):
        return bool(self._paths) and all(path.is_file() for path in self._paths)

    def _index(self):
        if not self.is_configured():
            raise BackendConfigurationError("Supply existing uncompressed proteome archive_paths")
        with self._lock:
            if self._sources is not None:
                if any(
                    _state(path) != source["file_state"]
                    for path, source in zip(self._paths, self._sources)
                ):
                    raise ArchiveFormatError(
                        "Archive changed; construct a new backend to rebuild its index"
                    )
                return
            sources = [
                index_archive(
                    path, max_members=self._max_members, max_header_bytes=self._max_header_bytes
                )
                for path in self._paths
            ]
            models = {}
            for source in sources:
                for row in source["models"]:
                    identity = f"{row['entry_id']}@v{row['version']}"
                    model = models.setdefault(
                        identity,
                        {
                            "model_id": identity,
                            "entry_id": row["entry_id"],
                            "accession": row["accession"],
                            "fragment_number": row["fragment_number"],
                            "version": row["version"],
                            "artifacts": [],
                        },
                    )
                    if any(artifact["format"] == row["format"] for artifact in model["artifacts"]):
                        raise ArchiveFormatError(
                            f"Conflicting archive artifact identity {identity}"
                        )
                    model["artifacts"].append(
                        {
                            **row,
                            "archive_path": source["archive_path"],
                            "header_sha256": source["header_sha256"],
                        }
                    )
            self._sources, self._models = sources, models

    def fingerprint(self):
        if not self.is_configured():
            return "unconfigured:alphafold-archive"
        try:
            self._index()
        except (ArchiveFormatError, OSError) as exc:
            raise BackendConfigurationError(
                f"AlphaFold archive cannot establish source identity: {exc}"
            ) from exc
        return (
            "alphafold-archive:"
            + hashlib.sha256(json.dumps(self._sources, sort_keys=True).encode()).hexdigest()
        )

    async def fetch(
        self, capability_id, queries, *, requested_outputs, groups_to_compute, params=None
    ):
        return await asyncio.to_thread(self._fetch, capability_id, queries, groups_to_compute)

    def _fetch(self, capability_id, queries, groups):
        try:
            self._index()
        except (ArchiveFormatError, OSError) as exc:
            return [
                LookupRecord(query=query, error=f"AlphaFold archive error: {exc}")
                for query in queries
            ]
        sources = [
            {key: value for key, value in source.items() if key != "models"}
            for source in self._sources
        ]
        complete = all(source["complete"] for source in sources)
        warnings = (
            ()
            if complete
            else ("AlphaFold archive listing incomplete: configured header/member cap reached",)
        )
        records = []
        for query in queries:
            if capability_id == "describe_prediction":
                identity = query.get("structure.alphafold.model_id")
                selected = (
                    [self._models[identity]]
                    if isinstance(identity, str) and identity in self._models
                    else []
                )
            else:
                accession = str(query.get("protein.uniprot.accession") or "").strip().upper()
                selected = [
                    model
                    for model in self._models.values()
                    if accession
                    and (
                        model["accession"] == accession
                        or re.fullmatch(re.escape(accession) + r"-[0-9]+", model["accession"])
                    )
                ]
            selected.sort(key=lambda model: model["model_id"])
            if not selected:
                records.append(
                    LookupRecord(query=query, found=False)
                    if complete
                    else LookupRecord(
                        query=query,
                        error="No observed model before archive scan cap; absence cannot be established",
                    )
                )
                continue
            coverage = {
                "scope": "supplied archive model filenames only; residue ranges not acquired",
                "observed_models": len(selected),
                "display_limit": 10,
                "displayed_models": min(10, len(selected)),
                "source_complete": complete,
                "sources": deepcopy(sources),
            }
            if capability_id == "list_models":
                values = {
                    "structure.alphafold.model_id": [model["model_id"] for model in selected],
                    "structure.alphafold.models": deepcopy(selected[:10]),
                    "structure.alphafold.model_coverage": coverage,
                }
            else:
                if capability_id == "describe_model":
                    canonical = f"AF-{query.get('protein.uniprot.accession')}-F1"
                    selected.sort(
                        key=lambda model: (
                            model["entry_id"] != canonical,
                            model["entry_id"],
                            -model["version"],
                        )
                    )
                model = deepcopy(selected[0])
                model["coverage"] = {
                    "status": "unknown",
                    "fragment_number": model["fragment_number"],
                    "uniprot_start": None,
                    "uniprot_end": None,
                    "sequence_length": None,
                }
                model["source"] = deepcopy(sources)
                values = {
                    "structure.alphafold.entry_id": model["entry_id"],
                    "structure.alphafold.version": model["version"],
                    "structure.alphafold.records": model,
                }
                if "confidence" in groups:
                    values["structure.alphafold.confidence"] = {
                        "entry_id": model["entry_id"],
                        "version": model["version"],
                        "available": False,
                        "scope": "archive headers only; residue confidence not parsed",
                        "coverage": model["coverage"],
                    }
            records.append(LookupRecord(query=query, found=True, values=values, warnings=warnings))
        return records
