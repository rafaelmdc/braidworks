"""Runnable interface artifacts rendered from one validated prepared query."""

import shlex

from braidworks.core.executor import ExpandMode
from braidworks.core.query import PreparedQuery


def python_artifact(prepared: PreparedQuery) -> str:
    """Use the core service; generated scripts need no toolkit or web dependencies."""
    return (
        "import asyncio\nimport json\n"
        "from braidworks.core import (QueryRequest, prepare_query, execute_query,\n"
        "    build_registry_from_entry_points)\n\n"
        "async def main():\n"
        "    registry = build_registry_from_entry_points()\n"
        f"    request = QueryRequest.from_json({prepared.request.to_json()!r})\n"
        "    prepared = prepare_query(registry, request)\n"
        "    result = await execute_query(registry, prepared)\n"
        "    print(json.dumps(result.to_json(), ensure_ascii=False))\n\n"
        "asyncio.run(main())\n"
    )


def cli_artifact(prepared: PreparedQuery, have: dict, *, batch: dict | None = None) -> str:
    request = prepared.request
    options = request.options
    tokens = ["braidworks", "weave"]
    if batch is not None:
        tokens += ["--in-file", "-"]
        if batch.get("format", "lines") == "lines":
            tokens += ["--in-type", batch["input_type"]]
    for key, value in have.items():
        tokens += ["--have", f"{key}={value}"]
    if request.targets:
        tokens += ["--want", ",".join(sorted(request.targets))]
    for token in request.traversals:
        tokens += ["--traverse", token]
    for cid, values in prepared.effective_params.items():
        for name, value in values.items():
            tokens += ["--param", f"{cid}:{name}={value}"]
    expansion = options.expand_policy
    expand = (
        "all"
        if expansion.mode is ExpandMode.ALL
        else f"top:{expansion.k}"
        if expansion.mode is ExpandMode.TOP_K
        else "none"
    )
    tokens += [
        "--policy",
        options.backend_policy.value,
        "--expand",
        expand,
        "--max-expansion",
        str(options.max_expansion),
        "--review-policy",
        options.review_policy.value,
        "--confidence-threshold",
        str(options.confidence_threshold),
    ]
    command = shlex.join(tokens)
    if batch is not None:
        command = "printf '%s' " + shlex.quote(batch["text"]) + " | " + command
    return command


def path_artifact(prepared: PreparedQuery, have: dict, *, batch: dict | None = None) -> str:
    if prepared.traversals:
        return "Traversal has no single type path."
    if batch is not None:
        return "The batch plans each distinct input-type group independently."
    return shlex.join(
        [
            "braidworks",
            "path",
            "--from",
            ",".join(have),
            "--to",
            ",".join(sorted(prepared.request.targets)),
            "--policy",
            prepared.request.options.backend_policy.value,
        ]
    )
