"""Differential probe; run from repo root with the provider script path as argument.

Download provider FAPROTAX 1.2.12 privately; do not commit its software/archive.
Only named pure/reference-parser functions are loaded; no upstream CLI is run.
Results go under ignored .audit-local/implementation. No numpy/BIOM install needed.
"""

import ast
import fnmatch
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

from faprotax_weaver.backends.local import _functional_groups, _load_rules

source = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(".audit-local/implementation/faprotax-reference/collapse_table.py")
)
names = {
    "whichPrefix",
    "open_file",
    "split_at_first_whitespace",
    "parse_group_name_and_metadata",
    "read_groups_from_list",
    "read_groups",
    "find_matches_to_words_expression",
    "assign_records_to_groups",
}
parsed = ast.parse(source.read_text())
module = ast.Module(
    body=[node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in names],
    type_ignores=[],
)
namespace = {
    "sys": sys,
    "re": re,
    "fnmatch": fnmatch,
    "gzip": gzip,
    "set_operations_keywords": ["add_group:", "subtract_group:", "intersect_group:"],
}
expected_sha256 = "00302f375a2e0465d2bd397a2cdb9d576cd9317e664b3b659d04d14f08675c17"
if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
    raise ValueError("Provider reference hash differs; review the new source before executing")
# Intentional oracle execution: selected functions from the verified provider file.
exec(compile(module, str(source), "exec"), namespace)  # noqa: S102
db = "weavers/faprotax_weaver/src/faprotax_weaver/data/FAPROTAX.txt"
members, groups, metadata, all_members, _ = namespace["read_groups"](
    db, "", "", "", "#", False, False, True, False, "", "", False, ""
)
lineages = [
    ["Methanosarcina", "Methanosarcina barkeri"],
    ["Bacteria", "Cyanobacteriia", "chloroplast"],
    ["Bacteria", "Cyanobacteriia"],
    ["Bacteria", "Cyanobacteriia", "Melainabacteria"],
    ["Methylococcus"],
    ["Methanosarcinaceae", "Methanosarcina", "Methanosarcina barkeriana"],
]
for group in _load_rules().values():
    for rule in group.rules:
        if rule.operation == "member":
            words = [w for w in rule.value.split("*") if w]
            # Include source token strings and simulated binomials, plus suffix false positives.
            lineages.extend(
                [words, words[:-1] + [" ".join(words[-2:])], [word + "xyz" for word in words]]
            )
labels = [";".join(row) for row in lineages]
assignments, *_ = namespace["assign_records_to_groups"](
    groups, members, all_members, labels, True, "-", "words"
)
expected = [
    sorted(groups[g] for g in range(len(groups)) if i in assignments[g]) for i in range(len(labels))
]
mismatches = [
    {"lineage": row, "ours": _functional_groups(row), "reference": truth}
    for row, truth in zip(lineages, expected)
    if _functional_groups(row) != truth
]
result = {
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "groups": len(groups),
    "cases": len(labels),
    "mismatches": len(mismatches),
    "examples": [{"lineage": r, "groups": e} for r, e in zip(lineages[:6], expected[:6])],
}
Path(".audit-local/implementation/faprotax-oracle-result.json").write_text(
    json.dumps(result, indent=2)
)
print(json.dumps(result, indent=2))
print("first mismatches", mismatches[:3])
assert not mismatches
