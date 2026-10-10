"""Private, immutable FAPROTAX rule grammar and ordered membership interpreter.

This is Braidworks' implementation of the bundled source grammar. The provider's
word mode treats alphanumerics and '-' as word characters, and '*' as intervening
text. It can therefore match epithet words inside full NCBI binomials.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from types import MappingProxyType


class RuleError(ValueError):
    """Malformed bundled definitions cannot establish functional affiliation."""


@dataclass(frozen=True)
class _Rule:
    operation: str
    value: str
    expression: re.Pattern[str] | None = None
    reference: str = ""
    line: int = 0


@dataclass(frozen=True)
class _Group:
    rules: tuple[_Rule, ...]
    attributes: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _word_expression(pattern: str) -> re.Pattern[str]:
    words = [word for word in pattern.lower().split("*") if word]
    if not words:
        raise RuleError("empty member pattern")
    # Unicode alphanumerics plus hyphens are word characters; underscores are
    # separators, matching the provider's default valid_word_symbols='-'.
    boundary = r"[^\W_\-]|-"
    return re.compile(
        ".*?".join(rf"(?<!{boundary}){re.escape(word)}(?!{boundary})" for word in words), re.DOTALL
    )


def _parse_groups(text: str) -> Mapping[str, _Group]:
    rules: dict[str, list[_Rule]] = {}
    attributes: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {}
    current = None
    for number, original in enumerate(text.splitlines(), 1):
        if not original.strip():
            current = None
            continue
        content, _, comment = original.partition("#")
        content = content.strip()
        if not content:
            continue
        if content[0] in "\"'":
            if len(content) < 2 or content[-1] != content[0]:
                raise RuleError(f"line {number}: unterminated quoted member")
            content = content[1:-1]
        operation, separator, value = content.partition(":")
        if operation in {"add_group", "subtract_group", "intersect_group"}:
            if current is None or not separator or not value.strip():
                raise RuleError(f"line {number}: group operation has no group or reference")
            rules[current].append(
                _Rule(operation, value.strip(), reference=comment.strip(), line=number)
            )
        elif current is None:
            name, *metadata = content.split(maxsplit=1)
            if not re.fullmatch(r"[A-Za-z0-9_]+", name) or name in rules:
                raise RuleError(f"line {number}: invalid or duplicate group {name!r}")
            current = name
            rules[name] = []
            entries = []
            for entry in metadata[0].split(";") if metadata else []:
                key, _, values = entry.partition(":")
                if key.strip():
                    entries.append((key.strip(), tuple(v.strip() for v in values.split(","))))
            attributes[name] = tuple(entries)
        else:
            rules[current].append(
                _Rule("member", content, _word_expression(content), comment.strip(), number)
            )
    if not rules:
        raise RuleError("source contains no functional groups")
    graph = {
        name: {rule.value for rule in members if rule.operation != "member"}
        for name, members in rules.items()
    }
    for name, references in graph.items():
        for reference in references:
            if reference not in rules:
                raise RuleError(f"group {name!r}: unknown reference {reference!r}")
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        raise RuleError("cyclic functional group references") from exc
    previous: set[str] = set()
    for name, references in graph.items():
        if not references <= previous:
            raise RuleError(f"group {name!r}: references must be defined beforehand")
        previous.add(name)
    return MappingProxyType(
        {name: _Group(tuple(members), attributes[name]) for name, members in rules.items()}
    )


def _evaluate(
    groups: Mapping[str, _Group], lineage_names: list[str], *, trace: dict | None = None
) -> list[str]:
    label = ";".join(name.lower() for name in lineage_names)
    memberships: dict[str, bool] = {}
    for name, group in groups.items():
        member = False
        operations = [] if trace is not None else None
        for rule in group.rules:
            before = member
            operand = (
                bool(rule.expression.search(label))
                if rule.operation == "member"
                else memberships[rule.value]
            )
            if rule.operation in {"member", "add_group"}:
                member |= operand
            elif rule.operation == "subtract_group":
                member &= not operand
            else:
                member &= operand
            # Matched member patterns and every group operation explain relevant
            # changes. Unmatched member patterns do not create enormous traces.
            if operations is not None and (operand or rule.operation != "member"):
                operations.append(
                    {
                        "operation": rule.operation,
                        "value": rule.value,
                        "operand": operand,
                        "before": before,
                        "after": member,
                        "reference": rule.reference,
                        "source_line": rule.line,
                    }
                )
        memberships[name] = member
        if trace is not None:
            trace[name] = {
                "member": member,
                "operations": operations,
                "attributes": {key: list(values) for key, values in group.attributes},
                "checked_member_patterns": sum(rule.operation == "member" for rule in group.rules),
            }
    return sorted(name for name, member in memberships.items() if member)
