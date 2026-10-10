"""The local backend for agora_weaver — bundled crosswalk + optional reaction DB.

``core`` (the reconstruction id + source genome) is served entirely from the bundled
``agora2_crosswalk.tsv`` — offline, all 7,302 strains. ``reactions`` (the repertoire)
needs the SQLite that ``setup.ensure_agora_db`` builds from the AGORA2 SBML archive;
when that DB is absent, core-only requests work and requested reactions return
an explicit resource error.

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from braidworks.core import BackendBase, LookupRecord
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.localdb import auto_consented
from braidworks.core.source_identity import SourceBinding, artifact_stamp

from agora_weaver import dataset
from agora_weaver.setup import DEFAULT_INDIVIDUAL_SBML_BASE, InvalidSBML, validate_model_sbml


class _ResourceUnavailable(ValueError):
    """A requested local resource is absent."""


class AgoraLocalBackend(BackendBase):
    """local backend — NCBI taxid -> AGORA2 reconstruction(s) (+ reaction repertoire)."""

    name = "local"

    def __init__(
        self,
        reaction_db_path: str | Path | None = None,
        *,
        sbml_cache_dir: str | Path | None = None,
        auto_download_models: bool = False,
        model_download_base_url: str = DEFAULT_INDIVIDUAL_SBML_BASE,
    ) -> None:
        if not isinstance(model_download_base_url, str):
            raise BackendConfigurationError("model_download_base_url must be an HTTP URL")
        try:
            endpoint = urlsplit(model_download_base_url)
        except ValueError as exc:
            raise BackendConfigurationError("model_download_base_url must be an HTTP URL") from exc
        if endpoint.scheme not in {"http", "https"} or not endpoint.netloc:
            raise BackendConfigurationError("model_download_base_url must be an HTTP URL")
        if model_download_base_url != DEFAULT_INDIVIDUAL_SBML_BASE and (
            endpoint.query or endpoint.fragment
        ):
            raise BackendConfigurationError(
                "Configured model_download_base_url must be an XML directory without query or fragment"
            )
        # ``None`` = "the default reaction-DB path, present-or-not"; core works either way.
        self._reaction_db_path = (
            Path(reaction_db_path) if reaction_db_path is not None else _default_db_path()
        )
        # Where per-model SBML files are cached, and whether a missing one may be downloaded
        # on demand (the ``model`` group; each model is ~8 MB).
        self._sbml_cache_dir = Path(sbml_cache_dir) if sbml_cache_dir is not None else None
        self._auto_download_models = auto_download_models
        self._model_download_base_url = model_download_base_url
        self._source = SourceBinding(
            self._reaction_db_path, lambda con: dict(con.execute("SELECT key, value FROM meta"))
        )
        self._expected_reaction_stamp = None
        self._generation_bound = False

    def is_configured(self) -> bool:
        # The bundled crosswalk always ships, so ``core`` is always answerable.
        return True

    def _reaction_db_ready(self) -> bool:
        return self._reaction_db_path.exists() and self._reaction_db_path.stat().st_size > 0

    def fingerprint(self) -> str:
        self._check_generation()
        rxn = self._source.fingerprint() if self._reaction_db_ready() else "no-reactions"
        from agora_weaver.setup import default_sbml_cache_dir

        directory = (
            self._sbml_cache_dir if self._sbml_cache_dir is not None else default_sbml_cache_dir()
        )
        state = {
            "directory": str(directory.resolve()),
            "auto_download": auto_consented(self._auto_download_models),
            "download_base_url": self._model_download_base_url,
            "artifacts": [
                (path.name, artifact_stamp(path)) for path in sorted(directory.glob("*.xml"))
            ],
        }
        model_state = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        return f"agora-local-{dataset.CROSSWALK_RELEASE}-{rxn}-models-{model_state}"

    def _check_generation(self) -> None:
        stamp = artifact_stamp(self._reaction_db_path) if self._reaction_db_ready() else None
        if self._generation_bound and stamp != self._expected_reaction_stamp:
            raise BackendConfigurationError("Reaction source changed; reopen the backend")
        self._expected_reaction_stamp = stamp
        self._generation_bound = True

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        if capability_id in {"list_genomes", "list_reactions", "describe_reaction"}:
            return await asyncio.to_thread(self._bridge_queries, capability_id, queries)
        if capability_id in {"list_reconstructions", "describe_reconstruction"}:
            return await asyncio.to_thread(
                self._fetch_sync, queries, groups_to_compute, capability_id
            )
        return await asyncio.to_thread(self._fetch_sync, queries, groups_to_compute)

    def _bridge_queries(self, capability, queries):
        self._check_generation()
        wants_reactions = capability in {"list_reactions", "describe_reaction"}
        if wants_reactions and not self._reaction_db_ready():
            return [
                LookupRecord(query=q, error="AGORA reaction database unavailable") for q in queries
            ]
        with self._source.session() if wants_reactions else nullcontext(None) as con:
            metadata = dict(con.execute("SELECT key,value FROM meta")) if con else {}
            if wants_reactions and metadata.get("release") != dataset.CROSSWALK_RELEASE:
                return [
                    LookupRecord(
                        query=q,
                        error="AGORA reaction database release does not match the pinned crosswalk",
                    )
                    for q in queries
                ]
            results = []
            for query in queries:
                try:
                    if capability == "describe_reaction":
                        abbreviation = str(query.get("reaction.vmh.id") or "")
                        row = con.execute(
                            "SELECT abbreviation,subsystem,ec,kegg,rhea FROM rxn_info WHERE abbreviation=?",
                            (abbreviation,),
                        ).fetchone()
                        memberships = [
                            r[0]
                            for r in con.execute(
                                "SELECT reconstruction FROM reaction WHERE abbreviation=? ORDER BY reconstruction",
                                (abbreviation,),
                            )
                        ]
                        if row is None and not memberships:
                            results.append(LookupRecord(query=query, found=False))
                            continue
                        values = {
                            "reaction.vmh.record": {
                                "id": abbreviation,
                                "annotations": dict(
                                    zip(("abbreviation", "subsystem", "ec", "kegg", "rhea"), row)
                                )
                                if row
                                else None,
                                "observed_reconstructions": memberships,
                                "source_release": metadata.get("release"),
                                "source_content_hash": metadata.get("content_hash"),
                                "annotation_source": metadata.get("annotation_source"),
                                "scope": "observed VMH abbreviation and source annotations; no inferred cross-reference equivalence",
                            }
                        }
                    else:
                        key = str(query.get("microbe.agora.reconstruction_id") or "")
                        release, separator, identifier = key.partition(":")
                        if not separator or release != dataset.CROSSWALK_RELEASE:
                            results.append(
                                LookupRecord(
                                    query=query,
                                    error="AGORA reconstruction ID must match the bundled release-qualified identity",
                                )
                            )
                            continue
                        associations = dataset.reconstruction_for(identifier)
                        if not associations:
                            results.append(LookupRecord(query=query, found=False))
                            continue
                        if capability == "list_genomes":
                            ids = sorted({row["gcf_id"] for row in associations if row["gcf_id"]})
                            values = {
                                "genome.accession": ids,
                                "microbe.agora.genome_listing": {
                                    "source_associations": associations,
                                    "observed_count": len(ids),
                                    "release": release,
                                    "scope": "exact crosswalk model/strain assembly associations",
                                },
                            }
                        else:
                            rows = dataset.reactions_for(con, [identifier])
                            ids = sorted({row["abbreviation"] for row in rows})
                            values = {
                                "reaction.vmh.id": ids,
                                "microbe.agora.reaction_listing": {
                                    "records": rows[:10],
                                    "observed_count": len(ids),
                                    "release": metadata.get("release"),
                                    "source_content_hash": metadata.get("content_hash"),
                                    "scope": "processed source model repertoire; full ID set, display capped at ten",
                                },
                            }
                    results.append(LookupRecord(query=query, found=True, values=values))
                except (sqlite3.Error, dataset.IncompleteModelCoverage) as exc:
                    results.append(
                        LookupRecord(query=query, error=f"AGORA reaction source error: {exc}")
                    )
            return results

    def _fetch_sync(
        self,
        queries: list[dict[str, Any]],
        groups_to_compute: frozenset[str],
        capability_id: str | None = None,
    ) -> list[LookupRecord]:
        self._check_generation()
        want_reactions = "reactions" in groups_to_compute
        if want_reactions and not self._reaction_db_ready():
            return [
                LookupRecord(query=query, error="AGORA reaction database unavailable")
                for query in queries
            ]
        want_models = "model" in groups_to_compute
        with self._source.session() if want_reactions else nullcontext(None) as con:
            records: list[LookupRecord] = []
            for query in queries:  # one record per query, in order — never reorder/drop
                taxid = str(query.get("ncbi.taxon.id", "") or "").strip()
                recs = dataset.reconstructions_for(taxid) if taxid else []
                if (
                    capability_id == "list_reconstructions"
                    and query.get("genome.accession") is not None
                ):
                    recs = dataset.reconstructions_for_genome(str(query["genome.accession"]))
                if capability_id == "describe_reconstruction":
                    key = str(query.get("microbe.agora.reconstruction_id", ""))
                    release, separator, reconstruction_id = key.partition(":")
                    if not separator or release != dataset.CROSSWALK_RELEASE:
                        records.append(
                            LookupRecord(
                                query=query,
                                error="AGORA reconstruction ID must match the bundled release-qualified identity",
                            )
                        )
                        continue
                    recs = dataset.reconstruction_for(reconstruction_id)

                if not recs:
                    records.append(LookupRecord(query=query, found=False))  # a miss is normal
                    continue
                values: dict[str, Any] = {"microbe.metabolism.reconstruction": recs}
                try:
                    if capability_id == "list_reconstructions":
                        ids = sorted(
                            {f"{dataset.CROSSWALK_RELEASE}:{r['reconstruction_id']}" for r in recs}
                        )
                        values["microbe.agora.reconstruction_id"] = ids
                        values["microbe.agora.reconstructions"] = recs[:10]
                        values["microbe.agora.coverage"] = {
                            "observed_count": len(ids),
                            "display_count": min(10, len(recs)),
                            "scope": "bundled crosswalk",
                            "release": dataset.CROSSWALK_RELEASE,
                        }
                    elif capability_id == "describe_reconstruction":
                        values["microbe.agora.reconstruction"] = {
                            "id": key,
                            "reconstruction_id": reconstruction_id,
                            "release": dataset.CROSSWALK_RELEASE,
                            "source_associations": recs,
                        }
                        if "artifact" in groups_to_compute:
                            values["microbe.agora.artifact"] = self._artifact_metadata(
                                reconstruction_id
                            )
                    if con is not None:
                        ids = [r["reconstruction_id"] for r in recs]
                        values["microbe.metabolism.reactions"] = dataset.reactions_for(con, ids)
                    if want_models:
                        values["microbe.metabolism.sbml"] = self._models_for(recs)
                except (
                    sqlite3.Error,
                    _ResourceUnavailable,
                    dataset.IncompleteModelCoverage,
                    httpx.HTTPError,
                    OSError,
                    InvalidSBML,
                ) as exc:
                    records.append(LookupRecord(query=query, error=f"AGORA resource error: {exc}"))
                    continue
                records.append(LookupRecord(query=query, found=True, values=values))
            return records

    def _artifact_metadata(self, reconstruction_id: str) -> dict[str, Any]:
        from agora_weaver.setup import default_sbml_cache_dir

        directory = (
            self._sbml_cache_dir if self._sbml_cache_dir is not None else default_sbml_cache_dir()
        )
        path = directory / f"{reconstruction_id}.xml"
        result = {
            "reconstruction_id": reconstruction_id,
            "crosswalk_release": dataset.CROSSWALK_RELEASE,
            "remote_availability": (
                "provider_release_selected_service"
                if self._model_download_base_url == DEFAULT_INDIVIDUAL_SBML_BASE
                else "caller_configured_unverified"
            ),
            "download_enabled": auto_consented(self._auto_download_models),
            "release_verified": False,
            "path": None,
            "model_id": None,
            "sha256": None,
        }
        if path.exists():
            result.update(
                {
                    "status": "cached_structurally_valid_release_unverified",
                    "path": str(path),
                    "model_id": validate_model_sbml(path),
                    "sha256": _sha256(path),
                }
            )
        else:
            result["status"] = (
                "consent_required"
                if not auto_consented(self._auto_download_models)
                else "not_cached"
            )
        return result

    def _models_for(self, recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cached (lazily-downloaded) SBML path per reconstruction — omitting any not available."""
        from agora_weaver.setup import ensure_model_sbml, individual_sbml_url

        out: list[dict[str, Any]] = []
        for rec in recs:
            recon_id = rec["reconstruction_id"]
            path = ensure_model_sbml(
                recon_id,
                cache_dir=self._sbml_cache_dir,
                auto=self._auto_download_models,
                base_url=self._model_download_base_url,
            )
            if path is None:
                raise _ResourceUnavailable(f"SBML unavailable for {recon_id}; download not enabled")
            if path is not None:
                out.append(
                    {
                        "reconstruction_id": recon_id,
                        "path": str(path),
                        "source_url": individual_sbml_url(
                            recon_id, base_url=self._model_download_base_url
                        ),
                        "release": dataset.CROSSWALK_RELEASE,
                        "model_id": validate_model_sbml(path),
                        "sha256": _sha256(path),
                    }
                )
        return out


def _default_db_path() -> Path:
    """Per-user default reaction-DB path (matches ``setup.default_db_path``)."""
    from agora_weaver.setup import default_db_path

    return default_db_path()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
