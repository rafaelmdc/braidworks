import sqlite3
import tempfile
from pathlib import Path

from mondo_weaver.backends.local import _ANCESTORS_SQL, MondoLocalBackend
from mondo_weaver.setup import _Term, db_is_valid, write_db

with tempfile.TemporaryDirectory() as directory:
    for reverse in [False, True]:
        terms = []
        for tid in ["MONDO:0000002", "MONDO:0000001"]:
            t = _Term(tid)
            t.name = "same name"
            t.xrefs = [("MESH", "D1", False)]
            terms.append(t)
        if reverse:
            terms.reverse()
        db = Path(directory) / f"{reverse}.sqlite"
        write_db(db, data_version=None, terms=terms)
        backend = MondoLocalBackend(db)
        con = sqlite3.connect(db)
        print(
            "reverse",
            reverse,
            "name",
            backend._resolve_mondo(con, "NAME", "same name"),
            "xref",
            backend._resolve_mondo(con, "MESH", "D1"),
            "valid",
            db_is_valid(db),
        )
        con.execute("INSERT INTO isa VALUES (?,?)", ("MONDO:0000001", "MONDO:0000002"))
        con.execute("INSERT INTO isa VALUES (?,?)", ("MONDO:0000002", "MONDO:0000001"))
        con.commit()
        con.set_progress_handler(lambda: 1, 10000)
        try:
            con.execute(_ANCESTORS_SQL, ("MONDO:0000001",)).fetchall()
        except sqlite3.OperationalError as error:
            print("Cycle", str(error), "(bounded via progress guard)")
        con.close()
