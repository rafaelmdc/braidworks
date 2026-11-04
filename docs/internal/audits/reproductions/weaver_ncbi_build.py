"""Offline audit reproduction. All writes are confined to a temporary directory."""

import sqlite3
import tarfile
import tempfile
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path

from ncbi_weaver.fixture import build_fixture_db
from taxonomy_resolver.build import build_taxonomy_database
from taxonomy_tools.build_ncbi_taxonomy import run

with tempfile.TemporaryDirectory(prefix="ncbi-audit-") as directory:
    root = Path(directory)
    database = build_fixture_db(root)
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT COUNT(*) FROM taxa").fetchone()[0]
    bad_archive = root / "bad.tar.gz"
    with tarfile.open(bad_archive, "w:gz") as archive:
        for name, data in (
            ("nodes.dmp", b"bad\t|\t1\t|\tspecies\t|\n"),
            ("names.dmp", b"1\t|\troot\t|\t\t|\tscientific name\t|\n"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, BytesIO(data))
    try:
        build_taxonomy_database(bad_archive, database)
    except ValueError as error:
        print("Malformed direct rebuild:", type(error).__name__)
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT COUNT(*) FROM taxa").fetchone()[0]
    print("Existing taxa before/after:", before, after)
    arguments = Namespace(
        dump=str(root / "mini_taxdump.tar.gz"),
        db=str(root / "cli.sqlite"),
        download=False,
        report_json=None,
    )
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            run(arguments)
    except AttributeError as error:
        print("Valid build CLI:", type(error).__name__, str(error))
