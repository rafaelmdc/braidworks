"""Shared text/table input parsing for CLI and browser batches."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from itertools import chain
from typing import Any


def read_input_rows(
    lines: Iterable[str], *, input_type: str | None = None, delimiter: str | None = None
) -> list[dict[str, str]]:
    if input_type:
        return [
            {input_type: value}
            for line in lines
            if (value := line.strip()) and not value.startswith("#")
        ]
    iterator = iter(lines)
    header = next(iterator, "")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(header, delimiters=",\t").delimiter
        except csv.Error:
            delimiter = "\t"
    reader = csv.DictReader(chain([header], iterator), delimiter=delimiter)
    names = [(key or "").strip() for key in reader.fieldnames or []]
    if not names or any(not key for key in names):
        raise ValueError("input needs a header row of nonempty type-ids")
    if len(set(names)) != len(names):
        raise ValueError("input header contains duplicate type-ids")
    rows = []
    for raw in reader:
        if None in raw:
            raise ValueError(f"input row {reader.line_num} has more cells than its header")
        row = {key.strip(): value.strip() for key, value in raw.items() if value and value.strip()}
        if row:
            rows.append(row)
    return rows


def row_label(row: Mapping[str, Any]) -> str:
    """How a result row names an input row: its value, or ``type=value; …`` for several.

    Every interface labels table rows this way, so the same table gives the same row
    labels in Python, on the command line and in the browser.
    """
    if len(row) == 1:
        return str(next(iter(row.values())))
    return "; ".join(f"{type_id}={value}" for type_id, value in row.items())
