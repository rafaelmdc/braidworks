"""GTDB reference-tree geometry: Newick → per-leaf root paths → patristic distance.

The phylogeny "distance" between two organisms is the **patristic (cophenetic)
distance** on the GTDB bac120/ar53 reference tree — the summed branch length on the
path between their two species-representative leaves.

**What the number means.** GTDB's branch lengths are in **expected amino-acid
substitutions per site** (the tree is inferred from a concatenated alignment of the
bac120 / ar53 marker proteins), so a patristic distance is the **total molecular
divergence** accumulated along the evolutionary path between two genomes — larger =
more diverged. The absolute value is scale-specific to the tree/alignment and is not
meaningful on its own; only the **relative ordering** of distances is (a consumer
should rank-normalize rather than lean on the raw magnitude).

Braidworks resolves *per entity* (one input id → its attributes), never per pair, so
this module deliberately splits the computation into two halves:

* :func:`build_rootpaths` — the per-leaf, batch-independent half. Each leaf's **root
  path** (``[(node_id, cumulative_depth), …]`` from the root down to the leaf) is a pure
  function of the leaf alone, so it is what the weaver *emits* as ``gtdb.tree.rootpath``
  and what the executor can cache per id. Node ids are assigned by a deterministic
  pre-order walk of the (fixed, per-release) tree, so two leaves fetched in different
  calls carry consistent ids for their shared ancestors.
* :func:`cophenetic` — the pairwise reduction. Given two root paths it finds their
  most-recent common ancestor (the deepest shared node id, since tree paths share a
  root prefix then diverge) and returns ``depth(a) + depth(b) − 2·depth(mrca)``. This is
  the one bit of genuinely pairwise math; a consumer (e.g. ORDINA's phylogeny layer)
  calls it to turn a set of fetched root paths into edges. Keeping it here means the
  tree-distance semantics are authored once, beside the tree that defines them.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# One step on a leaf's path from the root: the ancestor node's stable id and the
# cumulative branch length (depth) from the root to that node.
RootStep = tuple[int, float]
RootPath = list[RootStep]


@dataclass
class _Node:
    name: str = ""
    length: float | None = None
    children: list[_Node] = field(default_factory=list)


class NewickError(ValueError):
    """The Newick text could not be parsed."""


def parse_newick(text: str) -> _Node:
    """Parse a Newick string into a tree of :class:`_Node`, returning the root.

    Handles the GTDB dialect: nested clades, unquoted or single-quoted labels
    (internal labels are support values / taxon strings), and ``:branch_length``.
    Whitespace between tokens is ignored; a trailing ``;`` is optional.
    """
    parser = _Parser(text)
    root = parser.parse_clade()
    parser.skip_ws()
    if parser.pos < len(text) and text[parser.pos] == ";":
        parser.pos += 1
    return root


class _Parser:
    _SPECIAL = set("(),:;")

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def parse_clade(self) -> _Node:
        self.skip_ws()
        node = _Node()
        if self.pos < len(self.text) and self.text[self.pos] == "(":
            self.pos += 1  # consume "("
            node.children.append(self.parse_clade())
            self.skip_ws()
            while self.pos < len(self.text) and self.text[self.pos] == ",":
                self.pos += 1
                node.children.append(self.parse_clade())
                self.skip_ws()
            if self.pos >= len(self.text) or self.text[self.pos] != ")":
                raise NewickError(f"expected ')' at position {self.pos}")
            self.pos += 1  # consume ")"
        node.name = self._parse_label()
        self.skip_ws()
        if self.pos < len(self.text) and self.text[self.pos] == ":":
            self.pos += 1
            node.length = self._parse_length()
        return node

    def _parse_label(self) -> str:
        self.skip_ws()
        if self.pos < len(self.text) and self.text[self.pos] == "'":
            return self._parse_quoted()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in self._SPECIAL:
            if self.text[self.pos].isspace():
                break
            self.pos += 1
        return self.text[start : self.pos].strip()

    def _parse_quoted(self) -> str:
        self.pos += 1  # consume opening quote
        buf: list[str] = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "'":
                # A doubled '' is an escaped single quote inside the label.
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == "'":
                    buf.append("'")
                    self.pos += 2
                    continue
                self.pos += 1  # consume closing quote
                return "".join(buf)
            buf.append(ch)
            self.pos += 1
        raise NewickError("unterminated quoted label")

    def _parse_length(self) -> float:
        self.skip_ws()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in self._SPECIAL:
            if self.text[self.pos].isspace():
                break
            self.pos += 1
        token = self.text[start : self.pos].strip()
        try:
            return float(token)
        except ValueError as exc:
            raise NewickError(f"invalid branch length {token!r}") from exc


def _walk(
    node: _Node, parent: RootPath, counter: itertools.count[int], paths: dict[str, RootPath]
) -> None:
    node_id = next(counter)
    depth = (parent[-1][1] if parent else 0.0) + (node.length or 0.0)
    path = parent + [(node_id, depth)]
    if node.children:
        for child in node.children:
            _walk(child, path, counter, paths)
    elif node.name:
        paths[node.name] = path


def build_rootpaths(root: _Node) -> dict[str, RootPath]:
    """Map each leaf label to its root path ``[(node_id, depth), …]``.

    Node ids come from a deterministic pre-order walk (root = 0, then children in file
    order), so the ids of a leaf's ancestors are identical no matter which batch fetched
    it — the property that lets :func:`cophenetic` align two independently-fetched paths.
    ``depth`` is the cumulative branch length from the root (the root itself is depth 0).
    """
    paths: dict[str, RootPath] = {}
    _walk(root, [], itertools.count(), paths)
    return paths


def load_rootpaths(texts: Iterable[str]) -> dict[str, RootPath]:
    """Root paths for the leaves of several Newick trees under one shared id space.

    GTDB ships two disjoint reference trees (bacteria ``bac120`` + archaea ``ar53``).
    A single id counter spans all of them, so no leaf in one tree shares an ancestor id
    with a leaf in another: :func:`cophenetic` between cross-tree leaves finds no common
    node and returns their summed root depths (maximally distant), which is the right
    answer for organisms in different domains — while within a tree it is exact.
    """
    paths: dict[str, RootPath] = {}
    counter: itertools.count[int] = itertools.count()
    for text in texts:
        _walk(parse_newick(text), [], counter, paths)
    return paths


def cophenetic(a: Sequence[RootStep], b: Sequence[RootStep]) -> float:
    """Patristic distance between two leaves, from their root paths.

    The most-recent common ancestor is the deepest node the two paths share (they run
    together from the root, then diverge and never meet again), so the distance is
    ``depth(a_leaf) + depth(b_leaf) − 2·depth(mrca)``. Identical leaves give 0.

    Accepts any sequence of ``(node_id, depth)`` pairs — including the ``[id, depth]``
    lists produced by JSON round-tripping through a strand value.
    """
    if not a or not b:
        raise ValueError("root paths must be non-empty")
    mrca_depth = 0.0
    for (na, da), (nb, _db) in zip(a, b):
        if na == nb:
            mrca_depth = da
        else:
            break
    return float(a[-1][1]) + float(b[-1][1]) - 2.0 * mrca_depth
