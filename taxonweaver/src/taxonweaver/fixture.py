"""A tiny, deterministic taxonomy fixture — for golden/conformance, not production.

Builds a ~6-species synthetic NCBI taxonomy DB (the *Faecalibacterium* clade) from
inline ``nodes.dmp`` / ``names.dmp`` snippets, so ``weaverkit verify --strict`` and
the test suite can run real resolutions reproducibly without the ~70 MB download /
~1.2 GB build. This is the single source of the mini dump (the tests import it too).

See ``weaverkit/docs/decisions.md`` (Decision E): a synthetic fixture is the
first-class substrate for golden correctness; production-data coverage is a separate,
opt-in live test.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from taxonomy_resolver.build import build_taxonomy_database

NODES_DMP = """1\t|\t1\t|\tno rank\t|\t\t|\t8\t|\t0\t|\t1\t|\t0\t|\t1\t|\t0\t|\t0\t|\t0\t|\troot\t|
2\t|\t1\t|\tsuperkingdom\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1224\t|\t2\t|\tphylum\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
1236\t|\t1224\t|\tclass\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186801\t|\t1236\t|\torder\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
186803\t|\t186801\t|\tfamily\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
239934\t|\t186803\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
853\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
854\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
855\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
856\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
857\t|\t239934\t|\tspecies\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t\t|
"""

NAMES_DMP = """1\t|\troot\t|\t\t|\tscientific name\t|
2\t|\tBacteria\t|\tBacteria <prokaryote>\t|\tscientific name\t|
1224\t|\tBacillota\t|\t\t|\tscientific name\t|
1236\t|\tClostridia\t|\t\t|\tscientific name\t|
186801\t|\tClostridiales\t|\t\t|\tscientific name\t|
186803\t|\tOscillospiraceae\t|\t\t|\tscientific name\t|
239934\t|\tFaecalibacterium\t|\t\t|\tscientific name\t|
853\t|\tFaecalibacterium prausnitzii\t|\t\t|\tscientific name\t|
853\t|\tF. prausnitzii\t|\t\t|\tsynonym\t|
854\t|\tFaecalibacterium altus\t|\t\t|\tscientific name\t|
854\t|\tShared synonym\t|\t\t|\tsynonym\t|
855\t|\tFaecalibacterium minor\t|\t\t|\tscientific name\t|
855\t|\tShared synonym\t|\t\t|\tsynonym\t|
856\t|\tFaecalibacterium prausnitzii alpha\t|\t\t|\tscientific name\t|
857\t|\tFaecalibacterium prausnitzii beta\t|\t\t|\tscientific name\t|
"""


def build_fixture_db(directory: str | Path) -> Path:
    """Build the mini taxonomy SQLite into ``directory`` and return its path."""
    directory = Path(directory)
    archive = directory / "mini_taxdump.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in (("nodes.dmp", NODES_DMP), ("names.dmp", NAMES_DMP)):
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))
    db_path = directory / "mini_taxonomy.sqlite"
    build_taxonomy_database(archive, db_path)
    return db_path
