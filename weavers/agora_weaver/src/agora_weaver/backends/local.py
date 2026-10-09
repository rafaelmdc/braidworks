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
import sqlite3
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.source_identity import SourceBinding, artifact_stamp

from agora_weaver import dataset


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
    ) -> None:
        # ``None`` = "the default reaction-DB path, present-or-not"; core works either way.
        self._reaction_db_path = (
            Path(reaction_db_path) if reaction_db_path is not None else _default_db_path()
        )
        # Where per-model SBML files are cached, and whether a missing one may be downloaded
        # on demand (the ``model`` group; each model is ~8 MB).
        self._sbml_cache_dir = Path(sbml_cache_dir) if sbml_cache_dir is not None else None
        self._auto_download_models = auto_download_models
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
        return f"agora-local-{dataset.CROSSWALK_RELEASE}-{rxn}"

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
        return await asyncio.to_thread(self._fetch_sync, queries, groups_to_compute)

    def _fetch_sync(
        self, queries: list[dict[str, Any]], groups_to_compute: frozenset[str]
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
                if not recs:
                    records.append(LookupRecord(query=query, found=False))  # a miss is normal
                    continue
                values: dict[str, Any] = {"microbe.metabolism.reconstruction": recs}
                try:
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
                ) as exc:
                    records.append(LookupRecord(query=query, error=f"AGORA resource error: {exc}"))
                    continue
                records.append(LookupRecord(query=query, found=True, values=values))
            return records

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
            )
            if path is None:
                raise _ResourceUnavailable(f"SBML unavailable for {recon_id}; download not enabled")
            if path is not None:
                out.append(
                    {
                        "reconstruction_id": recon_id,
                        "path": str(path),
                        "source_url": individual_sbml_url(recon_id),
                    }
                )
        return out


def _default_db_path() -> Path:
    """Per-user default reaction-DB path (matches ``setup.default_db_path``)."""
    from agora_weaver.setup import default_db_path

    return default_db_path()
