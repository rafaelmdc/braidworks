"""A tiny, deterministic GMrepo dataset for ``weaverkit verify --strict`` and tests.

Builds a mini SQLite (via the same ``setup.write_db`` used for the real build) from
canned rows — no network. Mirrors the real API shapes for *Bacteroides* (genus,
NCBI taxid 816), whose single association reports it prevalent in Ulcerative Colitis,
plus a global overview row — so the spec's golden is reproducible offline. A second
taxon (*Faecalibacterium*, taxid 216851) with two phenotype rows exercises count>1.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from gmrepo_weaver.setup import write_db

_OVERVIEW = [
    {
        "ncbi_taxon_id": 816,
        "rank": "genus",
        "name": "Bacteroides",
        "pct_of_all_samples": 81.07,
        "nr_phenotypes": 58,
        "presented_samples": 55716,
    },
    {
        "ncbi_taxon_id": 216851,
        "rank": "genus",
        "name": "Faecalibacterium",
        "pct_of_all_samples": 74.5,
        "nr_phenotypes": 52,
        "presented_samples": 41200,
    },
]

_ASSOCIATIONS = [
    {
        "ncbi_taxon_id": 816,
        "rank": "genus",
        "mesh_id": "D003093",
        "phenotype_name": "Colitis, Ulcerative",
        "samples": 493,
        "phenotype_valid_runs": 540,
        "prevalence_percentage": 91.3,
        "abundance_mean": 8.02,
        "abundance_median": 7.41,
        "abundance_sd": 5.11,
    },
    {
        "ncbi_taxon_id": 216851,
        "rank": "genus",
        "mesh_id": "D003093",
        "phenotype_name": "Colitis, Ulcerative",
        "samples": 426,
        "phenotype_valid_runs": 540,
        "prevalence_percentage": 78.9,
        "abundance_mean": 2.44,
        "abundance_median": 2.03,
        "abundance_sd": 1.90,
    },
    {
        "ncbi_taxon_id": 216851,
        "rank": "genus",
        "mesh_id": "D003424",
        "phenotype_name": "Crohn Disease",
        "samples": 191,
        "phenotype_valid_runs": 312,
        "prevalence_percentage": 61.2,
        "abundance_mean": 1.71,
        "abundance_median": 1.44,
        "abundance_sd": 1.02,
    },
]

_PHENOTYPES = [
    {"mesh_id": "D003093", "phenotype_name": "Colitis, Ulcerative", "valid_runs": 540},
    {"mesh_id": "D003424", "phenotype_name": "Crohn Disease", "valid_runs": 312},
]

# A tiny per-sample profile set for the sample_profiles capability: one phenotype (UC), two
# runs, each with two genera's relative abundances — enough to exercise the mesh_id lookup and
# the sample × taxon shape without network.
_SAMPLE_PROFILES = [
    {"mesh_id": "D003093", "run_id": "ERRFIX01", "ncbi_taxon_id": 816, "rank": "genus",
     "relative_abundance": 52.4},
    {"mesh_id": "D003093", "run_id": "ERRFIX01", "ncbi_taxon_id": 216851, "rank": "genus",
     "relative_abundance": 18.7},
    {"mesh_id": "D003093", "run_id": "ERRFIX02", "ncbi_taxon_id": 816, "rank": "genus",
     "relative_abundance": 44.1},
    {"mesh_id": "D003093", "run_id": "ERRFIX02", "ncbi_taxon_id": 216851, "rank": "genus",
     "relative_abundance": 25.3},
]

_cached_path: Path | None = None


def build_fixture_db(target: Path) -> None:
    """Write the mini fixture DB to ``target`` (canned records, no network)."""
    write_db(
        target,
        overview=_OVERVIEW,
        associations=_ASSOCIATIONS,
        phenotypes=_PHENOTYPES,
        sample_profiles=_SAMPLE_PROFILES,
    )


def fixture_db_path() -> Path:
    """Build the fixture DB once per process and return its path."""
    global _cached_path
    if _cached_path is None:
        directory = Path(tempfile.mkdtemp(prefix="gmrepo_fixture_"))
        _cached_path = directory / "gmrepo.sqlite"
        build_fixture_db(_cached_path)
    return _cached_path
