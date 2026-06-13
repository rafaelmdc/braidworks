"""uniprot_weaver — UniProt protein identity (gene/protein query -> accession + taxid + annotation) weaver for Braidworks."""

from uniprot_weaver.factory import build_uniprot_weaver
from uniprot_weaver.provider import UniprotWeaverProvider, register
from uniprot_weaver.weaver import UniprotWeaver

__all__ = [
    "build_uniprot_weaver",
    "register",
    "UniprotWeaver",
    "UniprotWeaverProvider",
]
