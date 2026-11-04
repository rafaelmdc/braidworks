"""Optional taxdump history: pure parsing and validation before persistence."""

from collections.abc import Iterable


def parse_history(
    merged_rows: Iterable[list[str]], deleted_rows: Iterable[list[str]]
) -> tuple[dict[int, int], set[int]]:
    merged = {}
    deleted = set()
    for fields in merged_rows:
        if len(fields) != 2:
            raise ValueError("merged.dmp rows require two taxids")
        old, new = map(int, fields)
        if old < 1 or new < 1 or old in merged:
            raise ValueError("merged.dmp contains invalid or repeated taxids")
        merged[old] = new
    for fields in deleted_rows:
        if len(fields) != 1:
            raise ValueError("delnodes.dmp rows require one taxid")
        taxid = int(fields[0])
        if taxid < 1 or taxid in deleted or taxid in merged:
            raise ValueError("delnodes.dmp contains invalid, repeated or merged taxids")
        deleted.add(taxid)
    checked = set()
    for start in merged:
        path = set()
        node = start
        while node in merged and node not in checked:
            if node in path:
                raise ValueError("merged.dmp contains a merge cycle")
            path.add(node)
            node = merged[node]
        checked.update(path)
    return merged, deleted
