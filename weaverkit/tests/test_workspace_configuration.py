"""Public provider construction and transport lifecycle across installed weavers."""

import httpx
import pytest
from braidworks.core import BackendConfigurationError, WeaverFactory

SOURCES = [
    "example",
    "uniprot",
    "pdbe",
    "alphafold",
    "quickgo",
    "reactome",
    "ncbi",
    "gtdb",
    "bacdive",
    "agora",
    "faprotax",
    "disbiome",
    "gmrepo",
    "mondo",
    "wikidata",
    "wikipedia",
]
API_ONLY = ["uniprot", "pdbe", "alphafold", "quickgo", "reactome", "bacdive", "wikidata"]


@pytest.mark.parametrize("source", SOURCES)
def test_provider_rejects_unknown_options_and_accepts_empty_config(source):
    package = pytest.importorskip(source + "_weaver")
    factory = WeaverFactory()
    if source == "ncbi":
        from ncbi_weaver.provider import NCBIWeaverProvider

        factory.register(NCBIWeaverProvider())
    else:
        package.register(factory)
    factory.build(source, {})
    with pytest.raises(BackendConfigurationError, match="misspelled"):
        factory.build(source, {"misspelled": "secret"})


@pytest.mark.parametrize("source", API_ONLY)
async def test_provider_forwards_client_and_source_identity_and_borrows_lifetime(source):
    package = pytest.importorskip(source + "_weaver")
    factory = WeaverFactory()
    package.register(factory)
    async with httpx.AsyncClient(
        base_url="https://custom.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    ) as client:
        weaver = factory.build(source, {"client": client})
        backend = weaver._backends["api"]
        assert backend._client is client
        assert weaver.backend_fingerprint("api") != factory.build(source, {}).backend_fingerprint(
            "api"
        )
        async with weaver:
            backend._http()
            assert backend._client is client
        assert not client.is_closed
        assert (await client.get("/probe")).status_code == 200
        with pytest.raises(BackendConfigurationError, match="closed"):
            backend._http()


@pytest.mark.parametrize("source", API_ONLY)
async def test_weaver_context_closes_lazy_owned_api_client(source):
    package = pytest.importorskip(source + "_weaver")
    build = getattr(package, "build_" + source + "_weaver")
    async with build() as weaver:
        backend = weaver._backends["api"]
        assert backend._client is None
        backend._http()
        client = backend._client
        assert not client.is_closed
    assert client.is_closed
    await weaver.aclose()


def test_ncbi_api_settings_alone_are_forwarded_and_do_not_expose_key():
    module = pytest.importorskip("ncbi_weaver.factory")
    weaver = module.build_ncbi_weaver(
        api_key="secret", allow_fuzzy=False, api_max_report_pages=7, api_max_concurrency=2
    )
    assert set(weaver._backends) == {"api"}
    backend = weaver._backends["api"]
    assert backend._api_key == "secret" and not backend._allow_fuzzy
    assert backend._max_report_pages == 7 and backend._max_concurrency == 2
    assert "secret" not in backend.fingerprint()
    assert backend.fingerprint() != module.build_ncbi_weaver().backend_fingerprint("api")


def test_gtdb_tree_options_select_local_instead_of_being_dropped(monkeypatch, tmp_path):
    module = pytest.importorskip("gtdb_weaver.factory")
    selected = []
    path = tmp_path / "source.sqlite"
    monkeypatch.setattr(module, "_ensure_local_db", lambda *args, **kwargs: path)
    monkeypatch.setattr(
        module, "_resolve_tree_paths", lambda *args, **kwargs: selected.append(kwargs) or []
    )
    weaver = module.build_gtdb_weaver(enable_tree_placement=True)
    assert set(weaver._backends) == {"local"}
    assert selected[0]["enable_tree_placement"]
    with pytest.raises(BackendConfigurationError, match="explicit"):
        module.build_gtdb_weaver_configured(enable_api=False)


def test_agora_configured_wrapper_does_not_imply_download_consent(monkeypatch):
    module = pytest.importorskip("agora_weaver.factory")
    seen = []
    monkeypatch.setattr(module, "build_agora_weaver", lambda **config: seen.append(config))
    module.build_agora_weaver_configured(auto_setup=False)
    module.build_agora_weaver_configured()
    assert seen == [{"auto_setup": False}, {}]
