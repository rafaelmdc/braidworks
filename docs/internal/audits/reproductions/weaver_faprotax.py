"""Offline source-grammar probes against the bundled FAPROTAX rules."""

from faprotax_weaver.backends.local import _functional_groups, _load_groups

for names in (["Methanosarcina", "Methanosarcina barkeri"], ["Methanosarcina", "barkeri"]):
    print(names, _functional_groups(names))
print("Operator parsed as group", [name for name in _load_groups() if "group:" in name])
print(
    "Photosynthetic chloroplast labels",
    _functional_groups(["Bacteria", "Cyanobacteriia", "chloroplast"]),
)
