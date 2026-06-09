"""A tiny, deterministic Disbiome dataset for ``weaverkit verify --strict`` and tests.

Builds a mini SQLite (via the same ``setup.write_db`` used for the real build) from
canned records — no network. Mirrors the real API shapes for *Lactobacillus*
(NCBI taxid 1591), whose single experiment associates it (Elevated) with Autism,
so the spec's golden is reproducible offline.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from disbiome_weaver.setup import write_db

_EXPERIMENTS = [
    {
        "experiment_id": "1",
        "qualitative_outcome": "Elevated",
        "disease_id": "1",
        "disease_name": "Autism",
        "meddra_level": "preferred_term",
        "meddra_id": "10080683",
        "organism_id": "1",
        "organism_name": "Lactobacillus",
        "organism_ncbi_id": "1591",
        "subject_value": "None",
        "control_value": "None",
        "ratio": "None",
        "method_name": "qPCR",
        "sample_name": "Faeces",
        "host_type": "Human",
        "publication_id": "1",
        "control_name": "Healthy control",
        "response_name": "None",
        "response_unit": "None",
    },
    # A second organism (Enterococcus, taxid 1350) with TWO experiments for the same
    # disease — exercises count>1 and disease-name de-duplication in the summary slice.
    {
        "experiment_id": "2",
        "qualitative_outcome": "Elevated",
        "disease_id": "2",
        "disease_name": "Crohn's disease",
        "meddra_level": "preferred_term",
        "meddra_id": "10011401",
        "organism_id": "2",
        "organism_name": "Enterococcus",
        "organism_ncbi_id": "1350",
        "subject_value": "None",
        "control_value": "None",
        "ratio": "None",
        "method_name": "16S rRNA sequencing",
        "sample_name": "Biopsy",
        "host_type": "Human",
        "publication_id": "1",
        "control_name": "Healthy control",
        "response_name": "None",
        "response_unit": "None",
    },
    {
        "experiment_id": "3",
        "qualitative_outcome": "Reduced",
        "disease_id": "2",
        "disease_name": "Crohn's disease",
        "meddra_level": "preferred_term",
        "meddra_id": "10011401",
        "organism_id": "2",
        "organism_name": "Enterococcus",
        "organism_ncbi_id": "1350",
        "subject_value": "None",
        "control_value": "None",
        "ratio": "None",
        "method_name": "qPCR",
        "sample_name": "Faeces",
        "host_type": "Human",
        "publication_id": "1",
        "control_name": "Healthy control",
        "response_name": "None",
        "response_unit": "None",
    },
]
_DISEASES = [
    {
        "disease_id": "1",
        "name": "Autism",
        "stage": "None",
        "meddra_id": "10080683",
        "meddra_level": "preferred_term",
        "abbreviations": "None",
    },
    {
        "disease_id": "2",
        "name": "Crohn's disease",
        "stage": "None",
        "meddra_id": "10011401",
        "meddra_level": "preferred_term",
        "abbreviations": "CD",
    },
]
_ORGANISMS = [
    {
        "organism_id": "1",
        "name": "Lactobacillus",
        "scientific_name": "Lactobacillus",
        "ncbi_id": "1591",
        "incertae_sedis": "False",
        "silva_accession_number_base": "AATA01000092",
    },
    {
        "organism_id": "2",
        "name": "Enterococcus",
        "scientific_name": "Enterococcus",
        "ncbi_id": "1350",
        "incertae_sedis": "False",
        "silva_accession_number_base": "None",
    },
]
_PUBLICATIONS = [
    {
        "publication_id": "1",
        "title": "Gastrointestinal microbiota in children with autism in Slovakia.",
        "first_author": "Tomova A",
        "outlet": "Physiology & Behavior",
        "volume": "138",
        "start_page": "179",
        "end_page": "187",
        "year_of_publication": "2015",
        "pubmed_url": "https://www.ncbi.nlm.nih.gov/pubmed/25446201",
        "doi": "None",
        "age_of_subjects_given": "y",
        "controls_matched_for_possible_confounding_factors": "n",
        "measure_of_variance_reported": "yes, only in graphs",
    },
]

_cached_path: Path | None = None


def build_fixture_db(target: Path) -> None:
    """Write the mini fixture DB to ``target`` (canned records, no network)."""
    write_db(
        target,
        experiments=_EXPERIMENTS,
        diseases=_DISEASES,
        organisms=_ORGANISMS,
        publications=_PUBLICATIONS,
    )


def fixture_db_path() -> Path:
    """Build the fixture DB once per process and return its path."""
    global _cached_path
    if _cached_path is None:
        directory = Path(tempfile.mkdtemp(prefix="disbiome_fixture_"))
        _cached_path = directory / "disbiome.sqlite"
        build_fixture_db(_cached_path)
    return _cached_path
