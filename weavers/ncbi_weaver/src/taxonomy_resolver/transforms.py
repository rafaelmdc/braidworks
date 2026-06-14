"""Configurable fallback transforms applied before giving up on simple inputs.

The goal is to keep normalization strict while still allowing explicit,
review-safe rewrite rules such as stripping placeholder suffixes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .policy import WarningCode


@dataclass(frozen=True, slots=True)
class TransformRule:
    """One configurable affix-stripping rule."""

    name: str
    position: str
    tokens: tuple[str, ...]
    warnings: tuple[WarningCode, ...]


@dataclass(frozen=True, slots=True)
class AppliedTransform:
    """A transformed candidate generated from the original observed string."""

    rule_name: str
    transformed_name: str
    warnings: tuple[WarningCode, ...]


TRANSFORM_RULES = (
    TransformRule(
        name="strip_placeholder_suffix",
        position="suffix",
        tokens=("sp.", "spp."),
        warnings=(
            WarningCode.TRANSFORM_APPLIED,
            WarningCode.VAGUE_LABEL_DETECTED,
            WarningCode.PLACEHOLDER_LABEL_DETECTED,
        ),
    ),
)


def generate_transforms(name: str) -> list[AppliedTransform]:
    """Generate transformed variants using the configured rule set.

    The current implementation supports configurable token stripping on the
    prefix or suffix. It avoids hidden normalization changes by keeping these
    transforms as an explicit secondary stage.
    """

    stripped_name = name.strip()
    original_tokens = stripped_name.split()
    if not original_tokens:
        return []

    applied: list[AppliedTransform] = []
    seen_names: set[str] = set()

    for rule in TRANSFORM_RULES:
        if rule.position == "suffix":
            token = original_tokens[-1].lower()
            if token in rule.tokens and len(original_tokens) > 1:
                transformed_name = " ".join(original_tokens[:-1]).strip()
            else:
                continue
        elif rule.position == "prefix":
            token = original_tokens[0].lower()
            if token in rule.tokens and len(original_tokens) > 1:
                transformed_name = " ".join(original_tokens[1:]).strip()
            else:
                continue
        else:  # pragma: no cover - guarded by static rule definitions
            continue

        if transformed_name and transformed_name not in seen_names:
            seen_names.add(transformed_name)
            applied.append(
                AppliedTransform(
                    rule_name=rule.name,
                    transformed_name=transformed_name,
                    warnings=rule.warnings,
                )
            )

    return applied
