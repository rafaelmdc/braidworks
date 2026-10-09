"""A tiny, deterministic UniProtKB stand-in for ``weaverkit verify --strict`` golden.

The api backend is *always configured* (UniProtKB REST needs no key), so golden
would otherwise hit the live service — flaky and non-reproducible. This module
serves canned ``/uniprotkb/search`` responses for five real accessions and
"TP53", whose top hit
is human p53 (P04637), carrying every field the mapper reads. The shape mirrors a
real reviewed entry (nested proteinDescription, genes, organism.taxonId, a FUNCTION
comment, sequence.length) so the mapping path is exercised exactly as in production.
``build_uniprot_weaver_fixture()`` (in factory.py) wires the backend to this transport.
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qs

import httpx

# A real-shaped reviewed (Swiss-Prot) entry for human TP53.
_TP53 = {
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "primaryAccession": "P04637",
    "uniProtkbId": "P53_HUMAN",
    "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
    "annotationScore": 5.0,
    "proteinDescription": {
        "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}
    },
    "genes": [{"geneName": {"value": "TP53"}}],
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [
                {
                    "value": (
                        "Multifunctional transcription factor that induces cell cycle "
                        "arrest, DNA repair or apoptosis upon binding to its target DNA "
                        "sequence (PubMed:11025664). Acts as a tumor suppressor."
                    )
                }
            ],
        }
    ],
    "sequence": {"length": 393},
}

# Minimal actual REST projections observed 2026-10-09; offline identity/order fixtures.
_ENTRIES = {
    "A0A087WT22": {
        "primaryAccession": "A0A087WT22",
        "entryType": "UniProtKB unreviewed (TrEMBL)",
        "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
        "sequence": {"length": 187},
    },
    "P02340": {
        "primaryAccession": "P02340",
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "organism": {"scientificName": "Mus musculus", "taxonId": 10090},
        "sequence": {"length": 390},
    },
    "P38398": {
        "primaryAccession": "P38398",
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
        "sequence": {"length": 1863},
    },
    "Q00987": {
        "primaryAccession": "Q00987",
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
        "sequence": {"length": 491},
    },
}
_ENTRIES["P04637"] = _TP53

# Actual 2026-10-09 full-entry projections; annotation arrays explicitly truncated.
_DESCRIPTION_ENTRIES = {
    "P04637": {
        "primaryAccession": "P04637",
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
        "sequence": {
            "value": "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD",
            "length": 393,
            "molWeight": 43653,
            "crc64": "AD5C149FD8106131",
            "md5": "C133DFCE69F606F20865E9008199F852",
        },
        "entryAudit": {
            "firstPublicDate": "1987-08-13",
            "lastAnnotationUpdateDate": "2026-09-02",
            "lastSequenceUpdateDate": "2009-11-24",
            "entryVersion": 315,
            "sequenceVersion": 4,
        },
        "proteinExistence": "1: Evidence at protein level",
        "features": [
            {
                "type": "Chain",
                "location": {
                    "start": {"value": 1, "modifier": "EXACT"},
                    "end": {"value": 393, "modifier": "EXACT"},
                },
                "description": "Cellular tumor antigen p53",
                "featureId": "PRO_0000185703",
            }
        ],
        "references": [{"citation": {"id": "4006916"}}],
        "comments": [
            {
                "texts": [
                    {
                        "evidences": [
                            {"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "19776115"}
                        ],
                        "value": "(Microbial infection) Interacts with human "
                        "cytomegalovirus/HHV-5 protein UL123",
                    }
                ],
                "commentType": "SUBUNIT",
            }
        ],
    },
    "A0A087WT22": {
        "primaryAccession": "A0A087WT22",
        "entryType": "UniProtKB unreviewed (TrEMBL)",
        "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
        "sequence": {
            "value": "MAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQMLLDLRWCYFLINSS",
            "length": 187,
            "molWeight": 21416,
            "crc64": "C60E05EDDBC150C2",
            "md5": "07AE58ADC8D69F12DCB6EBA9B83FAEDF",
        },
        "entryAudit": {
            "firstPublicDate": "2014-10-29",
            "lastAnnotationUpdateDate": "2026-09-02",
            "lastSequenceUpdateDate": "2014-10-29",
            "entryVersion": 74,
            "sequenceVersion": 1,
        },
        "proteinExistence": "1: Evidence at protein level",
        "features": [
            {
                "type": "Domain",
                "location": {
                    "start": {"value": 1, "modifier": "EXACT"},
                    "end": {"value": 129, "modifier": "EXACT"},
                },
                "description": "p53 DNA-binding",
                "evidences": [{"evidenceCode": "ECO:0000259", "source": "Pfam", "id": "PF00870"}],
            }
        ],
        "references": [{"citation": {"id": "11237011"}}],
        "comments": [
            {
                "texts": [
                    {
                        "evidences": [
                            {"evidenceCode": "ECO:0000256", "source": "RuleBase", "id": "RU003304"}
                        ],
                        "value": "Binds DNA as a homotetramer",
                    }
                ],
                "commentType": "SUBUNIT",
            }
        ],
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/uniprotkb/search"):
        query = request.url.params.get("query", "")
        accessions = re.findall(r"accession:([A-Z0-9]+)", query)
        if accessions and request.url.params.get("size") == "500":
            entries = [_DESCRIPTION_ENTRIES.get(acc, _ENTRIES.get(acc)) for acc in accessions]
            return httpx.Response(
                200,
                json={"results": [entry for entry in entries if entry]},
                headers={"x-uniprot-release": "2026_03"},
            )
        accession = re.search(r"accession:([A-Z0-9]+)", query)
        entry = _ENTRIES.get(accession[1]) if accession else (_TP53 if "TP53" in query else None)
        results = [entry] if entry else []
        return httpx.Response(200, content=json.dumps({"results": results}))
    # ID-mapping (map_* capabilities): submit -> poll -> results. The job id echoes the
    # target db; GeneID 7157 -> P04637 (both reviewed and full jobs), so the golden is a
    # single deterministic accession (count = 1).
    if path.endswith("/idmapping/run"):
        form = parse_qs(request.content.decode())
        to_db = (form.get("to") or [""])[0]
        source = (form.get("ids") or [""])[0]
        return httpx.Response(200, content=json.dumps({"jobId": f"job-{to_db}|{source}"}))
    if "/idmapping/status/" in path:
        return httpx.Response(200, content=json.dumps({"jobStatus": "FINISHED"}))
    if "/idmapping/results/" in path:
        source = path.rsplit("|", 1)[-1]
        rows = (
            [{"from": source, "to": "P04637"}] if source in {"7157", "9606.ENSP00000269305"} else []
        )
        return httpx.Response(200, content=json.dumps({"results": rows}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned UniProt responses (no network)."""
    return httpx.AsyncClient(
        base_url="https://uniprot.test", transport=httpx.MockTransport(_handler)
    )
