"""``Session`` and the module-level ``get`` / ``path`` / ``sources`` functions.

A session discovers and builds the installed sources once, runs every query on its own
private event loop, and closes the sources' network clients when it closes. Running on a
private loop is what lets the synchronous :meth:`Session.get` work inside Jupyter (whose
loop is already running) and keeps each source's HTTP client on the loop that created it.

The module-level functions use one shared default session, created on first use and
closed at interpreter exit — the ``requests.get`` / ``requests.Session`` pattern.
"""

from __future__ import annotations

import asyncio
import atexit
import math
import threading
from collections.abc import Coroutine, Iterable, Mapping
from os import PathLike
from pathlib import Path
from typing import Any, Self, TypeVar

from braidworks._result import Result
from braidworks.core.braid import BackendPolicy, Braid
from braidworks.core.catalog import FieldMatches, field_catalog, rank_fields
from braidworks.core.diagnose import explain_no_route, installed_types, source_status
from braidworks.core.discovery import build_registry_from_entry_points
from braidworks.core.exceptions import NoPathError
from braidworks.core.executor import ReviewPolicy
from braidworks.core.inputs import read_input_rows
from braidworks.core.persistence_options import QueryPersistence
from braidworks.core.planner import Braider
from braidworks.core.query import QueryOptions, QueryRequest, normalize_expansion, prepare_query
from braidworks.core.query_state import continue_query, start_query
from braidworks.core.registry import BraidRegistry
from braidworks.core.review import apply_review_decisions
from braidworks.core.strand import Strand, StrandSet

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
def _is_blank(value: Any) -> bool:
    return (
        value is None
        or (isinstance(value, float) and math.isnan(value))
        or (isinstance(value, str) and not value.strip())
    )


def _clean(row: Mapping[str, Any]) -> dict[str, str]:
    return {str(k).strip(): str(v).strip() for k, v in row.items() if not _is_blank(v)}


def _input_rows(ids: Any, have: str | None) -> tuple[list[dict[str, str]], bool]:
    """Normalize ``ids`` to typed rows; returns ``(rows, typed)``.

    ``typed`` is True when the rows named their own types (mapping, DataFrame, file
    with a header) and False when they are plain values typed by ``have``.
    """
    if isinstance(ids, PathLike):
        with open(ids, encoding="utf-8", newline="") as handle:
            return read_input_rows(handle, input_type=have), have is None
    if isinstance(ids, (str, int)):
        ids = [ids]
    if hasattr(ids, "to_dict") and hasattr(ids, "columns"):  # a pandas DataFrame
        return [_clean(row) for row in ids.to_dict(orient="records")], True
    if isinstance(ids, Mapping):
        values = list(ids.values())
        if all(isinstance(v, (str, int, float)) or v is None for v in values):
            return [_clean(ids)], True
        columns = {key: list(column) for key, column in ids.items()}
        lengths = {len(column) for column in columns.values()}
        if len(lengths) > 1:
            raise ValueError("every column in ids={type: [values]} needs the same length")
        count = lengths.pop() if lengths else 0
        return [_clean({k: c[i] for k, c in columns.items()}) for i in range(count)], True
    items = list(ids)
    if items and all(isinstance(item, Mapping) for item in items):
        return [_clean(item) for item in items], True
    if have is None:
        return [], False
    return [{have: str(item).strip()} for item in items if not _is_blank(item)], False


def _label(row: Mapping[str, str]) -> str:
    if len(row) == 1:
        return next(iter(row.values()))
    return "; ".join(f"{type_id}={value}" for type_id, value in row.items())


def _strand_sets(rows: list[dict[str, str]]) -> list[StrandSet]:
    sets = []
    for index, row in enumerate(rows, start=1):
        if not row:
            continue
        ss = StrandSet.from_strands(_label(row), [Strand(t, v) for t, v in row.items()])
        ss.source_row = index
        sets.append(ss)
    return sets


def _parameter_items(
    params: Mapping[str, Any] | None, parameters: Mapping[str, Any]
) -> tuple[tuple[str | None, str, Any], ...]:
    items: list[tuple[str | None, str, Any]] = []
    for name, value in (params or {}).items():
        if isinstance(value, Mapping):
            items.extend((name, key, inner) for key, inner in value.items())
        else:
            items.append((None, name, value))
    items.extend((None, name, value) for name, value in parameters.items())
    return tuple(items)


def _as_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(" ", ",").split(",") if part.strip()]
    return [str(part) for part in value]


# --------------------------------------------------------------------------- #
# session
# --------------------------------------------------------------------------- #
class _LoopThread:
    """A private event loop on a daemon thread; all session I/O runs here."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self.loop.run_forever, name="braidworks-session", daemon=True
        )
        self._thread.start()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    async def arun(self, coro: Coroutine[Any, Any, T]) -> T:
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self.loop))

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join()
        self.loop.close()


class Session:
    """Installed sources plus settings, reused across queries.

    Args:
        sources: Restrict to these source ids (list or ``"uniprot,pdbe"``); default all.
        backend: ``"local_first"`` (default), ``"api_first"``, ``"local_only"`` or
            ``"api_only"``.
        cache: Path of an opt-in SQLite lookup cache, reused across sessions.
        registry: A prebuilt registry (advanced; skips discovery). The session closes it.
    """

    def __init__(
        self,
        sources: str | Iterable[str] | None = None,
        *,
        backend: str = "local_first",
        cache: str | PathLike | None = None,
        registry: BraidRegistry | None = None,
    ) -> None:
        self._only = frozenset(_as_list(sources)) or None
        self._backend = BackendPolicy(backend)
        self._persistence = QueryPersistence(
            cache_db=str(Path(cache).expanduser()) if cache is not None else None
        )
        self._registry = registry
        self._loop: _LoopThread | None = None
        self._closed = False

    # --- lifecycle -----------------------------------------------------------------
    @property
    def registry(self) -> BraidRegistry:
        if self._closed:
            raise RuntimeError("this braidworks Session is closed")
        if self._registry is None:
            self._registry = build_registry_from_entry_points(only=self._only)
        return self._registry

    def _runner(self) -> _LoopThread:
        if self._closed:
            raise RuntimeError("this braidworks Session is closed")
        if self._loop is None:
            self._loop = _LoopThread()
        return self._loop

    async def _close_sources(self) -> None:
        if self._registry is None:
            return
        for manifest in self._registry.manifests():
            await self._registry.get_weaver(manifest.weaver_id).aclose()

    def close(self) -> None:
        """Close every source's network client; the session cannot be used afterwards."""
        if self._closed:
            return
        if self._registry is not None:
            self._runner().run(self._close_sources())
        if self._loop is not None:
            self._loop.stop()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if not self._closed:
            if self._registry is not None:
                await self._runner().arun(self._close_sources())
            if self._loop is not None:
                self._loop.stop()
            self._closed = True

    # --- queries -------------------------------------------------------------------
    def _prepare(
        self,
        ids: Any,
        *,
        have: str | None,
        want: str | Iterable[str] | None,
        expand: str | None,
        for_each: str | Iterable[str] | None,
        review: str,
        min_confidence: float,
        max_expansion: int,
        params: Mapping[str, Any] | None,
        parameters: Mapping[str, Any],
    ):
        want_types = _as_list(want)
        traversals = _as_list(for_each)
        if not want_types and not traversals:
            raise ValueError(
                "get() needs want= naming the type(s) to retrieve (see braidworks keys)"
            )
        rows, typed = _input_rows(ids, have)
        if typed and have is not None and not isinstance(ids, PathLike):
            raise ValueError(
                "have= types a plain list of IDs; these rows already name their types "
                "(drop have=, or pass a list of values)"
            )
        if not typed and have is None:
            consumed, produced = installed_types(self.registry)
            # Types nothing produces are where queries start (names, free-text queries).
            starts = sorted(consumed - produced) + sorted(consumed & produced)
            examples = ", ".join(f'"{t}"' for t in starts[:8])
            example = f', e.g. have="{starts[0]}"' if starts else ""
            raise ValueError(
                f"get() needs have= to say what these IDs are{example}. "
                f"Inputs the installed sources accept include: {examples}. "
                "Run `braidworks keys` for the full list."
            )
        sets = _strand_sets(rows)
        if not sets:
            raise ValueError("no input values to look up")
        request = QueryRequest(
            tuple(sets),
            frozenset(want_types),
            traversals=tuple(traversals),
            options=QueryOptions(
                self._backend,
                normalize_expansion(expand, traversal=bool(traversals)),
                ReviewPolicy(review),
                min_confidence,
                max_expansion,
            ),
            parameter_items=_parameter_items(params, parameters),
        )
        registry = self.registry
        try:
            prepared = prepare_query(registry, request)
        except NoPathError as exc:
            have_types = sorted({t for ss in sets for t in ss.available_types()})
            lines = explain_no_route(registry, have_types, want_types)
            raise NoPathError("\n".join(lines)) from exc
        return prepared, want_types

    async def _execute(self, prepared, want_types: list[str]) -> Result:
        # Keep the engine state on the Result so paused rows can be resumed later.
        state = start_query(prepared)
        raw = await continue_query(self.registry, state, cache=self._persistence.cache())
        return Result(
            raw,
            prepared,
            want_types,
            session=self,
            state=state,
            totals=self._route_totals(prepared),
        )

    def _route_totals(self, prepared) -> dict[str, str]:
        """Declared ``{list_type: count_type}`` across every capability on the route."""
        totals: dict[str, str] = {}
        for weaver_id, capability_id in prepared.capability_ids:
            totals.update(self.registry.get_capability(weaver_id, capability_id).totals)
        return totals

    async def _continue(self, result: Result) -> Result:
        state = apply_review_decisions(
            self.registry, result._state, tuple(result._decisions.values())
        )
        raw = await continue_query(self.registry, state, cache=self._persistence.cache())
        return Result(
            raw,
            result._prepared,
            result.want,
            session=self,
            state=state,
            totals=self._route_totals(result._prepared),
        )

    def get(
        self,
        ids: Any,
        *,
        have: str | None = None,
        want: str | Iterable[str] | None = None,
        expand: str | None = None,
        for_each: str | Iterable[str] | None = None,
        review: str = "halt",
        min_confidence: float = 0.0,
        max_expansion: int = 10_000,
        params: Mapping[str, Any] | None = None,
        **parameters: Any,
    ) -> Result:
        """Look up ``want`` for each of ``ids``; see :func:`braidworks.get`."""
        prepared, want_types = self._prepare(
            ids,
            have=have,
            want=want,
            expand=expand,
            for_each=for_each,
            review=review,
            min_confidence=min_confidence,
            max_expansion=max_expansion,
            params=params,
            parameters=parameters,
        )
        return self._runner().run(self._execute(prepared, want_types))

    async def async_get(
        self,
        ids: Any,
        *,
        have: str | None = None,
        want: str | Iterable[str] | None = None,
        expand: str | None = None,
        for_each: str | Iterable[str] | None = None,
        review: str = "halt",
        min_confidence: float = 0.0,
        max_expansion: int = 10_000,
        params: Mapping[str, Any] | None = None,
        **parameters: Any,
    ) -> Result:
        """Awaitable :meth:`get`, for code already running in an event loop."""
        prepared, want_types = self._prepare(
            ids,
            have=have,
            want=want,
            expand=expand,
            for_each=for_each,
            review=review,
            min_confidence=min_confidence,
            max_expansion=max_expansion,
            params=params,
            parameters=parameters,
        )
        return await self._runner().arun(self._execute(prepared, want_types))

    def path(self, have: str | Iterable[str], want: str | Iterable[str]) -> Braid:
        """The route from ``have`` to ``want``, without fetching anything."""
        have_types, want_types = _as_list(have), _as_list(want)
        try:
            return Braider(self.registry).plan(
                available_types=frozenset(have_types),
                target_types=frozenset(want_types),
                backend_policy=self._backend,
            )
        except NoPathError as exc:
            lines = explain_no_route(self.registry, have_types, want_types)
            raise NoPathError("\n".join(lines)) from exc

    def sources(self) -> list[dict[str, Any]]:
        """Each installed source with its version and readiness (as `braidworks doctor`)."""
        return source_status(self.registry)

    def find(self, text: str, *, limit: int = 10) -> FieldMatches:
        """Fields whose name or description matches ``text``, best first.

        ``s.find("pdb structures")`` lists ``structure.pdb.ids`` with its meaning, the
        source that provides it and what it starts from. Use the type id as ``want=``
        (or ``have=`` when the field is an input).
        """
        return FieldMatches(rank_fields(text, field_catalog(self.registry), limit=limit))


# --------------------------------------------------------------------------- #
# module-level functions over a shared default session
# --------------------------------------------------------------------------- #
_default: Session | None = None
_default_lock = threading.Lock()


def _default_session() -> Session:
    global _default
    with _default_lock:
        if _default is None or _default._closed:
            _default = Session()
            atexit.register(_default.close)
        return _default


def get(
    ids: Any,
    *,
    have: str | None = None,
    want: str | Iterable[str] | None = None,
    sources: str | Iterable[str] | None = None,
    expand: str | None = None,
    for_each: str | Iterable[str] | None = None,
    review: str = "halt",
    min_confidence: float = 0.0,
    max_expansion: int = 10_000,
    params: Mapping[str, Any] | None = None,
    **parameters: Any,
) -> Result:
    """Look up ``want`` for each of ``ids`` across the installed sources.

    Example::

        import braidworks as bw

        result = bw.get(["P04637", "TP53"], have="protein.query",
                        want=["protein.name", "structure.pdb.ids"], organism="9606")
        result.to_pandas()

    Args:
        ids: One value, a list of values (typed by ``have``), a list of
            ``{type: value}`` rows, a ``{type: [values]}`` mapping, a DataFrame with
            type-named columns, or a ``pathlib.Path`` to a CSV/TSV (or, with ``have``,
            one value per line).
        have: What plain values are, e.g. ``"protein.query"``. Required for plain values.
        want: The type(s) to retrieve, as a list or ``"a,b"``.
        sources: Restrict to these source ids. Uses a one-off session when set.
        expand: ``"none"`` (default), ``"all"`` or ``"top:5"`` to follow set outputs.
        for_each: Follow a relationship (e.g. ``"orthologs"``) before resolving ``want``.
        review: ``"halt"`` (default) pauses ambiguous matches for review;
            ``"allow_continue"`` keeps the source's pick and flags it; ``"raise"``.
        min_confidence: Minimum match confidence (0–1); lower results pause.
        max_expansion: Run-wide limit on expanded rows.
        params: Scoped parameters, ``{capability: {name: value}}``, or names that clash
            with this function's own arguments.
        **parameters: Capability parameters by name, e.g. ``organism="9606"``.

    Returns:
        A :class:`Result`. Unknown types or parameters raise before any source call.
    """
    options = dict(
        have=have,
        want=want,
        expand=expand,
        for_each=for_each,
        review=review,
        min_confidence=min_confidence,
        max_expansion=max_expansion,
        params=params,
        **parameters,
    )
    if sources is not None:
        with Session(sources) as session:
            return session.get(ids, **options)
    return _default_session().get(ids, **options)


async def async_get(
    ids: Any,
    *,
    have: str | None = None,
    want: str | Iterable[str] | None = None,
    sources: str | Iterable[str] | None = None,
    expand: str | None = None,
    for_each: str | Iterable[str] | None = None,
    review: str = "halt",
    min_confidence: float = 0.0,
    max_expansion: int = 10_000,
    params: Mapping[str, Any] | None = None,
    **parameters: Any,
) -> Result:
    """Awaitable :func:`get`."""
    options = dict(
        have=have,
        want=want,
        expand=expand,
        for_each=for_each,
        review=review,
        min_confidence=min_confidence,
        max_expansion=max_expansion,
        params=params,
        **parameters,
    )
    if sources is not None:
        async with Session(sources) as session:
            return await session.async_get(ids, **options)
    return await _default_session().async_get(ids, **options)


def path(have: str | Iterable[str], want: str | Iterable[str]) -> Braid:
    """The route from ``have`` to ``want`` across the installed sources, without fetching."""
    return _default_session().path(have, want)


def sources() -> list[dict[str, Any]]:
    """Each installed source with its version and readiness."""
    return _default_session().sources()


def find(text: str, *, limit: int = 10) -> FieldMatches:
    """Fields whose name or description matches ``text``, best first.

    Example::

        bw.find("pdb structures")   # -> structure.pdb.ids, with its meaning and source
    """
    return _default_session().find(text, limit=limit)
