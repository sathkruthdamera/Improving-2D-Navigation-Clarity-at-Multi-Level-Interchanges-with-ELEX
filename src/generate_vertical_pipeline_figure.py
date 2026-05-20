"""Generate a readable vertical Figure 2 for the ELEX research paper.

This replaces the earlier horizontal pipeline diagram where text overlapped
inside narrow boxes.

Run:
    pip install matplotlib
    python src/generate_vertical_pipeline_figure.py

Output:
    outputs/fig02_elex_pipeline_vertical.png
"""

from pathlib import Path
import textwrap
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
out = OUT / "fig02_elex_pipeline_vertical.png"

fig, ax = plt.subplots(figsize=(7.2, 9.8), dpi=240)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

ax.text(0.5, 0.972, "Elevation-aware Local Exploded View (ELEX)",
        ha="center", va="top", fontsize=15.2, fontweight="bold")
ax.text(0.5, 0.935, "Vertical Rendering Pipeline",
        ha="center", va="top", fontsize=14.0, fontweight="bold")

steps = [
    ("1. Road graph ingest", "OSM layer/bridge tags, lane geometry, active route polyline, and optional elevation data."),
    ("2. Conflict detection", "Compute projected overlap, branch factor, stacked-road count, and route ambiguity near the decision point."),
    ("3. Trigger decision", "Activate enhanced view only when the driver is within the look-ahead window and complexity exceeds threshold."),
    ("4. Visual transform", "Apply bounded luminance, opacity hierarchy, route halo, arrows, soft shadow, and local exploded offset."),
    ("5. Car display render", "Draw lower layers first, higher layers second, and the active route last for clearer route commitment."),
]

left, width = 0.12, 0.76
box_h = 0.112
ys = [0.735, 0.590, 0.445, 0.300, 0.155]

for idx, ((title, body), y) in enumerate(zip(steps, ys)):
    patch = FancyBboxPatch((left, y), width, box_h,
                           boxstyle="round,pad=0.018,rounding_size=0.028",
                           linewidth=1.35, edgecolor="0.33", facecolor="0.965")
    ax.add_patch(patch)
    ax.text(left + width / 2, y + box_h * 0.73, title,
            ha="center", va="center", fontsize=10.9, fontweight="bold")
    ax.text(left + width / 2, y + box_h * 0.34, textwrap.fill(body, width=57),
            ha="center", va="center", fontsize=8.9, linespacing=1.25)

    if idx < len(ys) - 1:
        x = left + width / 2
        ax.add_patch(FancyArrowPatch((x, y - 0.012), (x, ys[idx + 1] + box_h + 0.012),
                                     arrowstyle="-|>", mutation_scale=15,
                                     linewidth=1.25, color="0.28"))

principle = (
    "Design principle: preserve traffic colors for traffic state; "
    "use independent visual channels only near complex interchanges."
)
ax.text(0.5, 0.065, textwrap.fill(principle, 86),
        ha="center", va="center", fontsize=8.7, linespacing=1.2)

fig.savefig(out, bbox_inches="tight", pad_inches=0.18)
print(f"Saved {out}")
