"""WeaverFactory dispatch and the WeaverProvider contract."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from braidworks.core import BaseWeaver, WeaverFactory, WeaverProvider

from helpers import make_weaver, simple_capability


class _Provider:
    def __init__(self, weaver_id: str) -> None:
        self.weaver_id = weaver_id
        self.seen_config: dict | None = None

    def build(self, config: Mapping[str, Any]) -> BaseWeaver:
        self.seen_config = dict(config)
        return make_weaver(simple_capability("c", {"a"}, {"b"}), weaver_id=self.weaver_id)


def test_provider_is_runtime_checkable():
    assert isinstance(_Provider("ncbi"), WeaverProvider)


def test_build_dispatches_to_registered_provider():
    factory = WeaverFactory()
    provider = _Provider("ncbi")
    factory.register(provider)
    weaver = factory.build("ncbi", {"db_path": "/tmp/x"})
    assert isinstance(weaver, BaseWeaver)
    assert provider.seen_config == {"db_path": "/tmp/x"}
    assert factory.providers() == ("ncbi",)


def test_unknown_weaver_id_raises():
    factory = WeaverFactory()
    with pytest.raises(KeyError):
        factory.build("missing", {})


def test_empty_weaver_id_rejected():
    factory = WeaverFactory()
    with pytest.raises(ValueError):
        factory.register(_Provider(""))


def test_duplicate_provider_rejected():
    factory = WeaverFactory()
    factory.register(_Provider("ncbi"))
    with pytest.raises(ValueError):
        factory.register(_Provider("ncbi"))
