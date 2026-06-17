#!/usr/bin/env bash
# Regenerate the committed SVGs from the drawio source.
# drawio (flatpak) CLI export + force-white-background post-process so the
# committed SVGs render light regardless of the viewer's color scheme.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/braidworks_portfolio_diagrams.drawio"
OUT="$HERE/svg"
mkdir -p "$OUT"

# 6 pages (1-based in drawio) -> page-0..page-5.svg
for n in 1 2 3 4 5 6; do
  idx=$((n - 1))
  dest="$OUT/page-$idx.svg"
  flatpak run --filesystem=home com.jgraph.drawio.desktop \
    -x -p "$n" -f svg -o "$dest" "$SRC" >/dev/null 2>&1 || true
done

# Post-process: force light background to match the committed format.
python3 - "$OUT" <<'PY'
import sys, pathlib
out = pathlib.Path(sys.argv[1])
old_style = "background: transparent; background-color: transparent; color-scheme: light dark;"
new_style = "background: #ffffff; background-color: #ffffff; color-scheme: light;"
for svg in sorted(out.glob("page-*.svg")):
    t = svg.read_text(encoding="utf-8")
    t = t.replace(old_style, new_style)
    if 'data-bw-bg="1"' not in t:
        t = t.replace("<defs/>", '<defs/><rect data-bw-bg="1" width="100%" height="100%" fill="#ffffff"/>', 1)
    svg.write_text(t, encoding="utf-8")
    print(f"processed {svg.name}")
PY
