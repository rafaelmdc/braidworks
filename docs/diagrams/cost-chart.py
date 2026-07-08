#!/usr/bin/env python3
"""Render the 'capability cost' chart (svg-deck/cost.svg) from recorded data.

This diagram is a chart, not a box-and-arrow drawing, so it lives here as code
rather than in the .drawio. The other portfolio diagrams are in
braidworks-portfolio-deck.drawio; render those with export-svg.sh.

    python cost-chart.py        # needs matplotlib
"""
import pathlib

import matplotlib
matplotlib.use("svg")
import matplotlib.pyplot as plt

OUT = pathlib.Path(__file__).parent / "svg-deck" / "cost.svg"

# Tokens (thousands) to build & debug each weaverkit capability, in build order.
labels = ["ncbi", "bacdive", "uniprot", "STRING", "PDB", "alpha fold",
          "go list", "reactome", "reactome\ndescribe", "go\ndescribe", "pdb\ndescribe"]
vals = [110, 37, 51, 33, 32, 21, 25, 15, 26, 27, 22]

GREEN, ORANGE, GREY = "#2E7D5B", "#C8860D", "#5A6670"
BAND_LO, BAND_HI, AVG = 15, 51, 29

plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
fig, ax = plt.subplots(figsize=(13, 6.2), dpi=100)
x = list(range(len(vals)))

ax.axhspan(BAND_LO, BAND_HI, color=GREEN, alpha=0.10, zorder=0)
ax.axhline(AVG, color=GREEN, ls="--", lw=1.2, alpha=0.7, zorder=1)

ax.plot(x, vals, color=GREEN, lw=2.2, zorder=2)
ax.scatter(x[1:], vals[1:], color=GREEN, s=42, zorder=3)
ax.scatter([0], [110], color=ORANGE, s=120, zorder=4)

for xi, v in zip(x, vals):
    ax.annotate(f"{v}k", (xi, v), textcoords="offset points", xytext=(0, 10),
                ha="center", fontsize=10, fontweight="bold", color="#222")

ax.annotate("first build\nframework + learning cost, paid once",
            xy=(0.15, 108), xytext=(1.1, 100), fontsize=11, color="#222", va="center",
            arrowprops=dict(arrowstyle="->", color=GREY, lw=1))
ax.text(4.4, 78, "After the first build, cost drops and stays bounded.",
        fontsize=12, fontweight="bold", color="#222")
ax.text(4.4, 70, "It doesn't climb as the system grows — every capability shares the\n"
        "same deterministic backbone; variation is the data source's messiness.",
        fontsize=10.5, color=GREY)
ax.text(len(vals) - 0.5, BAND_HI + 1.5, "bounded band · 15–51k",
        fontsize=10, color=GREEN, ha="right")
ax.text(0.15, AVG + 2.2, "~29k average (after the first build)",
        fontsize=10, color=GREEN, ha="left", style="italic")

ax.set_title("What each new capability costs — paid once, then bounded",
             fontsize=16, fontweight="bold", loc="left", color="#111", pad=26)
ax.annotate("Tokens to build & debug each weaverkit capability, in build order.",
            xy=(0, 1.03), xycoords="axes fraction", fontsize=11, color=GREY)

ax.set_ylim(0, 122)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10, color=GREY)
ax.set_yticks([0, 20, 40, 60, 80, 100, 120])
ax.set_yticklabels(["0", "20k", "40k", "60k", "80k", "100k", "120k"], fontsize=9, color=GREY)
ax.set_ylabel("tokens", fontsize=10, color=GREY)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#CCC")
ax.tick_params(length=0)
ax.grid(axis="y", color="#EEE", lw=0.8)
ax.set_axisbelow(True)

fig.tight_layout()
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, format="svg", bbox_inches="tight", facecolor="white")
print("wrote", OUT)
