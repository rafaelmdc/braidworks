"""Private UniProt mapping-job transport, composed by the API backend.

This adapter owns no HTTP client. The backend supplies its paced client and retains
lifecycle ownership. Normalization stays pure and source-specific.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from braidworks.core.http_pacing import PacedHTTPClient

from uniprot_weaver.backends.validation import _InvalidResponse, _object, _rows

_IDMAP_RESULT_PAGE = 500


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
            raise _InvalidResponse("UniProt next-page link is malformed")
    return None


def normalize_mapping_page(body: Any, requested_ids: frozenset[str]) -> dict[str, list[str]]:
    """Validate correlation and normalize one page without I/O or mutation."""
    out: dict[str, list[str]] = {}
    body = _object(body, "mapping results")
    if "results" not in body and "failedIds" not in body:
        raise _InvalidResponse("UniProt mapping page must contain results or failedIds")
    failed = body.get("failedIds", [])
    if not isinstance(failed, list) or any(
        not isinstance(src, str) or src not in requested_ids for src in failed
    ):
        raise _InvalidResponse("UniProt failedIds must identify requested inputs")
    for row in _rows(body.get("results", []), "mapping results"):
        to_val = row.get("to")
        target = (
            to_val
            if isinstance(to_val, str)
            else _object(to_val, "mapping target").get("primaryAccession")
        )
        src = row.get("from")
        if (
            not isinstance(src, str)
            or src not in requested_ids
            or not isinstance(target, str)
            or not target
        ):
            raise _InvalidResponse(
                "UniProt mapping row cannot be correlated to requested identifier"
            )
        out.setdefault(src, []).append(target)
    return {src: sorted(set(targets)) for src, targets in out.items()}


class MappingJobClient:
    """Submit, poll and page one source/target job under finite request budgets."""

    def __init__(
        self,
        http: PacedHTTPClient,
        *,
        poll_tries: int = 60,
        poll_delay: float = 1.0,
        max_pages: int = 1000,
    ) -> None:
        self._http = http
        self._poll_tries = poll_tries
        self._poll_delay = poll_delay
        self._max_pages = max_pages

    async def run(self, from_db: str, to_db: str, ids: list[str]) -> dict[str, list[str]]:
        """Run one ID-mapping job (``from_db`` -> ``to_db``); return source id -> target ids.

        Submit the whole batch, poll until the job finishes, then page the results,
        deduplicating and sorting targets across every result page.
        """
        if not ids:
            return {}
        http = self._http
        run = await http.post(
            "/idmapping/run", data={"from": from_db, "to": to_db, "ids": ",".join(ids)}
        )
        run.raise_for_status()
        job = _object(run.json(), "job submission").get("jobId")
        if not isinstance(job, str) or not job:
            raise _InvalidResponse("UniProt job submission must contain jobId")
        await self._await_job(http, job)

        out: dict[str, list[str]] = {}
        url: str | None = f"/idmapping/results/{job}"
        req_params: dict[str, Any] | None = {"format": "json", "size": _IDMAP_RESULT_PAGE}
        visited: set[str] = set()
        requested_ids = frozenset(ids)
        while url:
            if url in visited or len(visited) >= self._max_pages:
                raise _InvalidResponse(
                    "UniProt mapping result pagination repeats or exceeds budget"
                )
            visited.add(url)
            resp = await http.get(url, params=req_params)
            resp.raise_for_status()
            page = normalize_mapping_page(resp.json(), requested_ids)
            for src, targets in page.items():
                out.setdefault(src, []).extend(targets)
            url = _next_link(resp)  # follow paginated results; absolute URL, no params
            req_params = None
        return {src: sorted(set(targets)) for src, targets in out.items()}

    async def _await_job(self, http: PacedHTTPClient, job: str) -> None:
        """Poll ``/idmapping/status/{job}`` until the job finishes (or raise on failure)."""
        for _ in range(self._poll_tries):
            resp = await http.get(f"/idmapping/status/{job}")
            resp.raise_for_status()
            body = _object(resp.json(), "job status")
            status = body.get("jobStatus")
            if status is None:
                if "results" not in body and "failedIds" not in body:
                    raise _InvalidResponse("UniProt job status has no state or result evidence")
                _rows(body.get("results", []), "job status results")
            if status is None or status == "FINISHED":  # absent => results inline / ready
                return
            if status in ("RUNNING", "NEW", "QUEUED"):
                await asyncio.sleep(self._poll_delay)
                continue
            raise httpx.HTTPError(f"ID-mapping job {job} failed with status {status!r}")
        raise httpx.HTTPError(f"ID-mapping job {job} did not finish in time")
