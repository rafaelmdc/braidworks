"""Offline demo: canned queries over the sources' bundled fixtures, no network.

Every installed source whose entry point ``pkg.factory:build_x`` has a sibling
``build_x_fixture`` contributes that fixture-backed weaver (canned API responses or a
tiny bundled dataset). Sources without one are left out of the demo. The answers are
sample data, kept small and stable for tests; they are not current upstream records.

    braidworks demo                 # run every demo query, print the tables
    braidworks demo --serve         # the browser on the same sample data
    bw.demo("proteins")             # one demo query as a Result
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import io
import logging
from dataclasses import dataclass, field

from braidworks.core import BraidRegistry
from braidworks.core.exceptions import NoPathError, NoPlanError

_log = logging.getLogger(__name__)

NOTICE = (
    "Demo mode: answers come from small samples bundled with each source, not the live "
    "databases. Nothing is fetched from the network."
)


@dataclass(frozen=True)
class Demo:
    """One canned query the bundled fixtures answer end to end."""

    name: str
    title: str
    ids: tuple[str, ...]
    have: str
    want: tuple[str, ...]
    # {capability_id: {name: value}} as the browser sends them; flattened for bw.get.
    params: dict[str, dict[str, str]] = field(default_factory=dict)
    point: str = ""

    def get_kwargs(self) -> dict:
        flat = {name: value for values in self.params.values() for name, value in values.items()}
        return {"have": self.have, "want": list(self.want), **flat}

    def example(self) -> dict:
        """The browser's "Start from an example" card for this query."""
        return {
            "name": self.title,
            "have": self.have,
            "ids": "\n".join(self.ids),
            "want": list(self.want),
            "params": {cap: dict(values) for cap, values in self.params.items()},
        }


DEMOS: tuple[Demo, ...] = (
    Demo(
        name="proteins",
        title="Structures, pathways and partners of a gene",
        ids=("TP53", "NOTAGENE"),
        have="protein.query",
        want=(
            "protein.name",
            "structure.pdb.ids",
            "pathway.reactome.names",
            "go.biological_process",
            "protein.interaction.partners",
            "structure.alphafold.mean_plddt",
        ),
        params={"resolve_protein": {"organism": "9606"}},
        point="Six sources from one gene symbol; NOTAGENE shows how a miss is reported.",
    ),
    Demo(
        name="microbe",
        title="Traits and taxonomy of a microbe",
        ids=("Escherichia coli",),
        have="organism.scientific_name",
        want=("microbe.trait.gram_stain", "microbe.trait.cell_shape", "gtdb.taxon.id"),
        point="BacDive phenotypes and the GTDB species from one name.",
    ),
    Demo(
        name="taxon",
        title="Wikipedia attention for a species",
        ids=("Ursus arctos",),
        have="organism.scientific_name",
        want=("wikidata.qid", "wikipedia.title", "wikipedia.pageviews"),
        point="A two-step route: Wikidata finds the article, Wikipedia counts its views.",
    ),
)


def demo_registry() -> BraidRegistry:
    """A registry of every installed source that ships a fixture builder."""
    registry = BraidRegistry()
    for entry in sorted(
        importlib.metadata.entry_points(group="braidworks.weavers"), key=lambda e: e.name
    ):
        module_name, _, builder = entry.value.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:  # a broken source just stays out of the demo
            _log.warning("demo: skipping %s: %s", entry.name, exc)
            continue
        build_fixture = getattr(module, f"{builder}_fixture", None)
        if build_fixture is None:
            continue
        try:
            # Fixtures that build a tiny local database report it on stderr; that
            # is noise in a demo.
            with contextlib.redirect_stderr(io.StringIO()):
                registry.register(build_fixture())
        except Exception as exc:  # noqa: BLE001 - any fixture failure leaves the source out
            _log.warning("demo: skipping %s: %s", entry.name, exc)
    return registry


def runnable(registry: BraidRegistry) -> list[Demo]:
    """The demo queries the sources in ``registry`` can route (nothing is fetched)."""
    from braidworks import Session

    session = Session(registry=registry)
    out = []
    for demo in DEMOS:
        try:
            session.path(demo.have, demo.want)
        except (NoPathError, NoPlanError):  # a source it needs is not in the demo
            continue
        out.append(demo)
    return out


def run(name: str | None = None) -> list:
    """Run one demo (or every runnable one) offline; ``[(Demo, Result)]``."""
    from braidworks import Session

    with Session(registry=demo_registry()) as session:
        demos = [find_demo(name)] if name else runnable(session.registry)
        return [(demo, session.get(list(demo.ids), **demo.get_kwargs())) for demo in demos]


def find_demo(name: str) -> Demo:
    for demo in DEMOS:
        if demo.name == name:
            return demo
    names = ", ".join(demo.name for demo in DEMOS)
    raise ValueError(f"no demo named {name!r}; choose one of: {names}")
