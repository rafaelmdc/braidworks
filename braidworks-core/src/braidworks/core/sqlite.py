"""Small SQLite ownership helpers; schemas and SQL belong to their source packages."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def readonly_uri(path: str | Path) -> str:
    """Escape a filesystem path and open only an existing database."""
    return Path(path).absolute().as_uri() + "?mode=ro"


@contextmanager
def connection_scope(
    database: str | Path | sqlite3.Connection, *, readonly: bool = False
) -> Iterator[sqlite3.Connection]:
    """Close owned handles on every exit; leave borrowed handles untouched.

    This scope does not commit. Use transaction() for explicitly owned writes.
    Borrowed handles must already have the desired read/write configuration.
    """
    if isinstance(database, sqlite3.Connection):
        if readonly:
            raise ValueError("readonly requires a path, not a borrowed connection")
        yield database
        return
    connection = sqlite3.connect(readonly_uri(database) if readonly else database, uri=readonly)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Own one transaction; reject nesting into a caller's transaction."""
    if connection.in_transaction:
        raise ValueError("Cannot own an already active SQLite transaction")
    connection.execute("BEGIN")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
