"""taxonweaver — NCBI taxonomy weaver for Braidworks (local + Datasets v2 API)."""

from .backends.base import ResolutionBackend
from .backends.datasets_v2 import DatasetsV2Backend
from .backends.local import LocalTaxonomyBackend
from .dispatch import BackendDispatchWeaver
from .factory import build_ncbi_weaver
from .intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus
from .mapper import map_taxon_match
from .weaver import NCBITaxonWeaver

__all__ = [
    "NCBITaxonWeaver",
    "build_ncbi_weaver",
    "BackendDispatchWeaver",
    "ResolutionBackend",
    "LocalTaxonomyBackend",
    "DatasetsV2Backend",
    "TaxonMatch",
    "TaxonMatchStatus",
    "LineageEntry",
    "CandidateMatch",
    "map_taxon_match",
]
