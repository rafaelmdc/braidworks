"""Bounded offline work/memory probes; run with the isolated workspace environment.

UV_NO_SYNC=1 uv run python tools/benchmark_weaver_work.py --out /tmp/work.json
No downloads. Temporary fixture databases are deleted on exit. Timing and traced
Python allocations are descriptive measurements, not CI pass/fail thresholds.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import tempfile
import time
import tracemalloc
from pathlib import Path
from unittest.mock import patch

from agora_weaver import dataset as agora
from disbiome_weaver import fixture as disbiome_fixture
from disbiome_weaver import setup as disbiome_setup
from disbiome_weaver.backends.local import DisbiomeLocalBackend
from faprotax_weaver.backends import local as faprotax
from gtdb_weaver import taxonomy, tree
from mondo_weaver import setup as mondo_setup
from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.fixture import _term


def measure(operation):
    statements = []
    connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        con = connect(*args, **kwargs)
        con.set_trace_callback(
            lambda sql: (
                statements.append(sql)
                if sql.lstrip().upper().startswith(("SELECT", "WITH"))
                else None
            )
        )
        return con

    tracemalloc.start()
    started = time.perf_counter()
    with patch("sqlite3.connect", traced_connect):
        result = operation()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    selects = [sql for sql in statements if sql.lstrip().upper().startswith(("SELECT", "WITH"))]
    return {
        "seconds": round(elapsed, 6),
        "peak_python_bytes": peak,
        "selects": len(selects),
        "recursive_selects": sum("WITH RECURSIVE" in sql for sql in selects),
        "digest": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
    }


def fetch(backend, cap, queries, outputs, groups):
    records = asyncio.run(
        backend.fetch(
            cap, queries, requested_outputs=frozenset(outputs), groups_to_compute=frozenset(groups)
        )
    )
    return [
        {
            "found": record.found,
            "error": record.error,
            "values": {key: record.values[key] for key in outputs if key in record.values},
        }
        for record in records
    ]


def balanced_tree(start, count):
    if count == 1:
        return f"leaf{start}:1"
    split = count // 2
    return f"({balanced_tree(start, split)},{balanced_tree(start + split, count - split)}):1"


def profile(root, size, queries):
    results = {
        "scope": {
            "disbiome_rows": 500,
            "duplicate_queries": queries,
            "mondo_chain_nodes": 30,
            "agora_models": 30,
            "gtdb_rows": size,
            "tree_leaves": 2000,
            "memory_scope": "tracemalloc Python allocations; excludes SQLite/native allocations",
        }
    }
    path = root / "disbiome.sqlite"
    experiments = [
        {**disbiome_fixture._EXPERIMENTS[0], "experiment_id": str(index + 1)}
        for index in range(500)
    ]
    publications = [{**disbiome_fixture._PUBLICATIONS[0], "bounded_probe_padding": "x" * 2048}]
    disbiome_setup.write_db(
        path,
        experiments=experiments,
        diseases=disbiome_fixture._DISEASES,
        organisms=disbiome_fixture._ORGANISMS,
        publications=publications,
    )
    for group, outputs in [
        ("summary", ["microbe.disease.names", "microbe.disease.count"]),
        ("full", ["microbe.disease.records"]),
    ]:
        backend = DisbiomeLocalBackend(db_path=path)
        results[f"disbiome_{group}"] = measure(
            lambda backend=backend, outputs=outputs, group=group: fetch(
                backend,
                "disbiome.list_diseases",
                [{"ncbi.taxon.species_id": 1591}] * queries,
                outputs,
                [group],
            )
        )

    path = root / "mondo.sqlite"
    terms = [
        _term(
            f"MONDO:{index:07}",
            f"disease {index}",
            parents=[f"MONDO:{index - 1:07}"] if index else [],
            xrefs=[("MESH", "D1", True)] if index == 29 else [],
        )
        for index in range(30)
    ]
    mondo_setup.write_db(path, data_version="bounded-probe", terms=terms)
    for label, outputs, groups in [
        ("identity", ["disease.mondo.id"], ["identity"]),
        (
            "graph",
            ["disease.ontology.depth", "disease.ontology.ancestors"],
            ["identity", "term", "ancestors"],
        ),
    ]:
        backend = MondoLocalBackend(db_path=path)
        results[f"mondo_{label}"] = measure(
            lambda backend=backend, outputs=outputs, groups=groups: fetch(
                backend,
                "mondo.lookup_by_mesh",
                [{"disease.mesh.id": "D1"}] * queries,
                outputs,
                groups,
            )
        )

    with sqlite3.connect(root / "agora.sqlite") as con:
        con.executescript(agora._SCHEMA)
        ids = [f"model{index:03}" for index in range(30)]
        con.executemany(
            "INSERT INTO model_coverage VALUES (?, 'processed', 50, 'fixture', NULL)",
            [(rid,) for rid in ids],
        )
        con.executemany(
            "INSERT INTO reaction VALUES (?, ?)",
            [(rid, f"rxn{index:03}") for rid in ids for index in range(50)],
        )
        sql = []
        con.set_trace_callback(sql.append)
        results["agora_reactions"] = measure(lambda: agora.reactions_for(con, ids))
        results["agora_reactions"]["selects"] = len(sql)

    faprotax._load_groups()  # separate warm parsed-data matching from first-load cost
    with patch.object(faprotax, "_functional_groups", wraps=faprotax._functional_groups) as matcher:
        results["faprotax_duplicates"] = measure(
            lambda: fetch(
                faprotax.FaprotaxLocalBackend(),
                "describe_ecology",
                [{"ncbi.taxon.lineage": [{"name": "Methylococcaceae"}, {"name": "Methylococcus"}]}]
                * queries,
                ["microbe.ecology.functional_groups"],
                ["ecology"],
            )
        )
        results["faprotax_duplicates"]["matcher_calls"] = matcher.call_count

    for count in (size // 10, size):
        path = root / f"gtdb-{count}.sqlite"

        def build(count=count, path=path):
            taxonomy.build_crosswalk_db(
                (
                    (index, f"d__Bacteria;s__Species {index}", index % 10 == 0, f"GCF_{index}")
                    for index in range(count)
                ),
                path,
                release="bounded-probe",
            )
            with taxonomy.open_ro(path) as con:
                return con.execute("SELECT COUNT(*) FROM classification").fetchone()[0]

        results[f"gtdb_build_{count}"] = measure(build)
    text = balanced_tree(0, 2000) + ";"
    results["gtdb_all_rootpaths"] = measure(lambda: len(tree.load_rootpaths([text])))
    if hasattr(tree, "load_rootpath_index"):
        results["gtdb_indexed_paths"] = measure(
            lambda: tree.load_rootpath_index([text]).path_for("leaf1999")
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--size", type=int, default=10000)
    parser.add_argument("--queries", type=int, default=20)
    args = parser.parse_args()
    if not 10 <= args.size <= 100000 or not 1 <= args.queries <= 100:
        parser.error("size must be 10..100000 and queries 1..100")
    with tempfile.TemporaryDirectory(prefix="braidworks-work-probe-") as temporary:
        result = profile(Path(temporary), args.size, args.queries)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote offline work measurements -> {args.out}")


if __name__ == "__main__":
    main()
