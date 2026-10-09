"""Crosswalk and trees use one observed, checksum-verified official bundle."""

import gzip
import hashlib
import json
import sqlite3

import pytest
from braidworks.core import BackendConfigurationError
from gtdb_weaver import releases, setup, taxonomy
from gtdb_weaver.backends.local import GtdbLocalBackend

HEADER = "accession\tncbi_taxid\tgtdb_taxonomy\tgtdb_representative\n"


def fake_bundle():
    payloads = {}
    resources = {}
    for label, url in releases.release_sources("R232").items():
        content = (
            gzip.compress((HEADER + "GCF_1\t1\td__Bacteria;s__Species 1\tt\n").encode())
            if not label.endswith("tree")
            else b"(GCF_1:1,GCF_2:1);\n"
        )
        payloads[url] = content
        resources[label] = {"url": url, "md5": hashlib.md5(content).hexdigest()}
    return {
        "kind": "official-release",
        "release": "R232",
        "version_observed": "v232",
        "resources": resources,
    }, payloads


def test_release_manifest_is_checked_and_contains_all_four_resources(monkeypatch):
    bundle, _ = fake_bundle()
    manifest = "\n".join(
        f"{r['md5']}  ./{r['url'].rsplit('/', 1)[1]}" for r in bundle["resources"].values()
    )
    calls = []

    def read(url):
        calls.append(url)
        return "v232\n" if url.endswith("VERSION.txt") else manifest

    monkeypatch.setattr(releases, "_read_text", read)
    observed = releases.release_bundle("R232")
    assert observed["resources"] == bundle["resources"]
    assert all("/release232/232.0/" in url for url in calls)
    monkeypatch.setattr(releases, "_read_text", lambda _: "v226")
    with pytest.raises(ValueError, match="mismatch"):
        releases.release_bundle("R232")


def test_metadata_build_persists_both_original_hashes_and_tree_checksums(tmp_path, monkeypatch):
    bundle, payloads = fake_bundle()
    calls = []
    monkeypatch.setattr(setup, "release_bundle", lambda release: bundle)

    def download(url, target, **kwargs):
        calls.append(url)
        target.write_bytes(payloads[url])

    monkeypatch.setattr(setup, "_download", download)
    target = tmp_path / "crosswalk.sqlite"
    setup._build_crosswalk(
        target, bac120_url=setup.DEFAULT_BAC120_URL, ar53_url=setup.DEFAULT_AR53_URL, release=None
    )
    with sqlite3.connect(target) as con:
        observed = json.loads(
            con.execute("SELECT value FROM meta WHERE key='source_bundle'").fetchone()[0]
        )
    assert observed["release"] == "R232"
    for label in ("bac120", "ar53"):
        row = observed["resources"][label]
        assert row["sha256"] == hashlib.sha256(payloads[row["url"]]).hexdigest()
    assert all("latest" not in url for url in calls)
    assert not list(tmp_path.glob("gtdb-sources-*"))


def test_checksum_failure_preserves_existing_db_and_removes_downloads(tmp_path, monkeypatch):
    bundle, _ = fake_bundle()
    target = tmp_path / "crosswalk.sqlite"
    taxonomy.build_crosswalk_db([(1, "d__Bacteria;s__Old", True, "GCF_1")], target, release="R232")
    original = target.read_bytes()
    monkeypatch.setattr(setup, "release_bundle", lambda release: bundle)
    monkeypatch.setattr(
        setup, "_download", lambda url, dest, **kwargs: dest.write_bytes(b"corrupt")
    )
    monkeypatch.setattr(setup, "_MIN_FREE_BYTES", 0)
    with pytest.raises(ValueError, match="checksum"):
        setup.ensure_gtdb_db(target, auto=True, refresh=True)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob("gtdb-sources-*"))


def test_custom_inputs_do_not_inherit_a_live_release(tmp_path, monkeypatch):
    content = gzip.compress((HEADER + "GCF_1\t1\td__Bacteria;s__Custom\tt\n").encode())
    monkeypatch.setattr(setup, "_download", lambda url, dest, **kwargs: dest.write_bytes(content))
    monkeypatch.setattr(
        setup, "release_bundle", lambda _: pytest.fail("custom sources must not probe live release")
    )
    target = tmp_path / "source.sqlite"
    setup._build_crosswalk(
        target,
        bac120_url="https://custom/bacteria",
        ar53_url="https://custom/archaea",
        release="declared-by-caller",
    )
    assert taxonomy.db_release(target).startswith("custom-content-sha256:")
    with sqlite3.connect(target) as con:
        bundle = json.loads(
            con.execute("SELECT value FROM meta WHERE key='source_bundle'").fetchone()[0]
        )
    assert bundle["declared_release"] == "declared-by-caller"


async def test_wrong_release_tree_is_rejected_by_bound_backend(tmp_path):
    target = tmp_path / "crosswalk.sqlite"
    taxonomy.build_crosswalk_db(
        [(1, "d__Bacteria;s__Species 1", True, "GCF_1")], target, release="R232"
    )
    bundle, _ = fake_bundle()
    with sqlite3.connect(target) as con:
        con.execute("INSERT INTO meta VALUES ('source_bundle', ?)", (json.dumps(bundle),))
    tree = tmp_path / "wrong.tree"
    tree.write_text("(GCF_1:2,GCF_2:2);\n")
    backend = GtdbLocalBackend(target, tree_paths=[tree])
    with pytest.raises(BackendConfigurationError, match="checksum"):
        await backend.fetch(
            "describe_gtdb_tree_placement",
            [{"ncbi.taxon.id": 1}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )


def test_tree_acquisition_uses_the_same_persisted_bundle(tmp_path, monkeypatch):
    bundle, payloads = fake_bundle()
    calls = []
    monkeypatch.setattr(
        setup, "default_tree_paths", lambda release: [tmp_path / "bac.tree", tmp_path / "ar.tree"]
    )
    monkeypatch.setattr(setup, "_MIN_FREE_BYTES", 0)
    monkeypatch.setattr(
        setup, "release_bundle", lambda _: pytest.fail("do not resolve an independent release")
    )

    def download(url, target, **kwargs):
        calls.append(url)
        target.write_bytes(payloads[url])

    monkeypatch.setattr(setup, "_download", download)
    paths = setup.ensure_gtdb_trees(auto=True, bundle=bundle)
    assert len(paths) == 2
    assert calls == [bundle["resources"][label]["url"] for label in ("bac120_tree", "ar53_tree")]
