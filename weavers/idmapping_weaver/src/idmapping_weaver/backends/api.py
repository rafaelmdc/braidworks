"""The api backend for idmapping_weaver — the UniProt ID-mapping REST service.

The UniProt ID-mapping endpoint (``rest.uniprot.org/idmapping``) is **async** (submit a
job, poll its status, fetch the results) *and* a **batch** endpoint (many ids per job).
So one ``fetch`` call resolves the whole batch of ids in one or two jobs, never one call
per id.

Every capability is an :class:`~idmapping_weaver.edges.Edge`: ``fetch`` looks the edge up
by ``capability_id`` and runs the shared engine. **Into-hub** edges (``X -> accession``)
run two jobs concurrently — reviewed Swiss-Prot for the canonical accession and full
UniProtKB for genes with no reviewed entry — and order the result reviewed-first, so
``ExpandPolicy.top()`` takes the canonical entry while ``ALL`` fans every isoform.
**Out-of-hub** edges run a single job.

The HTTP client is injectable (``client=``) so tests and the golden fixture drive it with
an ``httpx.MockTransport`` offline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, format_exc

from idmapping_weaver import edges
from idmapping_weaver.edges import Edge

logger = logging.getLogger("idmapping_weaver.api")

DEFAULT_BASE_URL = "https://rest.uniprot.org"
_RESULT_PAGE = 500  # max page size the results endpoint allows
_POLL_DELAY = 1.0  # seconds between status polls
_POLL_TRIES = 60  # ~60s ceiling before giving up on a job


def _next_link(resp: httpx.Response) -> str | None:
    """The ``rel="next"`` URL from a paginated UniProt response's ``Link`` header, if any."""
    link = resp.headers.get("link")
    if not link:
        return None
    for part in link.split(","):
        if 'rel="next"' in part:
            start, end = part.find("<"), part.find(">")
            if 0 <= start < end:
                return part[start + 1 : end]
    return None


class IdMappingApiBackend(BackendBase):
    """UniProt ID-mapping REST backend. Always configured — the service is free, no key."""

    name = "api"

    def __init__(
        self, *, base_url: str = DEFAULT_BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    def is_configured(self) -> bool:
        """The ID-mapping REST service needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API/JSON contract version."""
        return "uniprot-idmapping-v1"

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # follow_redirects: the results endpoint 303-redirects to its stream variant.
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=30.0, follow_redirects=True
            )
        return self._client

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        edge = edges.EDGES_BY_CAPABILITY.get(capability_id)
        if edge is None:  # pragma: no cover - dispatch guards this upstream
            return [LookupRecord(query=q, found=False) for q in queries]
        return await self._resolve_edge(edge, queries)

    async def _resolve_edge(self, edge: Edge, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        """Map a batch of source ids to target ids for one edge, in one or two jobs."""
        in_ids = [str(q.get(edge.consumes, "") or "").strip() for q in queries]
        unique = list(dict.fromkeys(i for i in in_ids if i))
        if not unique:
            return [LookupRecord(query=q, found=False) for q in queries]

        try:
            if edge.into_hub:
                reviewed_map, all_map = await asyncio.gather(
                    self._idmap(edge.from_db, edges.TO_UNIPROT_REVIEWED, unique),
                    self._idmap(edge.from_db, edge.to_db, unique),
                )
            else:
                reviewed_map, all_map = {}, await self._idmap(edge.from_db, edge.to_db, unique)
        except httpx.HTTPError as exc:
            logger.warning("ID-mapping %s failed for %d id(s): %s", edge.capability, len(unique), exc)
            err = f"UniProt ID-mapping error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for query, src in zip(queries, in_ids):
            if not src:
                records.append(LookupRecord(query=query, found=False))
                continue
            reviewed = reviewed_map.get(src, [])
            reviewed_set = set(reviewed)
            ordered = reviewed + [t for t in all_map.get(src, []) if t not in reviewed_set]
            if not ordered:
                records.append(LookupRecord(query=query, found=False))
                continue
            records.append(
                LookupRecord(
                    query=query,
                    found=True,
                    values={
                        edge.produces: ordered,  # the fan dimension (set output)
                        edges.MAPPING_COUNT: len(ordered),
                        edges.MAPPING_RECORDS: [
                            {"id": t, "reviewed": t in reviewed_set} for t in ordered
                        ],
                    },
                )
            )
        return records

    async def _idmap(self, from_db: str, to_db: str, ids: list[str]) -> dict[str, list[str]]:
        """Run one ID-mapping job (``from_db`` -> ``to_db``); return source id -> target ids.

        Submit the whole batch, poll until the job finishes, then page the results,
        preserving the API's order so per-source target order is stable.
        """
        http = self._http()
        run = await http.post(
            "/idmapping/run",
            data={"from": from_db, "to": to_db, "ids": ",".join(ids)},
        )
        run.raise_for_status()
        job = run.json()["jobId"]
        await self._await_job(http, job)

        out: dict[str, list[str]] = {}
        url: str | None = f"/idmapping/results/{job}"
        params: dict[str, Any] | None = {"format": "json", "size": _RESULT_PAGE}
        while url:
            resp = await http.get(url, params=params)
            resp.raise_for_status()
            for row in resp.json().get("results", []):
                to_val = row.get("to")
                target = to_val if isinstance(to_val, str) else (to_val or {}).get("primaryAccession")
                src = str(row.get("from", ""))
                if target and src:
                    out.setdefault(src, []).append(target)
            url = _next_link(resp)  # follow paginated results; absolute URL, no params
            params = None
        return out

    async def _await_job(self, http: httpx.AsyncClient, job: str) -> None:
        """Poll ``/idmapping/status/{job}`` until the job finishes (or raise on failure)."""
        for _ in range(_POLL_TRIES):
            resp = await http.get(f"/idmapping/status/{job}")
            resp.raise_for_status()
            status = resp.json().get("jobStatus")
            if status is None or status == "FINISHED":  # absent => results inline / ready
                return
            if status in ("RUNNING", "NEW", "QUEUED"):
                await asyncio.sleep(_POLL_DELAY)
                continue
            raise httpx.HTTPError(f"ID-mapping job {job} failed with status {status!r}")
        raise httpx.HTTPError(f"ID-mapping job {job} did not finish in time")
