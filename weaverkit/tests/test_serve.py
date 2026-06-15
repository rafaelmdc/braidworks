"""Tests for ``weaverkit serve``.

The request logic (:func:`plan_response`) is exercised against a tiny in-test registry
with no web dependency. A single smoke test drives the FastAPI app via ``TestClient`` and
is skipped when the optional ``[serve]`` extra is not installed.
"""

from __future__ import annotations

import pytest
from braidworks.core import Provenance
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.weaver import BaseWeaver

from weaverkit.serve import plan_response, run_response


def _weaver(weaver_id, cap_id, consumes, produces, *, provenance=None):
    manifest = WeaverManifest(
        weaver_id=weaver_id,
        version="0.1.0",
        provenance=provenance,
        capabilities=(
            Capability(
                id=cap_id,
                consumes=frozenset(consumes),
                produces=frozenset(produces),
                output_groups=(OutputGroup(id="g", outputs=frozenset(produces)),),
                backends=("local",),
            ),
        ),
    )

    class _W(BaseWeaver):
        MANIFEST = manifest

        def backend_fingerprint(self, backend: str) -> str:
            return f"{weaver_id}-{backend}-v1"

        async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
            return WeaveResult(status=WeaveStatus.NO_MATCH, strand_set=StrandSet(strands=()))

    return _W()


@pytest.fixture
def registry():
    reg = BraidRegistry()
    reg.register(
        _weaver(
            "alpha", "a1", {"organism.name"}, {"ncbi.taxon.id"},
            provenance=Provenance(
                source_url="https://alpha.example", license="CC-BY-4.0",
                citation="https://doi.org/10.1/alpha", attribution="Alpha",
            ),
        )
    )
    reg.register(_weaver("beta", "b1", {"ncbi.taxon.id"}, {"protein.uniprot.accession"}))
    return reg


def test_plan_response_routes_and_emits_artifacts(registry):
    out = plan_response(registry, ["organism.name"], ["protein.uniprot.accession"])
    assert out["ok"] is True
    # two-step route projected
    assert out["path"]["step_count"] == 2
    arts = out["artifacts"]
    assert arts["cli_path"] == "braidworks path --from organism.name --to protein.uniprot.accession"
    assert "--have organism.name=<value>" in arts["cli_weave"]
    assert "--want protein.uniprot.accession" in arts["cli_weave"]
    assert "Braider(registry).plan" in arts["python"]
    assert arts["braid"] is out["path"]


def test_plan_response_collects_citations(registry):
    out = plan_response(registry, ["organism.name"], ["protein.uniprot.accession"])
    joined = " ".join(out["citations"])
    assert "Alpha" in joined  # alpha weaver is on the route and has provenance


def test_plan_response_no_path_is_human_error(registry):
    out = plan_response(registry, ["organism.name"], ["pdb.id"])  # nothing produces pdb.id
    assert out["ok"] is False
    assert out["error"]  # a "why no path" message, not an exception


def test_plan_response_requires_both_ends(registry):
    assert plan_response(registry, [], ["pdb.id"])["ok"] is False
    assert plan_response(registry, ["organism.name"], [])["ok"] is False


# --- run_response (executes a braid; deterministic, no network) --------------


def _producer(weaver_id, cap_id, consumes, produces, value):
    """A weaver whose execute deterministically emits ``produces -> value`` (no network)."""
    manifest = WeaverManifest(
        weaver_id=weaver_id,
        version="0.1.0",
        capabilities=(
            Capability(
                id=cap_id,
                consumes=frozenset(consumes),
                produces=frozenset(produces),
                output_groups=(OutputGroup(id="g", outputs=frozenset(produces)),),
                backends=("local",),
            ),
        ),
    )

    class _W(BaseWeaver):
        MANIFEST = manifest

        def backend_fingerprint(self, backend: str) -> str:
            return f"{weaver_id}-{backend}-v1"

        async def execute(self, capability_id, strand_set, *, requested_outputs, backend, params=None):
            return WeaveResult(
                capability_id=capability_id,
                weaver_version="0.1.0",
                backend_used=backend,
                computed_groups=frozenset({"g"}),
                status=WeaveStatus.OK,
                strands=tuple(Strand(t, value) for t in produces),
            )

    return _W()


@pytest.fixture
def run_registry():
    reg = BraidRegistry()
    reg.register(_producer("up", "resolve", {"protein.query"}, {"protein.uniprot.accession"}, "P04637"))
    return reg


def test_run_response_executes_and_returns_rows(run_registry):
    out = run_response(run_registry, {"protein.query": "TP53"}, ["protein.uniprot.accession"])
    assert out["ok"] is True
    assert out["summary"]["resolved"] == 1
    # the resolved row carries both the input and the produced accession
    (row,) = out["rows"]
    assert row["protein.uniprot.accession"] == "P04637"
    assert "protein.uniprot.accession" in out["columns"]
    # result carries per-step completion metadata (drives the front-end light-up)
    assert out["result"]["resolved"]


def test_run_response_no_path_is_error(run_registry):
    out = run_response(run_registry, {"protein.query": "TP53"}, ["pdb.id"])
    assert out["ok"] is False and out["error"]


def test_run_response_requires_have_and_want(run_registry):
    assert run_response(run_registry, {}, ["pdb.id"])["ok"] is False
    assert run_response(run_registry, {"protein.query": "TP53"}, [])["ok"] is False


# --- template split: interactive UI is served-only ---------------------------


def test_static_render_omits_serve_ui():
    """A static `view` export carries none of the builder/run/results JS."""
    from weaverkit.view import build_data, render_html

    html = render_html(build_data())  # interactive defaults to False
    for token in ('id="builder"', "buildResultHTML", "exportRows", "function setupBuilder",
                  'id="sheet"'):
        assert token not in html, token
    # ...but the render-side light-up hook stays in the base template.
    assert "function runStatusOf" in html


def test_interactive_render_injects_serve_ui():
    from weaverkit.view import build_data, render_html

    html = render_html(build_data(), interactive=True)
    for token in ('id="builder"', "buildResultHTML", "exportRows", "function setupBuilder",
                  'id="sheet"', "function showResults", "function showCite",  # modal pages
                  'id="b-search"', "function applySearch",       # graph search
                  'id="b-recipes"', "function saveRecipe"):      # save/load recipes
        assert token in html, token
    # no emoji in the served UI
    assert "\U0001f50d" not in html and "▶" not in html


# --- FastAPI smoke test (optional extra) -------------------------------------


def test_app_serves_page_and_plan_endpoint():
    testclient = pytest.importorskip(
        "fastapi.testclient", reason="weaverkit[serve] extra not installed"
    )
    from weaverkit.serve import create_app

    client = testclient.TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200 and "<html" in page.text.lower()

    resp = client.post("/api/plan", json={"from_types": ["protein.query"], "to_types": ["protein.query"]})
    assert resp.status_code == 200
    # protein.query -> protein.query is trivially satisfied (already available): ok, 0 steps.
    assert resp.json()["ok"] is True

    # The request body is a real Pydantic model — a malformed payload is a 422, not a crash.
    bad = client.post("/api/plan", json={"from_types": "not-a-list", "to_types": []})
    assert bad.status_code == 422


def test_run_stream_emits_sse_done_event():
    testclient = pytest.importorskip(
        "fastapi.testclient", reason="weaverkit[serve] extra not installed"
    )
    from weaverkit.serve import create_app

    client = testclient.TestClient(create_app())
    # A trivial 0-step run (the target is already available) — no network, ends immediately.
    body = client.get(
        "/api/run/stream",
        params={"have": '{"protein.query": "P04637"}', "want": "protein.query"},
    ).text
    assert '"event": "done"' in body and '"ok": true' in body
