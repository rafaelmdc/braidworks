"""Stable public API for the Taxonbridge resolver package."""

from importlib.metadata import PackageNotFoundError, version

from .policy import MatchType, ResolutionStatus, WarningCode
from .schemas import (
    BatchResolveRequest,
    BatchResolveResult,
    CandidateMatch,
    DecisionAction,
    DecisionRecord,
    LineageEntry,
    ResolveRequest,
    ResolveResult,
)
from .service import TaxonomyResolverService

try:
    __version__ = version("taxonbridge")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "BatchResolveRequest",
    "BatchResolveResult",
    "CandidateMatch",
    "DecisionAction",
    "DecisionRecord",
    "LineageEntry",
    "MatchType",
    "ResolveRequest",
    "ResolveResult",
    "ResolutionStatus",
    "TaxonomyResolverService",
    "WarningCode",
    "__version__",
]
