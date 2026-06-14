"""Top-level service entry points for the resolver package."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .cache import lookup_reviewed_mapping, record_reviewed_mapping
from .db import connect, fetch_all_metadata, initialize_database
from .exact import resolve_exact
from .fuzzy import suggest_fuzzy_candidates
from .lineage import get_lineage_for_taxid
from .normalize import looks_vague, normalize_name
from .policy import (
    MatchType,
    ResolutionStatus,
    WarningCode,
    allows_auto_accept,
    classify_fuzzy_status,
    requires_review,
)
from .schemas import (
    BatchResolveRequest,
    BatchResolveResult,
    DecisionRecord,
    ResolveRequest,
    ResolveResult,
)
from .transforms import generate_transforms


class TaxonomyResolverService:
    """Single orchestration surface for CLI, tests, and later Django code.

    The service owns workflow order and contract assembly, while lower-level
    modules own lookup, scoring, and persistence concerns.
    """

    def __init__(self, taxonomy_db_path: str | Path, cache_db_path: str | Path | None = None):
        self.taxonomy_db_path = Path(taxonomy_db_path)
        self.cache_db_path = Path(cache_db_path) if cache_db_path else None
        initialize_database(self.taxonomy_db_path, create_indexes=False)
        if self.cache_db_path and self.cache_db_path != self.taxonomy_db_path:
            initialize_database(self.cache_db_path)
        self._taxonomy_connection = connect(self.taxonomy_db_path)
        if self.cache_db_path and self.cache_db_path != self.taxonomy_db_path:
            self._cache_connection = connect(self.cache_db_path)
        else:
            self._cache_connection = self._taxonomy_connection
        self._taxonomy_metadata = fetch_all_metadata(self._taxonomy_connection)
        self._taxonomy_build_version = self._taxonomy_metadata.get("taxonomy_build_version")
        self._closed = False

    def close(self) -> None:
        """Release any persistent SQLite connections owned by the service."""

        if self._closed:
            return
        if self._cache_connection is not self._taxonomy_connection:
            self._cache_connection.close()
        self._taxonomy_connection.close()
        self._closed = True

    def __enter__(self) -> TaxonomyResolverService:
        """Support context-manager usage for explicit connection cleanup."""

        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        """Close owned connections when the service leaves a context block."""

        self.close()

    def resolve_name(self, request: ResolveRequest) -> ResolveResult:
        """Resolve one organism string using the deterministic-first workflow."""

        normalized_name = normalize_name(request.original_name)

        cached = lookup_reviewed_mapping(
            request,
            taxonomy_db_path=self._taxonomy_connection,
            cache_db_path=self._cache_connection,
            taxonomy_build_version=self._taxonomy_build_version,
            create_cache_indexes=self._cache_connection is not self._taxonomy_connection,
        )
        if cached:
            return ResolveResult(
                original_name=request.original_name,
                normalized_name=normalized_name,
                provided_level=request.provided_level,
                status=cached.status,
                review_required=requires_review(cached.status),
                auto_accept=allows_auto_accept(cached.status) or cached.status == ResolutionStatus.CONFIRMED_BY_USER,
                match_type=MatchType.CACHED,
                warnings=list(cached.warnings) + [WarningCode.CACHED_DECISION_REUSED],
                matched_taxid=cached.resolved_taxid,
                matched_name=cached.matched_scientific_name,
                score=cached.score,
                cache_applied=True,
                metadata={"decision_created_at": cached.created_at},
            )

        exact_result = resolve_exact(request, self._taxonomy_connection)
        if exact_result:
            return exact_result

        transformed_result = self._resolve_transformed_exact(request)
        if transformed_result:
            return transformed_result

        if looks_vague(request.original_name):
            status = ResolutionStatus.UNRESOLVED_VAGUE_LABEL
            return ResolveResult(
                original_name=request.original_name,
                normalized_name=normalized_name,
                provided_level=request.provided_level,
                status=status,
                review_required=requires_review(status),
                auto_accept=allows_auto_accept(status),
                match_type=MatchType.NONE,
                warnings=[WarningCode.VAGUE_LABEL_DETECTED],
            )

        candidates = (
            suggest_fuzzy_candidates(request, self._taxonomy_connection)
            if request.allow_fuzzy
            else []
        )
        if candidates:
            status, warnings = classify_fuzzy_status(len(candidates))
            return ResolveResult(
                original_name=request.original_name,
                normalized_name=normalized_name,
                provided_level=request.provided_level,
                status=status,
                review_required=requires_review(status),
                auto_accept=allows_auto_accept(status),
                match_type=MatchType.FUZZY,
                candidates=candidates,
                warnings=warnings,
            )

        status = ResolutionStatus.UNRESOLVED_NO_MATCH
        return ResolveResult(
            original_name=request.original_name,
            normalized_name=normalized_name,
            provided_level=request.provided_level,
            status=status,
            review_required=requires_review(status),
            auto_accept=allows_auto_accept(status),
            match_type=MatchType.NONE,
        )

    def resolve_batch(self, request: BatchResolveRequest) -> BatchResolveResult:
        """Resolve a batch and return compact per-status counts."""

        results = [self.resolve_name(item) for item in request.items]
        counts = Counter(result.status for result in results)
        summary = {status.value: counts.get(status, 0) for status in ResolutionStatus}
        return BatchResolveResult(results=results, batch_id=request.batch_id, summary=summary)

    def get_lineage(self, taxid: int) -> list[dict[str, str | int]]:
        """Expose lineage data using the same shape a future API would return."""

        return [asdict(entry) for entry in get_lineage_for_taxid(self._taxonomy_connection, taxid)]

    def record_decision(self, _decision: DecisionRecord) -> None:
        """Persist reviewed decisions when the cache backend is implemented."""

        record_reviewed_mapping(
            _decision,
            taxonomy_db_path=self._taxonomy_connection,
            cache_db_path=self._cache_connection,
            create_cache_indexes=self._cache_connection is not self._taxonomy_connection,
        )

    def get_taxonomy_build_info(self) -> dict[str, str]:
        """Expose taxonomy build metadata for CLI and later integration checks."""

        return dict(self._taxonomy_metadata)

    def _resolve_transformed_exact(self, request: ResolveRequest) -> ResolveResult | None:
        """Try configured fallback transforms before fuzzy matching or vague failure.

        Any transformed hit remains review-only even if the transformed name
        resolves cleanly, because the original observed string did not match
        directly.
        """

        for transform in generate_transforms(request.original_name):
            transformed_request = ResolveRequest(
                original_name=transform.transformed_name,
                provided_level=request.provided_level,
                allow_fuzzy=False,
                source=request.source,
                context=request.context,
            )
            transformed_result = resolve_exact(transformed_request, self._taxonomy_connection)
            if transformed_result is None:
                continue

            status = transformed_result.status
            if status in {
                ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC,
                ResolutionStatus.RESOLVED_EXACT_SYNONYM,
                ResolutionStatus.RESOLVED_NORMALIZED,
            }:
                status = ResolutionStatus.MANUAL_REVIEW_REQUIRED

            metadata = dict(transformed_result.metadata)
            metadata["transform_rule"] = transform.rule_name
            metadata["transformed_name"] = transform.transformed_name
            metadata["transformed_base_status"] = transformed_result.status.value

            warnings = list(transformed_result.warnings)
            for warning in transform.warnings:
                if warning not in warnings:
                    warnings.append(warning)

            return ResolveResult(
                original_name=request.original_name,
                normalized_name=normalize_name(request.original_name),
                provided_level=request.provided_level,
                status=status,
                review_required=True,
                auto_accept=False,
                match_type=transformed_result.match_type,
                warnings=warnings,
                matched_taxid=transformed_result.matched_taxid,
                matched_name=transformed_result.matched_name,
                matched_rank=transformed_result.matched_rank,
                score=transformed_result.score,
                candidates=transformed_result.candidates,
                lineage=transformed_result.lineage,
                cache_applied=transformed_result.cache_applied,
                metadata=metadata,
            )

        return None
