"""Spec loader + validator tests.

The validator is a guardrail, so the tests are mostly *negative*: each one breaks
one rule and asserts the matching problem is reported. A broken spec must never
slip through as valid.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from weaverkit.spec import (
    CapabilitySpec,
    GoldenSpec,
    GroupSpec,
    SpecError,
    WeaverSpec,
    load_spec,
    validate_spec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def _valid_dict() -> dict:
    """A valid spec as a plain dict, so tests can mutate one rule at a time."""
    return {
        "weaver": {
            "db_name": "madin",
            "weaver_id": "madin",
            "title": "Madin traits",
            "version": "0.1.0",
            "license": "CC-BY-4.0",
            "source_url": "https://example.org/madin",
            "fingerprint_source": "release-tag",
            "source_sample": "tax_id,gram\n562,negative\n",
            "backends": ["local"],
        },
        "capability": [
            {
                "id": "resolve_traits",
                "consumes": ["ncbi.taxon.id"],
                "backends": ["local"],
                "group": [
                    {"id": "traits.core", "outputs": ["microbe.trait.gram_stain"]},
                    {"id": "traits.growth", "outputs": ["microbe.trait.optimum_temp"]},
                ],
            }
        ],
        "golden": [
            {
                "capability": "resolve_traits",
                "input": {"ncbi.taxon.id": "562"},
                "expect": {"microbe.trait.gram_stain": "negative"},
            }
        ],
    }


# --- loading -----------------------------------------------------------------


def test_load_valid_fixture():
    spec = load_spec(FIXTURE)
    assert spec.db_name == "madin"
    assert spec.package == "madin_weaver"
    assert spec.resolved_weaver_id == "madin"
    assert validate_spec(spec) == []


def test_load_missing_file_raises_specerror():
    with pytest.raises(SpecError):
        load_spec(FIXTURE.parent / "does-not-exist.toml")


def test_load_bad_toml_raises_specerror(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not toml")
    with pytest.raises(SpecError):
        load_spec(bad)


def test_missing_required_field_raises_specerror():
    data = _valid_dict()
    del data["weaver"]["license"]
    with pytest.raises(SpecError):
        WeaverSpec.from_dict(data)


# --- derived properties ------------------------------------------------------


def test_capability_produces_is_union_of_groups():
    cap = CapabilitySpec(
        id="c",
        consumes=("ncbi.taxon.id",),
        groups=(
            GroupSpec("g1", ("a", "b")),
            GroupSpec("g2", ("c",)),
        ),
    )
    assert cap.produces == ("a", "b", "c")


def test_resolved_weaver_id_falls_back_to_db_name():
    data = _valid_dict()
    del data["weaver"]["weaver_id"]
    spec = WeaverSpec.from_dict(data)
    assert spec.resolved_weaver_id == "madin"


# --- validation: the happy path ---------------------------------------------


def test_valid_dict_passes():
    assert validate_spec(WeaverSpec.from_dict(_valid_dict())) == []


# --- validation: negative cases ---------------------------------------------


def test_unregistered_consume_key_rejected():
    data = _valid_dict()
    data["capability"][0]["consumes"] = ["madin.private.id"]
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("not a registered shared key" in p for p in problems)


def test_always_computed_groups_accepts_declared_group():
    data = _valid_dict()
    data["capability"][0]["always_computed_groups"] = ["traits.core"]
    spec = WeaverSpec.from_dict(data)
    assert spec.capabilities[0].always_computed_groups == ("traits.core",)
    assert validate_spec(spec) == []


def test_always_computed_groups_rejects_undeclared_group():
    data = _valid_dict()
    data["capability"][0]["always_computed_groups"] = ["nope"]
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("always_computed_groups references 'nope'" in p for p in problems)


def test_overlapping_group_outputs_rejected():
    data = _valid_dict()
    data["capability"][0]["group"][1]["outputs"] = ["microbe.trait.gram_stain"]
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("disjoint" in p for p in problems)


def test_empty_source_sample_rejected():
    data = _valid_dict()
    data["weaver"]["source_sample"] = "   "
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("source_sample" in p for p in problems)


def test_unknown_fingerprint_rejected():
    data = _valid_dict()
    data["weaver"]["fingerprint_source"] = "unknown"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("unknown" in p for p in problems)


def test_bad_db_name_rejected():
    data = _valid_dict()
    data["weaver"]["db_name"] = "Madin-DB"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("db_name" in p for p in problems)


def test_no_backends_rejected():
    data = _valid_dict()
    data["weaver"]["backends"] = []
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("backend" in p for p in problems)


def test_no_capabilities_rejected():
    data = _valid_dict()
    data["capability"] = []
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("at least one capability" in p for p in problems)


def test_capability_backend_not_in_weaver_backends_rejected():
    data = _valid_dict()
    data["capability"][0]["backends"] = ["api"]  # weaver only declares "local"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("not in the weaver's backends" in p for p in problems)


def test_group_without_outputs_rejected():
    data = _valid_dict()
    data["capability"][0]["group"][0]["outputs"] = []
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("no outputs" in p for p in problems)


def test_duplicate_group_id_rejected():
    data = _valid_dict()
    data["capability"][0]["group"][1]["id"] = "traits.core"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("duplicate output group id" in p for p in problems)


def test_golden_undeclared_capability_rejected():
    data = _valid_dict()
    data["golden"][0]["capability"] = "no_such_cap"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("not declared" in p for p in problems)


def test_golden_input_key_not_in_consumes_rejected():
    data = _valid_dict()
    data["golden"][0]["input"] = {"organism.name": "E. coli"}
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("not in capability" in p and "consumes" in p for p in problems)


def test_golden_expect_key_not_in_produces_rejected():
    data = _valid_dict()
    data["golden"][0]["expect"] = {"microbe.trait.not_a_real_output": "x"}
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("not in capability" in p and "produces" in p for p in problems)


def test_kind_defaults_to_lookup():
    data = _valid_dict()
    assert "kind" not in data["weaver"]
    assert WeaverSpec.from_dict(data).kind == "lookup"


def test_kind_resolver_accepted():
    data = _valid_dict()
    data["weaver"]["kind"] = "resolver"
    spec = WeaverSpec.from_dict(data)
    assert spec.kind == "resolver"
    assert validate_spec(spec) == []


def test_kind_invalid_rejected():
    data = _valid_dict()
    data["weaver"]["kind"] = "fuzzy"
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("kind" in p for p in problems)


def test_bulk_parsed_when_present():
    data = _valid_dict()
    data["bulk"] = {
        "backend": "local",
        "archive_url": "https://example.org/d.tar.gz",
        "filename": "x.sqlite",
    }
    spec = WeaverSpec.from_dict(data)
    assert spec.bulk is not None
    assert spec.bulk.backend == "local"
    assert validate_spec(spec) == []


def test_bulk_absent_by_default():
    assert WeaverSpec.from_dict(_valid_dict()).bulk is None


def test_bulk_backend_not_in_backends_rejected():
    data = _valid_dict()
    data["bulk"] = {"backend": "api", "archive_url": "https://x", "filename": "x.sqlite"}
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("[bulk]" in p and "not in the weaver's backends" in p for p in problems)


def test_bulk_empty_archive_url_rejected():
    data = _valid_dict()
    data["bulk"] = {"backend": "local", "archive_url": "  ", "filename": "x.sqlite"}
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert any("archive_url" in p for p in problems)


def test_bulk_filename_defaults_to_db_name():
    data = _valid_dict()
    data["bulk"] = {"backend": "local", "archive_url": "https://x"}
    spec = WeaverSpec.from_dict(data)
    assert spec.bulk.filename == "madin.sqlite"


def test_multiple_problems_reported_at_once():
    data = _valid_dict()
    data["weaver"]["source_sample"] = ""
    data["weaver"]["fingerprint_source"] = "unknown"
    data["capability"][0]["consumes"] = ["nope.key"]
    problems = validate_spec(WeaverSpec.from_dict(data))
    assert len(problems) >= 3


def test_golden_spec_from_dict_roundtrip():
    g = GoldenSpec.from_dict({"capability": "c", "input": {"k": "v"}, "expect": {"o": "r"}})
    assert g == GoldenSpec(capability="c", input={"k": "v"}, expect={"o": "r"})


def test_mutating_copy_does_not_share_state():
    base = _valid_dict()
    clone = copy.deepcopy(base)
    clone["weaver"]["db_name"] = "other"
    assert base["weaver"]["db_name"] == "madin"
