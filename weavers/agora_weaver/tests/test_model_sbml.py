"""The `model` group: taxid -> per-reconstruction SBML path (offline + opt-in live).

Offline test seeds a fake model file in a cache dir and checks the backend returns its path
without any network. The live test downloads one real ~8 MB AGORA2 model from VMH.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from agora_weaver.backends.local import AgoraLocalBackend
from agora_weaver.setup import individual_sbml_url
from agora_weaver.weaver import AgoraWeaver

_TAXID = "592010"  # Abiotrophia defectiva -> Abiotrophia_defectiva_ATCC_49176
_RECON = "Abiotrophia_defectiva_ATCC_49176"
_SBML = "microbe.metabolism.sbml"


async def _resolve(weaver: AgoraWeaver, taxid: str):
    out = await weaver.execute_batch(
        "describe_metabolic_reconstruction",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", taxid)])],
        requested_outputs=frozenset({_SBML}),
        backend="local",
    )
    return out[0]


async def test_model_group_returns_cached_sbml_path(tmp_path: Path):
    # Seed the cache so no download is attempted (auto_download_models stays False).
    (tmp_path / f"{_RECON}.xml").write_text("<sbml>fake</sbml>")
    weaver = AgoraWeaver({"local": AgoraLocalBackend(sbml_cache_dir=tmp_path)})
    r = await _resolve(weaver, _TAXID)
    assert r.status is WeaveStatus.OK
    models = {s.type_id: s.value for s in r.strands}[_SBML]
    assert len(models) == 1
    assert models[0]["reconstruction_id"] == _RECON
    assert Path(models[0]["path"]).name == f"{_RECON}.xml"
    assert models[0]["source_url"] == individual_sbml_url(_RECON)


async def test_model_group_omitted_when_uncached_and_no_download(tmp_path: Path):
    # Empty cache + downloads disabled -> the model output is simply absent (core still fine).
    weaver = AgoraWeaver({"local": AgoraLocalBackend(sbml_cache_dir=tmp_path)})
    r = await _resolve(weaver, _TAXID)
    assert r.status is WeaveStatus.OK
    assert _SBML not in {s.type_id for s in r.strands}


@pytest.mark.skipif(
    not os.environ.get("BRAIDWORKS_RUN_LIVE"),
    reason="live E2E; set BRAIDWORKS_RUN_LIVE=1 (downloads a real ~8 MB AGORA2 model)",
)
async def test_live_downloads_real_model(tmp_path: Path):
    weaver = AgoraWeaver(
        {"local": AgoraLocalBackend(sbml_cache_dir=tmp_path, auto_download_models=True)}
    )
    r = await _resolve(weaver, _TAXID)
    assert r.status is WeaveStatus.OK
    models = {s.type_id: s.value for s in r.strands}[_SBML]
    path = Path(models[0]["path"])
    assert path.exists() and path.stat().st_size > 100_000  # a real SBML is MBs
    assert path.read_text(errors="ignore").lstrip().startswith("<?xml")
