"""Taxon resolution backends (local SQLite, NCBI Datasets v2)."""

from .base import ResolutionBackend
from .datasets_v2 import DatasetsV2Backend
from .local import LocalTaxonomyBackend

__all__ = ["ResolutionBackend", "LocalTaxonomyBackend", "DatasetsV2Backend"]
