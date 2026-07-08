#!/usr/bin/env bash
# Regenerate svg-deck/ from braidworks-portfolio-deck.drawio (the deck-accurate
# portfolio diagrams) + the cost chart. Same drawio flatpak export + force-white
# post-process as export-svg.sh, but with meaningful filenames.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/braidworks-portfolio-deck.drawio"
OUT="$HERE/svg-deck"
mkdir -p "$OUT"

# drawio page index (1-based) -> output name
declare -A PAGES=(
  [1]=have-to-want [3]=data-model [4]=plan-execute [5]=interfaces [6]=stack [7]=four-tiers
)
for idx in "${!PAGES[@]}"; do
  flatpak run --filesystem=home com.jgraph.drawio.desktop \
    -x -p "$idx" -f svg --no-sandbox -o "$OUT/${PAGES[$idx]}.svg" "$SRC" >/dev/null 2>&1 || true
done

# Force light background (match the committed format; render light in any viewer).
python3 - "$OUT" <<'PY'
import sys, pathlib
out = pathlib.Path(sys.argv[1])
old = "background: transparent; background-color: transparent; color-scheme: light dark;"
new = "background: #ffffff; background-color: #ffffff; color-scheme: light;"
for svg in sorted(out.glob("*.svg")):
    if svg.name == "cost.svg":
        continue
    t = svg.read_text(encoding="utf-8").replace(old, new)
    if 'data-bw-bg="1"' not in t:
        t = t.replace("<defs/>", '<defs/><rect data-bw-bg="1" width="100%" height="100%" fill="#ffffff"/>', 1)
    svg.write_text(t, encoding="utf-8")
    print(f"processed {svg.name}")
PY

# The cost chart is code, not drawio.
python3 "$HERE/cost-chart.py"
