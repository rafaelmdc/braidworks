"""``Result``: what :func:`braidworks.get` returns — a table with honest outcomes.

One row per input (or per expanded child), labelled by the value the caller supplied.
The same row schema backs ``rows``, ``to_csv`` and ``to_pandas``, so every export of
one result agrees. The engine's full :class:`ExecutionResult` stays on ``raw``.
"""

from __future__ import annotations

import csv
import html
import io
import json
from collections.abc import Iterator
from os import PathLike
from typing import Any

from braidworks.core.braid import Braid
from braidworks.core.executor import ExecutionError, ExecutionResult, ReviewQueueItem
from braidworks.core.listing import Listing, describe_size
from braidworks.core.outcomes import execution_records
from braidworks.core.query import PreparedQuery
from braidworks.core.references import Reference, format_references
from braidworks.core.result import WeaveStatus
from braidworks.core.review import ReviewDecision
from braidworks.core.strand import entity_key

STATUSES = ("resolved", "unresolved", "review", "error")


def _cell(value: Any) -> str:
    """Flatten one value for a text table: lists join with ``; ``, mappings as JSON."""
    if isinstance(value, (list, tuple)):
        return "; ".join(_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else str(value)


def _shown(row: dict[str, Any], type_id: str, width: int | None = None) -> str:
    """A cell for people: the value, plus "(25 of 321)" / "(25+)" for a partial list."""
    value = row.get(type_id)
    text = _cell(value)
    if width is not None:
        text = text[:width]
    if isinstance(value, Listing) and not value.complete:
        text += f" ({describe_size(value)})"
    return text


# --------------------------------------------------------------------------- #
# the row schema, shared by Result and the command line
# --------------------------------------------------------------------------- #
def record_row(record: dict[str, Any], want: list[str]) -> dict[str, Any]:
    """One engine record as a row: input, row, parent?, status, wanted types, missing."""
    row: dict[str, Any] = {"input": record["entity"], "row": record["source_row"]}
    if "parent" in record:
        row["parent"] = record["parent"]
    row["status"] = record["status"]
    for type_id in want:
        row[type_id] = record["values"].get(type_id)
    row["missing"] = list(record["missing"])
    return row


def row_columns(rows: list[dict[str, Any]], want: list[str]) -> list[str]:
    """Row keys in display order: input, row, parent (if expanded), status, wanted, missing."""
    has_parent = any("parent" in row for row in rows)
    return ["input", "row", *(["parent"] if has_parent else []), "status", *want, "missing"]


def _export_columns(rows: list[dict[str, Any]], want: list[str]) -> list[str]:
    """``row_columns`` plus ``<type>.total`` after each sized list, for flat exports."""
    sized = {t for t in want for row in rows if isinstance(row.get(t), Listing)}
    out: list[str] = []
    for column in row_columns(rows, want):
        out.append(column)
        if column in sized:
            out.append(f"{column}.total")
    return out


def _export_row(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    flat = dict(row)
    for column in columns:
        if column.endswith(".total") and column not in row:
            value = row.get(column[: -len(".total")])
            flat[column] = value.total if isinstance(value, Listing) else None
    return flat


def rows_csv(rows: list[dict[str, Any]], want: list[str], *, sep: str = ",") -> str:
    """The rows as CSV (or TSV with ``sep="\\t"``), with a ``.total`` per sized list."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=sep, lineterminator="\n")
    columns = _export_columns(rows, want)
    writer.writerow(columns)
    for row in rows:
        flat = _export_row(row, columns)
        writer.writerow([_cell(flat.get(column)) for column in columns])
    return buffer.getvalue()


def rows_summary(rows: list[dict[str, Any]], inputs: int) -> str:
    """One line of counts: inputs, resolved, unresolved, need review, errors."""
    counts = {status: 0 for status in STATUSES}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return (
        f"{inputs} input{'s' if inputs != 1 else ''} · {counts['resolved']} resolved · "
        f"{counts['unresolved']} unresolved · {counts['review']} need review · "
        f"{counts['error']} error{'s' if counts['error'] != 1 else ''}"
    )


class ReviewItem:
    """One row paused for a human decision; record it, then call ``result.resume()``.

    ``ambiguous`` rows need :meth:`choose` (pick a numbered candidate) or
    :meth:`reject`; rows a source flagged for confirmation take :meth:`accept` or
    :meth:`reject`. Recording a decision does not run anything until ``resume()``.
    """

    def __init__(self, result: Result, item: ReviewQueueItem) -> None:
        self._result = result
        triggering = item.triggering_result
        self.input: str = item.strand_set.entity_id
        self.row: int | None = item.strand_set.source_row
        self.step: str = triggering.capability_id
        self.ambiguous: bool = triggering.status is WeaveStatus.AMBIGUOUS
        self.candidates: list[dict[str, Any]] = [
            {
                "index": index,
                "confidence": candidate.confidence,
                "values": {strand.type_id: strand.value for strand in candidate.strands},
            }
            for index, candidate in enumerate(triggering.candidates)
        ]
        self.warnings: list[str] = list(triggering.warnings)
        self._key = str(entity_key(item.strand_set))

    @property
    def decision(self) -> str | None:
        """The recorded decision (``"select 1"``, ``"accept"``, ``"reject"``), if any."""
        recorded = self._result._decisions.get(self._key)
        if recorded is None:
            return None
        if recorded.action == "select":
            return f"select {recorded.candidate_index}"
        return recorded.action

    def choose(self, index: int) -> None:
        """Pick candidate ``index`` for an ambiguous match."""
        if not self.candidates:
            raise ValueError(f"{self.input!r} has no candidates to choose from; use accept()")
        if type(index) is not int or not 0 <= index < len(self.candidates):
            raise ValueError(
                f"{self.input!r}: candidate index must be 0..{len(self.candidates) - 1}"
            )
        self._record(ReviewDecision(self._key, "select", index))

    def accept(self) -> None:
        """Confirm a result the source flagged for review."""
        if self.ambiguous:
            raise ValueError(f"{self.input!r} is ambiguous: choose(index) a candidate instead")
        self._record(ReviewDecision(self._key, "accept"))

    def reject(self) -> None:
        """Record no match for this input."""
        self._record(ReviewDecision(self._key, "reject"))

    def _record(self, decision: ReviewDecision) -> None:
        self._result._decisions[self._key] = decision

    def __repr__(self) -> str:
        where = f"row {self.row}" if self.row is not None else "row ?"
        kind = "ambiguous, choose one" if self.ambiguous else "flagged, accept or reject"
        lines = [f"{self.input} ({where}) at {self.step}: {kind}"]
        for candidate in self.candidates:
            values = ", ".join(f"{t}={_cell(v)[:40]!r}" for t, v in candidate["values"].items())
            lines.append(f"  [{candidate['index']}] {candidate['confidence']:.2f}  {values}")
        if self.decision:
            lines.append(f"  decision: {self.decision}")
        return "\n".join(lines)


class Result:
    """Rows, coverage and provenance for one query.

    Row keys: ``input`` (the supplied value), ``row`` (1-based input position, so
    duplicates stay distinct), ``parent`` (only for expanded children), ``status``
    (``resolved`` / ``unresolved`` / ``review`` / ``error``), one key per requested
    type (``None`` when absent) and ``missing`` (requested types this row lacks).
    A list value is a :class:`Listing`: ``len()`` is what came back, ``.total`` the
    true size and ``.complete`` whether it is all of it.
    """

    def __init__(
        self,
        raw: ExecutionResult,
        prepared: PreparedQuery,
        want: list[str],
        *,
        session: Any = None,
        state: Any = None,
    ) -> None:
        self.raw = raw
        self.want = list(want)
        self._prepared = prepared
        self._session = session  # the Session that ran this, for resume()
        self._state = state  # the engine state that resume() continues from
        self._decisions: dict[str, ReviewDecision] = {}
        self._records = execution_records(raw, self.want)
        # Input order; stable, so expanded children keep the engine's order within a row.
        self._records.sort(key=lambda record: record["source_row"] or 0)
        self.rows: list[dict[str, Any]] = [record_row(r, self.want) for r in self._records]

    # --- reading -------------------------------------------------------------------
    @property
    def columns(self) -> list[str]:
        """Row keys in display order: input, row, parent (if expanded), status, wanted types, missing."""
        return row_columns(self.rows, self.want)

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.rows)

    def __getitem__(self, input_value: str) -> list[dict[str, Any]]:
        """Every row for one input value (several when duplicated or expanded)."""
        return [row for row in self.rows if row["input"] == input_value]

    def column(self, type_id: str) -> dict[str, Any]:
        """``{input: value}`` for one requested type, skipping rows without it."""
        return {row["input"]: row[type_id] for row in self.rows if row.get(type_id) is not None}

    @property
    def missing(self) -> list[dict[str, Any]]:
        """Rows lacking at least one requested type, whatever their status."""
        return [row for row in self.rows if row["missing"] or row["status"] != "resolved"]

    @property
    def review(self) -> list[ReviewItem]:
        """Rows paused for a human decision, in input order (see :class:`ReviewItem`)."""
        if not hasattr(self, "_review_items"):
            items = sorted(self.raw.review_queue, key=lambda i: i.strand_set.source_row or 0)
            self._review_items = [ReviewItem(self, item) for item in items]
        return self._review_items

    def resume(self) -> Result:
        """Continue the run with the decisions recorded on :attr:`review` items.

        Returns a new :class:`Result`; rows that were already finished are kept as
        they were, and this result is left unchanged. Undecided rows stay paused.
        """
        session = self._resume_session()
        return session._runner().run(session._continue(self))

    async def async_resume(self) -> Result:
        """Awaitable :meth:`resume`."""
        session = self._resume_session()
        return await session._runner().arun(session._continue(self))

    def _resume_session(self):
        if not self._decisions:
            raise ValueError(
                "no review decisions recorded: call choose(), accept() or reject() on the "
                "items in result.review first"
            )
        if self._session is None or self._state is None:
            raise ValueError("this result was not produced by braidworks.get; cannot resume")
        return self._session

    @property
    def errors(self) -> list[ExecutionError]:
        """Source failures, one per failed lookup (a row may still hold other data)."""
        return list(self.raw.errors)

    @property
    def references(self) -> list[Reference]:
        """The sources this result drew on, with their citations."""
        return list(self.raw.references)

    @property
    def route(self) -> list[Braid]:
        """The plan(s) that ran: one per group of inputs sharing the same input types."""
        return [braid for braid, _ in self._prepared.plans]

    @property
    def parameters(self) -> dict[str, dict[str, Any]]:
        """Effective parameters per capability (defaults plus what the caller set)."""
        return {cid: dict(values) for cid, values in self._prepared.effective_params.items()}

    def cite(self) -> str:
        """The sources this result drew on, as a plain-text reference list."""
        return format_references(self.raw.references)

    def summary(self) -> str:
        """One line of counts: inputs, resolved, unresolved, need review, errors."""
        return rows_summary(self.rows, len(self._prepared.request.inputs))

    # --- exporting -----------------------------------------------------------------
    def to_csv(self, path: str | PathLike | None = None, *, sep: str = ",") -> str:
        """Write the rows as CSV (or TSV with ``sep="\\t"``); returns the text."""
        text = rows_csv(self.rows, self.want, sep=sep)
        if path is not None:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        return text

    def to_pandas(self, *, explode: str | None = None):
        """A pandas DataFrame of the rows; ``explode`` gives one row per list member."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "to_pandas() needs pandas: pip install 'braidworks-core[pandas]' "
                "(or use result.rows / result.to_csv())"
            ) from exc
        columns = _export_columns(self.rows, self.want)
        frame = pd.DataFrame([_export_row(row, columns) for row in self.rows], columns=columns)
        return frame.explode(explode, ignore_index=True) if explode else frame

    def to_json(self) -> dict[str, Any]:
        """Summary, rows, references and the full engine result, as JSON-ready data."""
        return {
            "summary": self.summary(),
            "want": list(self.want),
            "rows": self.rows,
            "references": [reference.to_json() for reference in self.raw.references],
            "result": self.raw.to_json(),
        }

    # --- display -------------------------------------------------------------------
    def __repr__(self) -> str:
        lines = [f"<braidworks.Result {self.summary()}>"]
        for row in self.rows[:10]:
            values = ", ".join(f"{t}={_shown(row, t, 40)!r}" for t in self.want)
            lines.append(f"  {row['input']} [{row['status']}] {values}")
        if len(self.rows) > 10:
            lines.append(f"  … {len(self.rows) - 10} more rows")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        columns = self.columns
        head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
        body = "".join(
            "<tr>"
            + "".join(
                "<td>"
                + html.escape(_shown(row, c, 200) if c in self.want else _cell(row.get(c))[:200])
                + "</td>"
                for c in columns
            )
            + "</tr>"
            for row in self.rows[:50]
        )
        more = f"<p>… {len(self.rows) - 50} more rows</p>" if len(self.rows) > 50 else ""
        return (
            f"<p><strong>{html.escape(self.summary())}</strong></p>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"
        )
