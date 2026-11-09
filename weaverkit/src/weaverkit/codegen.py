"""Runnable interface artifacts rendered from one validated prepared query."""

import shlex

from braidworks.core.executor import ExpandMode
from braidworks.core.query import PreparedQuery


def python_artifact(prepared: PreparedQuery, *, persistence=None) -> str:
    """The query as the ``bw.Session(...).get(...)`` code the Python tutorials teach.

    The script needs only braidworks and the sources; it prints the summary and writes
    the same CSV the browser downloads. Cache lifetimes and leases keep their defaults
    (the command-line artifact carries them when set).
    """
    request = prepared.request
    options = request.options
    rows = [{t: ss.get(t).value for t in sorted(ss.available_types())} for ss in request.inputs]
    types = {key for row in rows for key in row}
    session_args = []
    if options.backend_policy.value != "local_first":
        session_args.append(f"backend={options.backend_policy.value!r}")
    if persistence is not None and persistence.cache_db:
        session_args.append(f"cache={persistence.cache_db!r}")
    if persistence is not None and persistence.run_db:
        session_args.append(f"runs={persistence.run_db!r}")

    get_args = []
    if len(types) == 1 and all(len(row) == 1 for row in rows):
        (have,) = types
        get_args.append(repr([row[have] for row in rows]))
        get_args.append(f"have={have!r}")
    else:  # rows that start from different fields name their own types
        get_args.append(repr(rows))
    if request.targets:
        get_args.append(f"want={sorted(request.targets)!r}")
    if request.traversals:
        get_args.append(f"for_each={list(request.traversals)!r}")
    params: dict[str, dict] = {}
    for cap, values in (request.params or {}).items():
        params.setdefault(cap, {}).update(values)
    loose = {}
    for cap, name, value in request.parameter_items:
        if cap is None:
            loose[name] = value
        else:
            params.setdefault(cap, {})[name] = value
    if params:
        get_args.append(f"params={params!r}")
    expansion = options.expand_policy
    expand = (
        "all"
        if expansion.mode is ExpandMode.ALL
        else f"top:{expansion.k}"
        if expansion.mode is ExpandMode.TOP_K
        else None
    )
    if expand is not None and not (request.traversals and expand == "all"):
        get_args.append(f"expand={expand!r}")
    if options.review_policy.value != "halt":
        get_args.append(f"review={options.review_policy.value!r}")
    if options.confidence_threshold:
        get_args.append(f"min_confidence={options.confidence_threshold!r}")
    if options.max_expansion != 10_000:
        get_args.append(f"max_expansion={options.max_expansion!r}")
    if persistence is not None and persistence.run_id:
        get_args.append(f"run_id={persistence.run_id!r}")
    get_args.extend(f"{name}={value!r}" for name, value in loose.items())

    body = "".join(f"        {arg},\n" for arg in get_args)
    return (
        "import braidworks as bw\n\n"
        f"with bw.Session({', '.join(session_args)}) as s:\n"
        "    result = s.get(\n"
        f"{body}"
        "    )\n\n"
        "print(result.summary())\n"
        'result.to_csv("braidworks-results.csv")  # the table the browser downloads\n'
    )


def cli_artifact(
    prepared: PreparedQuery, have: dict, *, batch: dict | None = None, persistence=None
) -> str:
    request = prepared.request
    options = request.options
    tokens = ["braidworks", "get"]
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
    if persistence is not None:
        if persistence.cache_db:
            tokens += [
                "--cache-db",
                persistence.cache_db,
                "--cache-positive-ttl",
                str(persistence.cache_policy.positive_ttl),
                "--cache-negative-ttl",
                str(persistence.cache_policy.negative_ttl),
                "--cache-max-bytes",
                str(persistence.cache_policy.max_payload_bytes),
            ]
        if persistence.run_db:
            tokens += [
                "--run-db",
                persistence.run_db,
                "--lease-seconds",
                str(persistence.lease_seconds),
            ]
            if persistence.run_id:
                tokens += ["--run-id", persistence.run_id]
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
