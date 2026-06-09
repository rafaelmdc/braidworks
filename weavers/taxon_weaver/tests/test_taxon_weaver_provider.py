"""NCBIWeaverProvider conforms to the factory seam and builds via Layer 1."""

from __future__ import annotations

from braidworks.core import WeaverFactory, WeaverProvider

from taxon_weaver import NCBITaxonWeaver, NCBIWeaverProvider, vocab


def test_provider_conforms_to_contract():
    provider = NCBIWeaverProvider()
    assert provider.weaver_id == vocab.WEAVER_ID == "ncbi"
    assert isinstance(provider, WeaverProvider)


def test_factory_builds_ncbi_weaver_from_config(mini_db_path):
    factory = WeaverFactory()
    factory.register(NCBIWeaverProvider())
    weaver = factory.build("ncbi", {"db_path": mini_db_path})
    assert isinstance(weaver, NCBITaxonWeaver)
    assert weaver.MANIFEST.weaver_id == "ncbi"
    for cap in weaver.MANIFEST.capabilities:
        assert cap.backends == ("local",)
