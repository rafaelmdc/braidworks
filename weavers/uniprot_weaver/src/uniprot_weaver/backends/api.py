"""The api backend for uniprot_weaver — the keyless UniProtKB REST API.

Strategy (MVP — top reviewed hit as the representative protein):
  * ``protein.query`` (a free-text gene symbol / protein name / accession) is sent
    to ``GET /uniprotkb/search`` with a compact ``fields`` projection.
  * We prefer **reviewed (Swiss-Prot)** entries — ``... AND reviewed:true``, take the
    top-ranked hit — and fall back to unreviewed (TrEMBL) only if there is none.
    This is the nomenclatural-standard analogue of BacDive's type-strain choice.
  * The hit is normalized into a ``LookupRecord``: accession + descriptive fields,
    plus the organism's **NCBI taxid** (``organism.taxonId``) — the bridge that links
    a protein back into the organism layer and onward to every downstream molecular
    weaver via ``protein.uniprot.accession``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). JSON paths were validated
against the live API (search for gene:TP53 -> P04637); every read guards missing
keys, since unreviewed entries omit recommendedName / gene / function.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, format_exc

from uniprot_weaver import mapping

logger = logging.getLogger("uniprot_weaver.api")

# --- ID-mapping (the map_* capabilities) -------------------------------------
# The ID-mapping endpoint is async (submit a job, poll, fetch) AND a batch endpoint
# (many ids per job), so a whole batch resolves in one or two jobs. into-hub mapping
# runs two jobs (reviewed Swiss-Prot + full UniProtKB) and orders reviewed-first.
_IDMAP_RESULT_PAGE = 500  # max page size the results endpoint allows
_IDMAP_POLL_DELAY = 1.0  # seconds between status polls
_IDMAP_POLL_TRIES = 60  # ~60s ceiling before giving up on a job

DEFAULT_BASE_URL = "https://rest.uniprot.org"
# Compact projection — the fields the mapper reads, plus annotation_score (the
# representative tie-break). annotation_score arrives as JSON key "annotationScore".
_FIELDS = (
    "accession,protein_name,gene_names,organism_name,organism_id,"
    "length,cc_function,reviewed,annotation_score"
)
# Page size to rank within. A bounded gene_exact/accession query returns far fewer;
# for a broad free-text query this caps how many top-ranked candidates we tie-break.
_PAGE = 25
# Official UniProtKB accession syntax (so "P04637" routes to an exact lookup).
_ACCESSION = re.compile(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}")


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


def _mapping_record(
    query: dict[str, Any], type_id: str, ordered: list[str], *, reviewed_set: set[str]
) -> LookupRecord:
    """A LookupRecord for an into-hub mapping: a set output + count/records (reviewed flag)."""
    if not ordered:
        return LookupRecord(query=query, found=False)
    return LookupRecord(
        query=query,
        found=True,
        values={
            type_id: ordered,  # the fan dimension (set output)
            mapping.MAPPING_COUNT: len(ordered),
            mapping.MAPPING_RECORDS: [
                {"id": i, "reviewed": i in reviewed_set} for i in ordered
            ],
        },
    )


def _query_variants(term: str) -> list[str]:
    """Candidate UniProtKB query clauses for a free-text term, most-specific first.

    A bare term ranks by relevance and mis-resolves (free-text "TP53" tops out at
    MDM2, which merely *mentions* TP53). So we try an exact accession, then an exact
    gene symbol, then free text — the first that hits wins.
    """
    variants: list[str] = []
    if _ACCESSION.fullmatch(term.upper()):
        variants.append(f"accession:{term.upper()}")
    variants.append(f"gene_exact:{term}")
    variants.append(term)
    return variants


def _pick(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically pick the representative hit from a result page.

    Total order: highest annotation score first, then accession ascending as a stable
    tie-break. This makes a given query map to the *same* protein every time (UniProt's
    default relevance ranking does not), choosing the best-curated entry as the
    representative — for a specific organism, query its accession or add the organism.
    """
    return min(
        results,
        key=lambda r: (-float(r.get("annotationScore") or 0.0), r.get("primaryAccession", "")),
    )
# Evidence parentheticals UniProt appends to FUNCTION text — noise on a dossier card.
_EVIDENCE = re.compile(r"\s*\((?:PubMed:[^)]*|By similarity|Probable|Potential|Reviewed[^)]*)\)")


def _recommended_name(desc: dict[str, Any]) -> str | None:
    """Best display name: recommended, else submitted, else first alternative."""
    recommended = desc.get("recommendedName", {})
    if isinstance(recommended, dict) and recommended.get("fullName", {}).get("value"):
        return recommended["fullName"]["value"]
    submitted = desc.get("submittedName")
    if isinstance(submitted, list) and submitted:
        full = submitted[0].get("fullName", {})
        if full.get("value"):
            return full["value"]
    alternatives = desc.get("alternativeNames")
    if isinstance(alternatives, list) and alternatives:
        return alternatives[0].get("fullName", {}).get("value")
    return None


def _primary_gene(genes: Any) -> str | None:
    if isinstance(genes, list) and genes:
        return genes[0].get("geneName", {}).get("value")
    return None


def _function(comments: Any) -> str | None:
    """First FUNCTION comment's text, with UniProt evidence parentheticals stripped."""
    if not isinstance(comments, list):
        return None
    for comment in comments:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts") or []
            if texts and texts[0].get("value"):
                return _EVIDENCE.sub("", texts[0]["value"]).strip()
    return None


def _extract(entry: dict[str, Any]) -> dict[str, Any]:
    """Map one UniProtKB entry to produced type_ids (omitting absent fields)."""
    organism = entry.get("organism", {}) or {}
    candidates: dict[str, Any] = {
        "protein.uniprot.accession": entry.get("primaryAccession"),
        "protein.name": _recommended_name(entry.get("proteinDescription", {}) or {}),
        "protein.gene": _primary_gene(entry.get("genes")),
        "protein.organism": organism.get("scientificName"),
        "ncbi.taxon.id": organism.get("taxonId"),
        "protein.function": _function(entry.get("comments")),
        "protein.length": (entry.get("sequence", {}) or {}).get("length"),
        "protein.reviewed": (
            "reviewed"
            if str(entry.get("entryType", "")).startswith("UniProtKB reviewed")
            else "unreviewed"
        ),
    }
    return {k: v for k, v in candidates.items() if v is not None}


class UniprotApiBackend(BackendBase):
    """UniProtKB REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self, *, base_url: str = DEFAULT_BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    def is_configured(self) -> bool:
        """UniProtKB REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API/JSON contract version."""
        return "uniprot-rest-v1"

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # follow_redirects: the ID-mapping results endpoint 303-redirects to its
            # stream variant when a job finishes.
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
        if capability_id == mapping.TO_ACCESSION:
            return await self._map_to_accession(queries)
        if capability_id == mapping.FROM_ACCESSION:
            return await self._map_from_accession(queries, requested_outputs)
        # resolve_protein: one search per query; the whole entry arrives at once, so we
        # compute every field and let the shared mapper filter to requested_outputs.
        organism = str((params or {}).get("organism") or "").strip() or None
        records: list[LookupRecord] = []
        for query in queries:
            term = str(query.get("protein.query", "")).strip()
            records.append(await self._resolve_one(query, term, organism))
        return records

    # --- ID mapping ----------------------------------------------------------

    async def _map_to_accession(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        """Any supported id -> UniProt accession(s). Picks the `from` db per input type.

        Queries may carry different alternative inputs, so we group by source db and run
        the reviewed-first pair (Swiss-Prot + full UniProtKB) per group. Accessions are
        ordered reviewed-first; a whole-job failure becomes a per-query error.
        """
        # source value per query + which from db it implies.
        per_query: list[tuple[str, str] | None] = []
        by_db: dict[str, set[str]] = {}
        for q in queries:
            hit: tuple[str, str] | None = None
            for type_id, from_db in mapping.FROM_DB.items():
                raw = str(q.get(type_id, "") or "").strip()
                if raw:
                    hit = (from_db, raw)
                    by_db.setdefault(from_db, set()).add(raw)
                    break
            per_query.append(hit)

        try:
            resolved: dict[str, dict[str, list[str]]] = {}
            reviewed: dict[str, dict[str, list[str]]] = {}
            for from_db, ids in by_db.items():
                rev, allm = await asyncio.gather(
                    self._idmap(from_db, mapping.UNIPROT_TO_REVIEWED, sorted(ids)),
                    self._idmap(from_db, mapping.UNIPROT_TO, sorted(ids)),
                )
                reviewed[from_db] = rev
                resolved[from_db] = allm
        except httpx.HTTPError as exc:
            logger.warning("UniProt ID-mapping (to accession) failed: %s", exc)
            err = f"UniProt ID-mapping error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for q, hit in zip(queries, per_query):
            if hit is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            from_db, src = hit
            rev = reviewed[from_db].get(src, [])
            rev_set = set(rev)
            ordered = rev + [a for a in resolved[from_db].get(src, []) if a not in rev_set]
            records.append(_mapping_record(q, mapping.ACCESSION, ordered,
                                           reviewed_set=rev_set))
        return records

    async def _map_from_accession(
        self, queries: list[dict[str, Any]], requested_outputs: frozenset[str]
    ) -> list[LookupRecord]:
        """UniProt accession -> any requested target id type(s). Picks the `to` db per output."""
        targets = {t: mapping.TO_DB[t] for t in requested_outputs if t in mapping.TO_DB}
        if not targets:  # nothing routable requested (e.g. only count/records)
            return [LookupRecord(query=q, found=False) for q in queries]

        accs = sorted({str(q.get(mapping.ACCESSION, "") or "").strip() for q in queries} - {""})
        try:
            maps: dict[str, dict[str, list[str]]] = {}
            for type_id, to_db in targets.items():
                maps[type_id] = await self._idmap(mapping.UNIPROT_FROM, to_db, accs) if accs else {}
        except httpx.HTTPError as exc:
            logger.warning("UniProt ID-mapping (from accession) failed: %s", exc)
            err = f"UniProt ID-mapping error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for q in queries:
            acc = str(q.get(mapping.ACCESSION, "") or "").strip()
            values: dict[str, Any] = {}
            recs: list[dict[str, Any]] = []
            for type_id, to_db in targets.items():
                ids = maps[type_id].get(acc, [])
                if ids:
                    values[type_id] = ids
                    recs.extend({"id": i, "db": to_db} for i in ids)
            if not values:
                records.append(LookupRecord(query=q, found=False))
                continue
            values[mapping.MAPPING_COUNT] = len(recs)
            values[mapping.MAPPING_RECORDS] = recs
            records.append(LookupRecord(query=q, found=True, values=values))
        return records

    async def _idmap(self, from_db: str, to_db: str, ids: list[str]) -> dict[str, list[str]]:
        """Run one ID-mapping job (``from_db`` -> ``to_db``); return source id -> target ids.

        Submit the whole batch, poll until the job finishes, then page the results,
        preserving the API's order so per-source target order is stable.
        """
        if not ids:
            return {}
        http = self._http()
        run = await http.post(
            "/idmapping/run", data={"from": from_db, "to": to_db, "ids": ",".join(ids)}
        )
        run.raise_for_status()
        job = run.json()["jobId"]
        await self._await_job(http, job)

        out: dict[str, list[str]] = {}
        url: str | None = f"/idmapping/results/{job}"
        req_params: dict[str, Any] | None = {"format": "json", "size": _IDMAP_RESULT_PAGE}
        while url:
            resp = await http.get(url, params=req_params)
            resp.raise_for_status()
            for row in resp.json().get("results", []):
                to_val = row.get("to")
                target = to_val if isinstance(to_val, str) else (to_val or {}).get("primaryAccession")
                src = str(row.get("from", ""))
                if target and src:
                    out.setdefault(src, []).append(target)
            url = _next_link(resp)  # follow paginated results; absolute URL, no params
            req_params = None
        return out

    async def _await_job(self, http: httpx.AsyncClient, job: str) -> None:
        """Poll ``/idmapping/status/{job}`` until the job finishes (or raise on failure)."""
        for _ in range(_IDMAP_POLL_TRIES):
            resp = await http.get(f"/idmapping/status/{job}")
            resp.raise_for_status()
            status = resp.json().get("jobStatus")
            if status is None or status == "FINISHED":  # absent => results inline / ready
                return
            if status in ("RUNNING", "NEW", "QUEUED"):
                await asyncio.sleep(_IDMAP_POLL_DELAY)
                continue
            raise httpx.HTTPError(f"ID-mapping job {job} failed with status {status!r}")
        raise httpx.HTTPError(f"ID-mapping job {job} did not finish in time")

    async def _resolve_one(
        self, query: dict[str, Any], term: str, organism: str | None = None
    ) -> LookupRecord:
        if not term:
            return LookupRecord(query=query, found=False)
        try:
            entry = await self._best_hit(term, organism)
        except httpx.HTTPError as exc:  # network/HTTP problem is a per-entity error
            logger.warning("UniProt lookup failed for %r: %s", term, exc)
            return LookupRecord(query=query, error=f"UniProt API error: {format_exc(exc)}")

        if entry is None:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(entry))

    async def _best_hit(
        self, term: str, organism: str | None = None
    ) -> dict[str, Any] | None:
        """Deterministic hit: prefer reviewed, escalate accession -> gene -> free text.

        The first variant that returns any results wins; ``_pick`` then chooses the
        representative from that page by a fixed total order (so the result is stable).
        ``organism`` (an NCBI taxid) constrains the species — without it a bare gene
        symbol resolves to whichever species UniProt ranks first (e.g. TP53 -> hamster).
        """
        for reviewed in (True, False):
            for base in _query_variants(term):
                results = await self._search(base, reviewed=reviewed, organism=organism)
                if results:
                    return _pick(results)
        return None

    async def _search(
        self, base: str, *, reviewed: bool, organism: str | None = None
    ) -> list[dict[str, Any]]:
        """A ranked page of UniProtKB hits for one query clause (reviewed-only if asked).

        Sorted by annotation score so the highest-curated candidates lead even when the
        page is truncated; ``_pick`` applies the final deterministic selection.
        """
        q = f"({base}) AND reviewed:true" if reviewed else f"({base})"
        if organism:
            q = f"{q} AND organism_id:{organism}"
        resp = await self._http().get(
            "/uniprotkb/search",
            params={
                "query": q,
                "fields": _FIELDS,
                "format": "json",
                "size": str(_PAGE),
                "sort": "annotation_score desc",
            },
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
