"""Shared helpers for thin CLI command modules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from taxonomy_resolver.policy import MatchType, ResolutionStatus, WarningCode
from taxonomy_resolver.schemas import (
    BatchResolveRequest,
    DecisionAction,
    DecisionRecord,
    ResolveRequest,
)
from taxonomy_resolver.service import TaxonomyResolverService


def read_json(path: Path) -> Any:
    """Load JSON from disk using UTF-8."""

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write indented JSON to disk using UTF-8."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def print_json(payload: Any) -> None:
    """Print stable JSON to stdout."""

    print(json.dumps(payload, indent=2))


def build_service(args: argparse.Namespace) -> TaxonomyResolverService:
    """Create a resolver service from CLI arguments."""

    return TaxonomyResolverService(
        taxonomy_db_path=args.db,
        cache_db_path=getattr(args, "cache_db", None),
    )


def parse_batch_request(payload: Any) -> BatchResolveRequest:
    """Parse batch input JSON into the internal request contract."""

    if isinstance(payload, list):
        items = [ResolveRequest(**item) for item in payload]
        return BatchResolveRequest(items=items)
    if isinstance(payload, dict):
        items_payload = payload.get("items", [])
        items = [ResolveRequest(**item) for item in items_payload]
        return BatchResolveRequest(items=items, batch_id=payload.get("batch_id"))
    raise ValueError("Batch input must be a list of requests or an object with an 'items' key.")


def parse_decisions(payload: Any) -> list[DecisionRecord]:
    """Parse decision JSON into decision records."""

    if isinstance(payload, dict) and "decisions" in payload:
        payload = payload["decisions"]
    if not isinstance(payload, list):
        raise ValueError("Decision input must be a list or an object with a 'decisions' key.")

    decisions: list[DecisionRecord] = []
    for item in payload:
        item = dict(item)
        item["action"] = DecisionAction(item["action"])
        item["match_type"] = MatchType(item["match_type"])
        item["status"] = ResolutionStatus(item["status"])
        item["warnings"] = [WarningCode(warning) for warning in item.get("warnings", [])]
        decisions.append(DecisionRecord(**item))
    return decisions
