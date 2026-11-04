"""Pure projection of correlated Wikibase entity responses; English joins stay English."""

import re
from typing import Any

from braidworks.core import LookupRecord


class InvalidEntityResponse(ValueError):
    """A source shape or identifier correlation cannot establish an exact entity."""


def entity_records(body: Any, ids: list[str], language: str) -> dict[str, LookupRecord]:
    if not isinstance(body, dict) or not isinstance(body.get("entities"), dict) or "error" in body:
        raise InvalidEntityResponse("Wikibase response must contain entities")
    redirects = {}
    if not isinstance(body.get("redirects", []), list):
        raise InvalidEntityResponse("Wikibase redirects must be a list")
    for row in body.get("redirects", []):
        if (
            not isinstance(row, dict)
            or row.get("from") not in ids
            or not re.fullmatch(r"Q[1-9][0-9]*", str(row.get("to", "")))
        ):
            raise InvalidEntityResponse("Uncorrelated Wikibase redirect")
        if row["from"] in redirects and redirects[row["from"]] != row["to"]:
            raise InvalidEntityResponse("Conflicting Wikibase redirect")
        redirects[row["from"]] = row["to"]
    expected = set(ids) | set(redirects.values())
    if set(body["entities"]) - expected:
        raise InvalidEntityResponse("Wikibase response contains an unrequested entity")
    records = {}
    for requested in ids:
        current = redirects.get(requested, requested)
        entity = body["entities"].get(current)
        if not isinstance(entity, dict):
            raise InvalidEntityResponse(
                "Wikibase omitted an entity without explicit missing status"
            )
        query = {"wikidata.qid": requested}
        if "missing" in entity:
            records[requested] = LookupRecord(query=query, found=False)
            continue
        if entity.get("id") != current:
            raise InvalidEntityResponse(
                "Wikibase entity ID conflicts with requested/redirected identity"
            )
        fields = {}
        for name in ["labels", "descriptions", "sitelinks", "claims"]:
            if not isinstance(entity.get(name), dict):
                raise InvalidEntityResponse(f"Wikibase {name} must be an object")
            fields[name] = entity[name]
        scientific_names = []
        for claim in fields["claims"].get("P225", []):
            if not isinstance(claim, dict) or not isinstance(claim.get("mainsnak"), dict):
                raise InvalidEntityResponse("Wikibase scientific name claim malformed")
            snak = claim["mainsnak"]
            if snak.get("snaktype") == "value":
                datavalue = snak.get("datavalue")
                if not isinstance(datavalue, dict):
                    raise InvalidEntityResponse("Wikibase scientific name datavalue malformed")
                value = datavalue.get("value")
                if not isinstance(value, str):
                    raise InvalidEntityResponse("Wikibase scientific name must be a string")
                scientific_names.append(value)
        if not scientific_names:
            records[requested] = LookupRecord(query=query, found=False)
            continue

        label, label_language = _localized(fields["labels"], language)
        description, description_language = _localized(fields["descriptions"], language)
        values = {
            "wikidata.qid": current,
            "wikidata.sitelinks": len(fields["sitelinks"]),
            "wikidata.identity": {
                "requested_qid": requested,
                "current_qid": current,
                "redirected": requested != current,
                "scientific_names": sorted(set(scientific_names)),
                "source_claims": {key: fields["claims"].get(key, []) for key in ["P225", "P685"]},
            },
            "wikidata.localized": {
                "label": label,
                "description": description,
                "requested_language": language,
                "label_language": label_language,
                "description_language": description_language,
                "fallback_language": "en",
            },
        }
        english = fields["sitelinks"].get("enwiki")
        if english is not None:
            if (
                not isinstance(english, dict)
                or english.get("site") != "enwiki"
                or not isinstance(english.get("title"), str)
            ):
                raise InvalidEntityResponse("Wikibase English sitelink malformed")
            values["wikipedia.title"] = english["title"].replace(" ", "_")
        records[requested] = LookupRecord(query=query, found=True, values=values)
    return records


def _localized(values: dict, language: str) -> tuple[str | None, str | None]:
    row = values.get(language) or values.get("en")
    if row is None:
        return None, None
    if (
        not isinstance(row, dict)
        or not isinstance(row.get("value"), str)
        or not isinstance(row.get("language"), str)
    ):
        raise InvalidEntityResponse("Wikibase localized value must retain its actual language")
    return row["value"], row["language"]
