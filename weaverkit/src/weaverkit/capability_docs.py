"""Render spec-owned capability inventories inside otherwise hand-written documents."""

from pathlib import Path

from weaverkit.spec import SpecError, WeaverSpec, load_spec, validate_spec

START = "<!-- weaverkit:capabilities:start -->"
END = "<!-- weaverkit:capabilities:end -->"


def _code(value: str) -> str:
    return "`" + value.replace("`", "&#96;").replace("|", r"\|").replace("\n", " ") + "`"


def render_capabilities(spec: WeaverSpec) -> str:
    """Return a deterministic exact inventory; explanations stay outside the markers."""
    rows = [
        "| Capability | Input types | Output groups / expandable keys | Backends | Parameters |",
        "|---|---|---|---|---|",
    ]
    for cap in spec.capabilities:
        inputs = (" or " if cap.consumes_any else ", ").join(_code(key) for key in cap.consumes)
        groups = ", ".join(_code(group.id) for group in cap.groups)
        if cap.set_outputs:
            groups += "; expands " + ", ".join(_code(key) for key in sorted(cap.set_outputs))
        backends = ", ".join(_code(name) for name in (cap.backends or spec.backends))
        params = ", ".join(_code(param.name) for param in cap.parameters) or "—"
        rows.append(f"| {_code(cap.id)} | {inputs} | {groups} | {backends} | {params} |")
    return "\n".join(rows)


def replace_inventory(document: str, spec: WeaverSpec) -> str:
    """Replace one explicitly owned region, rejecting missing or malformed markers."""
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("expected exactly one capability start/end marker pair")
    before, remaining = document.split(START)
    _generated, after = remaining.split(END)
    if END in before or START in after:
        raise ValueError("capability markers must be ordered start then end")
    return before + START + "\n" + render_capabilities(spec) + "\n" + END + after


def update_capability_docs(root: Path, *, check: bool = False) -> list[Path]:
    """Validate every source before writing; check mode reports drift without writes.

    Accept a workspace root or one package directory. Marker ownership is explicit;
    newly introduced reference pages must move the markers deliberately.
    """
    specs = (
        [root / "weaver.spec.toml"]
        if (root / "weaver.spec.toml").is_file()
        else sorted(root.glob("weavers/*/weaver.spec.toml"))
    )
    if not specs:
        raise ValueError(f"{root}: no weaver specs found")
    changes = []
    for path in specs:
        spec = load_spec(path)
        problems = validate_spec(spec)
        if problems:
            raise SpecError(f"{path}: " + "; ".join(problems))
        candidates = [path.parent / name for name in ("README.md", "REFERENCE.md")]
        owned = []
        for doc in candidates:
            if doc.is_file():
                text = doc.read_text()
                if START in text or END in text:
                    owned.append((doc, text))
        if len(owned) != 1:
            raise ValueError(f"{path.parent}: expected one marked README.md or REFERENCE.md")
        doc, original = owned[0]
        updated = replace_inventory(original, spec)
        if updated != original:
            changes.append((doc, updated))
    if not check:
        for path, updated in changes:
            path.write_text(updated)
    return [path for path, _ in changes]
