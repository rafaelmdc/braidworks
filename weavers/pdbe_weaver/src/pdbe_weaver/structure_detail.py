"""Pure PDBe/SIFTS projections preserving numbering and provider identity."""

from __future__ import annotations

import gzip
import hashlib
import io
import xml.etree.ElementTree as ET


class DetailFormatError(ValueError):
    """A requested source detail cannot establish its schema or identity."""


SIFTS_COMPRESSED_LIMIT = 10 * 1024 * 1024
SIFTS_XML_LIMIT = 50 * 1024 * 1024


def sifts_residues(content: bytes, pdb_id: str, url: str) -> dict:
    with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
        xml = stream.read(SIFTS_XML_LIMIT + 1)
    if len(xml) > SIFTS_XML_LIMIT or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise DetailFormatError("SIFTS XML exceeds limit or contains declarations")
    root = ET.fromstring(xml)
    if root.attrib.get("dbAccessionId", "").lower() != pdb_id.lower():
        raise DetailFormatError("SIFTS entry identity mismatch")
    ns = {"s": "http://www.ebi.ac.uk/pdbe/docs/sifts/eFamily.xsd"}
    rows = []
    for entity in root.findall("s:entity", ns):
        for segment in entity.findall("s:segment", ns):
            for residue in segment.findall("s:listResidue/s:residue", ns):
                rows.append(
                    {
                        "entity": dict(entity.attrib),
                        "segment": dict(segment.attrib),
                        "residue": dict(residue.attrib),
                        "cross_references": [
                            dict(ref.attrib) for ref in residue.findall("s:crossRefDb", ns)
                        ],
                        "annotations": [
                            {"attributes": dict(value.attrib), "text": value.text}
                            for value in residue.findall("s:residueDetail", ns)
                        ],
                    }
                )
    if not rows:
        raise DetailFormatError("SIFTS entry has no residue records")
    return {
        "pdb_id": pdb_id.lower(),
        "records": rows,
        "count": len(rows),
        "source": {
            "url": url,
            "sha256": hashlib.sha256(content).hexdigest(),
            "entry": dict(root.attrib),
            "databases": [dict(db.attrib) for db in root.findall("s:listDB/s:db", ns)],
        },
        "interpretation": "explicit residue cross-references; numbering strings and insertion codes preserved; unobserved residues retain source annotations",
    }


def source_detail(body, requested, group):
    if not isinstance(body, dict):
        raise DetailFormatError("PDBe detail envelope must be keyed by entry")
    result = {}
    for key, value in body.items():
        if not isinstance(key, str) or key.lower() not in requested:
            raise DetailFormatError("PDBe detail contains an unrequested entry")
        if group == "mappings":
            if not isinstance(value, dict) or not isinstance(value.get("UniProt"), dict):
                raise DetailFormatError("PDBe mappings require a UniProt object")
            for mapping in value["UniProt"].values():
                if not isinstance(mapping, dict) or not isinstance(mapping.get("mappings"), list):
                    raise DetailFormatError("PDBe UniProt mappings require ranges")
                if any(not isinstance(row, dict) for row in mapping["mappings"]):
                    raise DetailFormatError("PDBe UniProt ranges must be objects")
        elif not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise DetailFormatError("PDBe detail records must be object lists")
        else:
            field = {
                "entities": "entity_id",
                "assemblies": "assembly_id",
                "ligands": "chem_comp_id",
            }[group]
            if any(row.get(field) is None for row in value):
                raise DetailFormatError(f"PDBe {group} records require {field}")
        result[key.lower()] = value
    return result


def coordinate_artifacts(pdb_id, assemblies=None):
    pid = pdb_id.lower()
    base = "https://www.ebi.ac.uk/pdbe/entry-files/download"
    return {
        "pdb_id": pid,
        "entry_mmcif_url": f"{base}/{pid}_updated.cif",
        "assemblies": [
            {
                "assembly_id": row["assembly_id"],
                "mmcif_gz_url": f"{base}/{pid}-assembly-{row['assembly_id']}.cif.gz",
            }
            for row in assemblies
        ]
        if assemblies is not None
        else None,
        "acquired": False,
        "scope": "provider download URL conventions; entry availability and assembly identities come from metadata, artifact contents not downloaded",
    }
