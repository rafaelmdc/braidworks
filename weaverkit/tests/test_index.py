"""Index builder tests — discovery, reachability, and rendering.

The index is a map (not a gate), so these check that it flattens specs correctly,
computes unmet inputs across weavers, and round-trips through TSV/CSV.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from weaverkit.index import (
    COLUMNS,
    build_index,
    build_key_rows,
    build_rows,
    discover_specs,
    render,
    render_keys_md,
    uncatalogued_outputs,
    write_index,
    write_key_index,
)
from weaverkit.keys import is_known_output
from weaverkit.spec import CapabilitySpec, GroupSpec, WeaverSpec


def _spec(db_name: str, consumes: tuple[str, ...], outputs: tuple[str, ...], **kw) -> WeaverSpec:
    return WeaverSpec(
        db_name=db_name,
        title=f"{db_name} title",
        version="0.1.0",
        license="CC0-1.0",
        source_url="https://example.org",
        fingerprint_source="release-tag",
        source_sample="a,b\n1,2\n",
        backends=kw.pop("backends", ("local",)),
        capabilities=(
            CapabilitySpec(
                id=kw.pop("cap_id", "resolve"),
                consumes=consumes,
                groups=(GroupSpec(id="g", outputs=outputs),),
            ),
        ),
        **kw,
    )


def test_build_rows_flattens_and_joins_multivalue() -> None:
    spec = _spec("madin", ("ncbi.taxon.id",), ("microbe.trait.gram_stain", "microbe.trait.opt"))
    (row,) = build_rows([spec])
    assert row.weaver == "madin"
    assert row.capability == "resolve"
    assert row.consumes == "ncbi.taxon.id"
    assert row.produces == "microbe.trait.gram_stain;microbe.trait.opt"


def test_entry_key_is_never_unmet() -> None:
    # organism.name is the user-supplied entry point, so it's always "met".
    spec = _spec("taxon", ("organism.name",), ("ncbi.taxon.id",))
    (row,) = build_rows([spec])
    assert row.unmet_inputs == ""


def test_input_met_by_another_weaver() -> None:
    producer = _spec("taxon", ("organism.name",), ("ncbi.taxon.id",))
    consumer = _spec("madin", ("ncbi.taxon.id",), ("microbe.trait.gram_stain",))
    rows = {r.weaver: r for r in build_rows([producer, consumer])}
    assert rows["madin"].unmet_inputs == ""  # taxon produces ncbi.taxon.id


def test_island_input_is_reported_unmet() -> None:
    # gene.ncbi.id is a registered shared key but nothing here produces it.
    spec = _spec("orphan", ("gene.ncbi.id",), ("go.term",))
    (row,) = build_rows([spec])
    assert row.unmet_inputs == "gene.ncbi.id"


def test_api_key_column_carried_through() -> None:
    spec = _spec("api", ("ncbi.taxon.id",), ("go.term",), backends=("api",), api_key="required")
    (row,) = build_rows([spec])
    assert row.api_key == "required"


def test_render_tsv_header_and_parse() -> None:
    spec = _spec("madin", ("ncbi.taxon.id",), ("go.term",))
    text = render(build_rows([spec]), delimiter="\t")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    assert tuple(reader.fieldnames) == COLUMNS
    (parsed,) = list(reader)
    assert parsed["weaver"] == "madin"
    assert parsed["consumes"] == "ncbi.taxon.id"


def test_discover_skips_fixtures(tmp_path: Path) -> None:
    (tmp_path / "realweaver").mkdir()
    (tmp_path / "realweaver" / "weaver.spec.toml").write_text("x")
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    (tmp_path / "tests" / "fixtures" / "weaver.spec.toml").write_text("x")
    found = discover_specs(tmp_path)
    assert [p.parent.name for p in found] == ["realweaver"]


def test_write_index_picks_delimiter_from_suffix(tmp_path: Path) -> None:
    weaver_dir = tmp_path / "exampleweaver"
    weaver_dir.mkdir()
    spec_toml = (
        Path(__file__).parents[2] / "weavers" / "exampleweaver" / "weaver.spec.toml"
    ).read_text()
    (weaver_dir / "weaver.spec.toml").write_text(spec_toml)

    tsv = tmp_path / "out.tsv"
    csv_out = tmp_path / "out.csv"
    write_index(tmp_path, tsv)
    write_index(tmp_path, csv_out)
    assert "\t" in tsv.read_text()
    assert "," in csv_out.read_text()


def test_is_known_output_shared_catalogued_and_unknown() -> None:
    assert is_known_output("ncbi.taxon.id")  # shared key
    assert is_known_output("ncbi.taxon.parent_id")  # catalogued leaf output
    assert not is_known_output("some.invented.field")


def test_uncatalogued_outputs_flags_unknown_produced_field() -> None:
    spec = _spec("widget", ("ncbi.taxon.id",), ("some.invented.field", "ncbi.taxon.parent_id"))
    rows = build_rows([spec])
    assert uncatalogued_outputs(rows) == ["some.invented.field"]


def test_uncatalogued_outputs_empty_when_all_known() -> None:
    spec = _spec("widget", ("ncbi.taxon.id",), ("ncbi.taxon.parent_id",))
    assert uncatalogued_outputs(build_rows([spec])) == []


def test_build_index_real_workspace() -> None:
    # The real repo root has at least exampleweaver with a valid spec.
    root = Path(__file__).parents[2]
    rows = build_index(root)
    assert any(r.weaver == "example" for r in rows)


# --- key-centric pivot -------------------------------------------------------


def test_build_key_rows_wires_producers_and_consumers() -> None:
    producer = _spec("taxon", ("organism.name",), ("ncbi.taxon.id",))
    consumer = _spec("madin", ("ncbi.taxon.id",), ("microbe.trait.gram_stain",))
    by_key = {k.key: k for k in build_key_rows(build_rows([producer, consumer]))}
    assert by_key["ncbi.taxon.id"].produced_by == "taxon:resolve"
    assert by_key["ncbi.taxon.id"].consumed_by == "madin:resolve"


def test_build_key_rows_classifies_roles() -> None:
    spec = _spec("widget", ("organism.name",), ("ncbi.taxon.parent_id", "some.invented.field"))
    by_key = {k.key: k for k in build_key_rows(build_rows([spec]))}
    assert by_key["organism.name"].role == "entry"
    assert by_key["ncbi.taxon.id"].role == "shared"  # registered, even though unused here
    assert by_key["ncbi.taxon.parent_id"].role == "leaf"
    assert by_key["some.invented.field"].role == "uncatalogued"


def test_build_key_rows_includes_registered_but_unused_key() -> None:
    spec = _spec("taxon", ("organism.name",), ("ncbi.taxon.id",))
    by_key = {k.key: k for k in build_key_rows(build_rows([spec]))}
    # gene.ncbi.id is a registered shared key nothing here touches — still listed, empty wiring.
    assert by_key["gene.ncbi.id"].produced_by == ""
    assert by_key["gene.ncbi.id"].consumed_by == ""


def test_render_keys_md_has_note_sections_and_rows() -> None:
    producer = _spec("taxon", ("organism.name",), ("ncbi.taxon.id",))
    consumer = _spec("madin", ("ncbi.taxon.id",), ("some.invented.field",))
    md = render_keys_md(build_key_rows(build_rows([producer, consumer])))
    assert "do not edit by hand" in md
    assert "## Shared join keys" in md
    assert "## Uncatalogued (naming-drift risk)" in md
    assert "`ncbi.taxon.id`" in md
    assert "`taxon:resolve`" in md  # producer wired into the table


def test_write_key_index_emits_markdown(tmp_path: Path) -> None:
    weaver_dir = tmp_path / "exampleweaver"
    weaver_dir.mkdir()
    spec_toml = (
        Path(__file__).parents[2] / "weavers" / "exampleweaver" / "weaver.spec.toml"
    ).read_text()
    (weaver_dir / "weaver.spec.toml").write_text(spec_toml)

    out = tmp_path / "keys-index.md"
    write_key_index(tmp_path, out)
    assert out.read_text().startswith("# Key index")
