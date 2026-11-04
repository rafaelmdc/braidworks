"""GTDB offline audit probes; writes only temporary databases."""

import tempfile
from pathlib import Path

from gtdb_weaver import taxonomy, tree
from gtdb_weaver.backends.api import _best_row

with tempfile.TemporaryDirectory(prefix="gtdb-audit-") as directory:
    root = Path(directory)
    rows = [
        (562, "d__Bacteria;s__Species A", True, "A"),
        (562, "d__Bacteria;s__Species B", True, "B"),
    ]
    for label, source in (("forward", rows), ("reverse", list(reversed(rows)))):
        path = root / f"{label}.sqlite"
        taxonomy.build_crosswalk_db(source, path, release="fixture")
        connection = taxonomy.open_ro(path)
        try:
            print(label, taxonomy.lookup(connection, {"ncbi.taxon.id": 562}))
        finally:
            connection.close()
    path = root / "forward.sqlite"
    taxonomy.build_crosswalk_db(
        [(999, "d__Bacteria;s__Species C", True, "C")], path, release="fixture-new"
    )
    connection = taxonomy.open_ro(path)
    try:
        print("Old taxid survives rebuild:", taxonomy.lookup(connection, {"ncbi.taxon.id": 562}))
    finally:
        connection.close()
for text in ("(A:1,B:1);garbage", "(A:nan,B:1);", "(A:-1,B:1);", ""):
    try:
        print("Accepted Newick", repr(text), tree.build_rootpaths(tree.parse_newick(text)))
    except Exception as error:  # noqa: BLE001 - audit records escaped exception types
        print(type(error).__name__, str(error))
paths = tree.load_rootpaths(["(A:0.01,B:0.02);", "(C:0.01,D:0.02);"])
print("Cross-domain synthetic distance:", tree.cophenetic(paths["A"], paths["C"]))
print(
    "Unrelated search accepted:",
    _best_row(
        [{"gtdbTaxonomy": "d__Bacteria;s__Unrelated species", "isGtdbSpeciesRep": True}],
        "No such species",
    ),
)
