"""The local backend for disbiome_weaver — IMPLEMENT ME.

This is the novel ~20% the scaffold cannot write for you: the actual lookup
against the local source, normalized into ``LookupRecord``s. Everything
else (manifest, dispatch, mapper) is generated and wired. Implement the three
``# TODO`` spots below; each links to the section of the guide with the full
contract and an example.

Guide: weaverkit/docs/implementing-backends.md
Worked example (copy this shape): weavers/example_weaver/src/example_weaver/backends/local.py
"""

from __future__ import annotations

from typing import Any

from braidworks.core import BackendBase
from braidworks.core import LookupRecord


class DisbiomeLocalBackend(BackendBase):
    """local backend. Not configured until you wire its data source."""

    name = "local"

    def __init__(self) -> None:
        # TODO(configured): set True once the data source is actually wired (DB
        # file opened / API key present). While False, the dispatch raises
        # BackendUnavailable and conformance golden tests skip this backend.
        # See: weaverkit/docs/implementing-backends.md#is_configured
        self._configured = False

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        # TODO(fingerprint): return a STABLE, version-specific string for the data
        # this backend serves — a release tag, dump date, or content checksum.
        # It is part of the cache key, so it must change when the data changes and
        # be identical for identical data. NEVER return "" or "unknown" (that
        # silently disables cache invalidation; conformance rejects it).
        # Spec's declared source of truth for the version: content hash (sha256) of the fetched Disbiome tables, recorded at build time — Disbiome publishes no release tag.
        # See: weaverkit/docs/implementing-backends.md#fingerprint
        return "disbiome_weaver-local-TODO"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[LookupRecord]:
        # TODO(fetch): look the inputs up in the local source and return one
        # LookupRecord PER input query, IN THE SAME ORDER (the dispatch relies
        # on positional alignment — never drop, reorder, or merge).
        #   - each ``query`` is {consumed_type_id: value} for one entity;
        #   - on a hit:   record.found=True, record.values={produced_type_id: value, ...}
        #                 (only keys this capability produces; the mapper filters
        #                  to the requested subset);
        #   - on a miss:  record.found=False (a normal data outcome, not an error);
        #   - on failure: record.error="..." (per-entity; do not raise for data
        #                 problems — failures are values).
        # ``capability_id`` tells you which capability is running if the backend
        # serves more than one; ``requested_outputs`` lets you skip expensive
        # fields nobody asked for; ``groups_to_compute`` is the resolved set of
        # triggered group ids — gate expensive paths on membership in it.
        # See: weaverkit/docs/implementing-backends.md#fetch
        raise NotImplementedError("TODO: implement local fetch for disbiome_weaver")
