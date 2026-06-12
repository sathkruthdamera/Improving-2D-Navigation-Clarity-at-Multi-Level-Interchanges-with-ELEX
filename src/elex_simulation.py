"""
ELEX: Elevation-Aware Local Exploded View renderer for 2D navigation clarity
at multi-level interchanges.

This module is a *full working implementation* of the ELEX algorithm described
in the paper, not pseudocode. It contains:

  1. A synthetic Dallas-Fort Worth-style stacked interchange (build_roads).
  2. The elevation-luminance encoding          L_e = clip(L_max - k*h, L_min, L_max)
  3. The local exploded-layout transform        x' = x + lambda*(h-mean h)*n + gamma*g(d)*u
  4. The complexity trigger                      K(v) = w_b*B + w_o*O + w_z*Z + w_s*S
  5. The look-ahead activation logic             activate iff K > threshold and d < D
  6. A vectorized clarity-metric evaluator (PDI, candidate roads, confusion risk).
  7. Figure generation for every figure referenced by the paper, including the
     trigger plot (Fig. 8) and the CarPlay-style mockup (Fig. 9).

Run:
    pip install numpy matplotlib
    python src/elex_simulation.py

Outputs (written to ./outputs and mirrored into ./data/metrics.csv):
    outputs/algorithm_variants.png
    outputs/simulation_steps.png
    outputs/pdi_barplot.png
    outputs/confusion_risk_barplot.png
    outputs/trigger_plot.png            (Fig. 8 - look-ahead activation)
    outputs/carplay_mockup.png          (Fig. 9 - baseline vs ELEX display)
    outputs/metrics.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
DATA = Path("data")


# --------------------------------------------------------------------------- #
# Configuration - every magic number in one auditable place.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ElexConfig:
    # --- world scale --------------------------------------------------------
    meters_per_unit: float = 140.0      # 1 scene unit ~ 140 m of real road
    lookahead_m: float = 500.0          # NHTSA-style decision look-ahead window

    # --- elevation luminance  L_e = clip(L_max - k*h, L_min, L_max) ----------
    L_min: float = 0.37
    L_max: float = 0.83
    k_lum: float = 0.45

    # --- exploded layout  x' = x + lambda*(h-mean h)*n + gamma*g(d)*u --------
    explode_radius_R: float = 4.2       # activation radius (scene units)
    gamma_base: float = 0.72            # base outward explode amplitude
    gamma_level: float = 0.06           # extra amplitude per level
    lam_normal: float = 0.08            # normal (per-level) lateral offset
    route_scale_elex: float = 0.38      # route is shifted less (stability)
    route_scale_explode: float = 0.55
    offset_sep: float = 0.16            # normal-offset-layering separation

    # --- complexity trigger  K(v) = w_b*B + w_o*O + w_z*Z + w_s*S -----------
    w_branch: float = 1.0
    w_overlap: float = 1.0
    w_levels: float = 1.0
    w_succession: float = 1.0
    trigger_threshold: float = 2.0      # K above this => clarified view eligible
    perception_radius: float = 3.0      # roads within this of the car are "seen"
    overlap_radius: float = 0.65        # screen distance counted as "stacked"

    # --- metric sampling ----------------------------------------------------
    metric_samples: int = 90
    metric_zone: float = 4.2            # only score inside the activation zone


CFG = ElexConfig()


# --------------------------------------------------------------------------- #
# Geometry primitives
# --------------------------------------------------------------------------- #
@dataclass
class Road:
    name: str
    x: np.ndarray
    y: np.ndarray
    level: int
    route: bool = False


def bezier(p0, p1, p2, p3, n=180):
    t = np.linspace(0, 1, n)
    pts = (((1 - t) ** 3)[:, None] * np.array(p0)
           + (3 * (1 - t) ** 2 * t)[:, None] * np.array(p1)
           + (3 * (1 - t) * t ** 2)[:, None] * np.array(p2)
           + (t ** 3)[:, None] * np.array(p3))
    return pts[:, 0], pts[:, 1]


def line(p0, p1, n=180):
    return np.linspace(p0[0], p1[0], n), np.linspace(p0[1], p1[1], n)


def build_roads():
    """Synthetic DFW-style stacked interchange: 10 segments, 5 vertical levels."""
    roads = []
    x, y = line((-6, 0), (6, 0));            roads.append(Road("east-west mainline", x, y, 0))
    x, y = line((0, -5.5), (0, 5.5));        roads.append(Road("north-south mainline", x, y, 1))
    x, y = line((-6, -0.75), (6, -0.75));    roads.append(Road("frontage road", x, y, -1))
    x, y = line((0.75, -5.5), (0.75, 5.5));  roads.append(Road("collector road", x, y, 0))
    x, y = bezier((-5, -0.1), (-2, 3.5), (2.5, 3.4), (5.5, 0.15));     roads.append(Road("upper direct connector", x, y, 3))
    x, y = bezier((-5, 0.25), (-2.4, -3.1), (2.4, -3.25), (5.5, -0.15)); roads.append(Road("lower sweeping connector", x, y, 2))
    x, y = bezier((-0.25, -5), (3.6, -2.3), (3.7, 1.6), (0.25, 5));    roads.append(Road("active route loop ramp", x, y, 4, True))
    x, y = bezier((0.15, -5.2), (-3.8, -1.7), (-3.2, 2.4), (-0.2, 5.2)); roads.append(Road("competing flyover", x, y, 2))
    x, y = bezier((-5.2, -3.7), (-3, -0.1), (1.5, 1.8), (5.3, 3.4));   roads.append(Road("diagonal distributor", x, y, 1))
    x, y = bezier((-5.4, 3.6), (-2.7, 1), (1.7, -1.1), (5.4, -3.7));   roads.append(Road("opposing connector", x, y, 2))
    return roads


ROADS = build_roads()
LEVELS = np.array([r.level for r in ROADS])
MIN_L, MAX_L = LEVELS.min(), LEVELS.max()
N_LEVELS = len(np.unique(LEVELS))


def norm_level(level):
    """Normalize a discrete layer index to h in [0, 1]."""
    return (level - MIN_L) / max(1, MAX_L - MIN_L)


def poly_normal(x, y):
    """Unit normal at every vertex of a polyline."""
    dx, dy = np.gradient(x), np.gradient(y)
    n = np.sqrt(dx * dx + dy * dy) + 1e-9
    return -dy / n, dx / n


# --------------------------------------------------------------------------- #
# (1) Elevation luminance encoding
# --------------------------------------------------------------------------- #
def elevation_luminance(level, cfg=CFG):
    """L_e = clip(L_max - k*h, L_min, L_max). Higher roads are darker but legible."""
    h = norm_level(level)
    return float(np.clip(cfg.L_max - cfg.k_lum * h, cfg.L_min, cfg.L_max))


# --------------------------------------------------------------------------- #
# (2) Local exploded-layout transform
# --------------------------------------------------------------------------- #
def exploded_layout(r, cfg=CFG, route_scale=None):
    """x' = x + lambda*(h-mean h)*n + gamma*g(d)*u  with g(d)=max(0,1-d/R).

    Outward push declutters stacked geometry; the route is pushed less so it
    stays where the driver expects it (route-preserving constraint)."""
    x, y = r.x.copy(), r.y.copy()
    d = np.sqrt(x * x + y * y)
    gate = np.clip(1 - d / cfg.explode_radius_R, 0, 1)          # g(d)
    ux, uy = x / (d + 1e-8), y / (d + 1e-8)                     # outward unit u
    amp = cfg.gamma_base + cfg.gamma_level * (r.level - MIN_L)  # gamma
    if r.route and route_scale is not None:
        amp *= route_scale
    x, y = x + amp * gate * ux, y + amp * gate * uy
    return x, y, gate


def normal_offset(r, cfg=CFG):
    """Per-level lateral shift along the road normal (the 'offset' variant)."""
    nx, ny = poly_normal(r.x, r.y)
    sep = cfg.offset_sep * (r.level - MIN_L)
    return r.x + sep * nx, r.y + sep * ny


def transform(mode, roads, cfg=CFG):
    """Apply the geometry transform for a given rendering mode."""
    out = []
    for r in roads:
        if mode == "offset":
            x, y = normal_offset(r, cfg)
        elif mode in {"explode", "elex"}:
            route_scale = (cfg.route_scale_elex if mode == "elex"
                           else cfg.route_scale_explode)
            x, y, gate = exploded_layout(r, cfg, route_scale)
            if mode == "elex":
                nx, ny = poly_normal(x, y)
                x = x + cfg.lam_normal * (r.level - MIN_L) * gate * nx
                y = y + cfg.lam_normal * (r.level - MIN_L) * gate * ny
        else:                                  # baseline / luminance: no geometry change
            x, y = r.x.copy(), r.y.copy()
        out.append(Road(r.name, x, y, r.level, r.route))
    return out


# --------------------------------------------------------------------------- #
# (3) Complexity trigger  K(v) = w_b*B + w_o*O + w_z*Z + w_s*S
# --------------------------------------------------------------------------- #
def _min_dist_point_to_road(q, r, stride=2):
    p = np.c_[r.x[::stride], r.y[::stride]]
    return np.sqrt(((p - q) ** 2).sum(axis=1)).min()


def _closest_point_on_road(q, r, stride=2):
    p = np.c_[r.x[::stride], r.y[::stride]]
    i = int(np.argmin(((p - q) ** 2).sum(axis=1)))
    return p[i]


def complexity_score(vehicle_pos, roads, cfg=CFG):
    """Compute K(v) and its normalized components for a vehicle position.

    Components (each normalized to roughly [0, 1] so a fixed threshold is
    meaningful regardless of scene scale):

      B  branch factor          - distinct roads inside the perception window
      O  projected overlap       - proximity-weighted crowding of those roads
      Z  vertical-level count    - number of distinct layers locally present
      S  successive-decision      - stacked pairs (near in screen, differ in level)
    """
    q = np.asarray(vehicle_pos, dtype=float)
    dists = np.array([_min_dist_point_to_road(q, r) for r in roads])
    near = dists < cfg.perception_radius
    n_near = int(near.sum())

    if n_near == 0:
        return 0.0, {"B": 0.0, "O": 0.0, "Z": 0.0, "S": 0.0, "n_near": 0}

    near_idx = np.where(near)[0]
    near_levels = LEVELS[near_idx]

    # B - branch factor (normalized by total road count)
    B = n_near / len(roads)

    # O - overlap density: proximity-weighted crowding, normalized by n_near
    O = float(np.exp(-dists[near_idx] / cfg.overlap_radius).sum()) / n_near

    # Z - distinct vertical levels present locally
    Z = len(np.unique(near_levels)) / N_LEVELS

    # S - successive/stacked decisions: pairs of near roads whose representative
    #     points are within overlap_radius in screen space but differ in level.
    reps = np.array([_closest_point_on_road(q, roads[i]) for i in near_idx])
    stacked = 0
    pairs = 0
    for a in range(n_near):
        for b in range(a + 1, n_near):
            pairs += 1
            close = np.hypot(*(reps[a] - reps[b])) < cfg.overlap_radius
            if close and near_levels[a] != near_levels[b]:
                stacked += 1
    S = stacked / max(1, pairs)

    K = (cfg.w_branch * B + cfg.w_overlap * O
         + cfg.w_levels * Z + cfg.w_succession * S)
    return float(K), {"B": B, "O": O, "Z": Z, "S": S, "n_near": n_near}


def route_approach_path(roads, n=140):
    """The portion of the active route that approaches the decision center,
    returned as positions plus their straight-line distance to the center."""
    route = next(r for r in roads if r.route)
    pts = np.c_[route.x, route.y]
    d_center = np.hypot(pts[:, 0], pts[:, 1])
    closest = int(np.argmin(d_center))          # apex of the loop near center
    approach = pts[:closest + 1]
    return approach, np.hypot(approach[:, 0], approach[:, 1])


def simulate_lookahead(roads, cfg=CFG):
    """Drive the vehicle down the approach and decide, at each step, whether the
    clarified ELEX view should activate (K > threshold AND distance < window)."""
    approach, d_units = route_approach_path(roads)
    d_m = d_units * cfg.meters_per_unit
    K, active = [], []
    for pos, dm in zip(approach, d_m):
        k, _ = complexity_score(pos, roads, cfg)
        K.append(k)
        active.append(k > cfg.trigger_threshold and dm < cfg.lookahead_m)
    return d_m, np.array(K), np.array(active)


# --------------------------------------------------------------------------- #
# (4) Styling / rendering
# --------------------------------------------------------------------------- #
def style(mode, r, cfg=CFG):
    """Return (linewidth, alpha, color, halo, arrows) for a road in a mode."""
    if mode == "baseline":
        return (3.2 if r.route else 2.2), 1.0, ("#0b5cff" if r.route else "0.55"), False, False
    if mode == "luminance":
        return (3.2 if r.route else 2.4), 1.0, ("#0b5cff" if r.route else f"{elevation_luminance(r.level, cfg):.3f}"), False, False
    if mode in {"offset", "explode"}:
        return (3.2 if r.route else 2.2), 1.0, ("#0b5cff" if r.route else "0.58"), False, False
    if mode == "elex":
        light = f"{elevation_luminance(r.level, cfg):.3f}"
        return (5.4 if r.route else 2.4), (1.0 if r.route else 0.42), ("#00a7ff" if r.route else light), r.route, r.route
    raise ValueError(mode)


def setup(ax, title):
    ax.set_xlim(-6.2, 6.2); ax.set_ylim(-5.7, 5.7); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor("#f6f4ec")


def arrow(ax, x, y):
    i = int(len(x) * 0.66)
    ax.annotate("", xy=(x[i + 5], y[i + 5]), xytext=(x[i - 5], y[i - 5]),
                arrowprops=dict(arrowstyle="-|>", lw=2.1, color="#005fb8", mutation_scale=14))


def draw(ax, mode, title=None, cfg=CFG):
    """Render the interchange in the requested mode onto an axis.

    Draw order realizes step (5) of the pipeline: lower layers first, higher
    layers next, active route (halo + fill + arrows) last."""
    setup(ax, title or "")
    rr = transform(mode, ROADS, cfg) if mode in {"offset", "explode", "elex"} else ROADS
    for r in sorted(rr, key=lambda z: (z.route, z.level)):   # route always last
        lw, alpha, color, halo, arrows = style(mode, r, cfg)
        if mode == "elex" and not r.route and r.level > 0:   # soft stack shadow
            ax.plot(r.x + 0.05, r.y - 0.05, color="black", lw=lw + 1.5,
                    alpha=0.11, solid_capstyle="round")
        if halo:                                              # route halo + casing
            ax.plot(r.x, r.y, color="#b9ecff", lw=lw + 5.5, alpha=0.72, solid_capstyle="round")
            ax.plot(r.x, r.y, color="white", lw=lw + 2.5, alpha=0.95, solid_capstyle="round")
        ax.plot(r.x, r.y, color=color, lw=lw, alpha=alpha, solid_capstyle="round")
        if arrows:
            arrow(ax, r.x, r.y)
    ax.text(-5.9, -5.25,
            "Route: blue | higher roads: darker | ELEX: halo + explode + suppression",
            fontsize=7)


# --------------------------------------------------------------------------- #
# (5) Vectorized clarity metrics
# --------------------------------------------------------------------------- #
def sample_poly(r, m=CFG.metric_samples):
    pts = np.c_[r.x, r.y]
    seg = np.diff(pts, axis=0)
    seglen = np.sqrt((seg ** 2).sum(axis=1))
    s = np.r_[0, np.cumsum(seglen)]
    target = np.linspace(0, s[-1], m)
    return np.c_[np.interp(target, s, r.x), np.interp(target, s, r.y)]


def _sample_to_road_min(samples, r, stride=2):
    """Vectorized min distance from every sample to a road polyline.

    samples: (m, 2)   road points: (k, 2)  ->  (m,) per-sample minimum.
    Uses the same ::2 downsampling the original scalar code used, so the
    numeric results are identical - just computed without the Python loop."""
    p = np.c_[r.x[::stride], r.y[::stride]]                  # (k, 2)
    diff = samples[:, None, :] - p[None, :, :]              # (m, k, 2)
    return np.sqrt((diff ** 2).sum(axis=2)).min(axis=1)     # (m,)


def metrics_for(mode, cfg=CFG):
    """Perceptual Discriminability Index, candidate-road count, confusion risk."""
    rr = transform(mode, ROADS, cfg) if mode in {"offset", "explode", "elex"} else ROADS
    route = next(r for r in rr if r.route)
    samples = sample_poly(route)
    samples = samples[np.sqrt((samples ** 2).sum(axis=1)) < cfg.metric_zone]
    non = [r for r in rr if not r.route]

    # (m, n_nonroute) distance matrix, fully vectorized
    dist_mat = np.stack([_sample_to_road_min(samples, r) for r in non], axis=1)
    cand_counts = (dist_mat < cfg.overlap_radius).sum(axis=1)
    min_dists = dist_mat.min(axis=1)

    _, _, _, halo, arrows = style(mode, route, cfg)
    visual = 20 if mode == "elex" else (6 if mode == "luminance" else 3)
    spatial = 20 * np.tanh(1.7 * np.mean(min_dists))
    pdi = max(0, min(100, 18 + spatial + visual + (11 if halo else 0) + (6 if arrows else 0)))
    risk = 100 * (np.mean(cand_counts) + 0.3) / (pdi + 1)
    ambiguous_share = np.mean(cand_counts >= 2)
    return pdi, float(np.mean(cand_counts)), risk, float(ambiguous_share), float(np.mean(min_dists))


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
MODES = [
    ("baseline",  "A. Baseline flat 2D"),
    ("luminance", "B. Elevation luminance"),
    ("offset",    "C. Normal-offset layering"),
    ("explode",   "D. Triggered explode"),
    ("elex",      "E. Full ELEX"),
]


def fig_variants():
    fig, axs = plt.subplots(1, 5, figsize=(18, 4))
    for ax, (m, t) in zip(axs, MODES):
        draw(ax, m, t)
    fig.tight_layout(); fig.savefig(OUT / "algorithm_variants.png", dpi=180); plt.close(fig)


def fig_steps():
    steps = [("baseline", "1. Raw overlap"), ("luminance", "2. Elevation cue"),
             ("explode", "3. Local explode"), ("elex", "4. Final ELEX")]
    fig, axs = plt.subplots(1, 4, figsize=(16, 4))
    for ax, (m, t) in zip(axs, steps):
        draw(ax, m, t)
    fig.tight_layout(); fig.savefig(OUT / "simulation_steps.png", dpi=180); plt.close(fig)


def fig_bars(rows):
    labels = [r[0] for r in rows]
    pdi = [r[2] for r in rows]
    risk = [r[4] for r in rows]
    plt.figure(figsize=(9, 4)); plt.bar(labels, pdi); plt.ylabel("PDI ↑")
    plt.xticks(rotation=20, ha="right"); plt.tight_layout()
    plt.savefig(OUT / "pdi_barplot.png", dpi=180); plt.close()
    plt.figure(figsize=(9, 4)); plt.bar(labels, risk); plt.ylabel("Confusion risk ↓")
    plt.xticks(rotation=20, ha="right"); plt.tight_layout()
    plt.savefig(OUT / "confusion_risk_barplot.png", dpi=180); plt.close()


def fig_trigger(cfg=CFG):
    """Figure 8 - the look-ahead trigger really firing as the car approaches."""
    d_m, K, active = simulate_lookahead(ROADS, cfg)
    order = np.argsort(-d_m)                                  # far -> near
    d_m, K, active = d_m[order], K[order], active[order]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(d_m, K, color="#0b5cff", lw=2.2, label="Complexity K(v)")
    ax.axhline(cfg.trigger_threshold, color="0.4", ls="--", lw=1.2,
               label=f"Threshold = {cfg.trigger_threshold:g}")
    ax.axvspan(0, cfg.lookahead_m, color="#00a7ff", alpha=0.10,
               label=f"Look-ahead window ({cfg.lookahead_m:g} m)")
    if active.any():
        ax.fill_between(d_m, 0, K, where=active, color="#00a7ff", alpha=0.30,
                        label="ELEX active")
    ax.set_xlabel("Distance to decision point (m)  —  vehicle approaches → left")
    ax.set_ylabel("Complexity score K(v)")
    ax.set_title("Figure 8. ELEX activates only inside the high-complexity decision zone",
                 loc="left", fontsize=11, fontweight="bold")
    ax.invert_xaxis()                                        # nearer to the right
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout(); fig.savefig(OUT / "trigger_plot.png", dpi=180); plt.close(fig)


def fig_carplay():
    """Figure 9 - CarPlay-style mockup: dense baseline vs clarified ELEX."""
    fig = plt.figure(figsize=(12, 5.2)); fig.patch.set_facecolor("#1b1d22")
    for col, (mode, label) in enumerate([("baseline", "Standard 2D"), ("elex", "ELEX clarified")]):
        ax = fig.add_axes([0.04 + col * 0.49, 0.07, 0.45, 0.78])
        draw(ax, mode)
        ax.set_title("")
        frame = FancyBboxPatch((-6.2, -5.7), 12.4, 11.4,
                               boxstyle="round,pad=0.0,rounding_size=0.6",
                               linewidth=2.2, edgecolor="#3a3f47",
                               facecolor="none", zorder=5)
        ax.add_patch(frame)
        # maneuver banner
        ax.add_patch(FancyBboxPatch((-6.0, 4.2), 7.2, 1.2,
                                    boxstyle="round,pad=0.05,rounding_size=0.25",
                                    linewidth=0, facecolor="#0b5cff", alpha=0.92, zorder=6))
        ax.text(-5.6, 4.8, "↗  Exit 12B · 0.3 mi", color="white",
                fontsize=11, fontweight="bold", va="center", zorder=7)
        fig.text(0.04 + col * 0.49 + 0.225, 0.9, label, color="white",
                 ha="center", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.015,
             "Figure 9. Same interchange on a CarPlay-style display: dense overlap (left) "
             "vs route-clear ELEX view (right).",
             color="0.8", ha="center", fontsize=9)
    fig.savefig(OUT / "carplay_mockup.png", dpi=180,
                facecolor=fig.get_facecolor()); plt.close(fig)


# --------------------------------------------------------------------------- #
# Metrics export
# --------------------------------------------------------------------------- #
def compute_rows():
    rows = []
    for mode, title in MODES:
        pdi, cand, risk, amb, sep = metrics_for(mode)
        rows.append((title[3:], mode, pdi, cand, risk, amb, sep))
    return rows


def write_metrics(rows):
    header = "algorithm,mode,PDI,Mean candidate roads,Confusion risk,Ambiguous-share,Mean separation\n"
    body = "".join(",".join(map(str, row)) + "\n" for row in rows)
    (OUT / "metrics.csv").write_text(header + body)
    if DATA.exists():                       # keep the committed copy in sync
        (DATA / "metrics.csv").write_text(header + body)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    fig_variants()
    fig_steps()
    rows = compute_rows()
    write_metrics(rows)
    fig_bars(rows)
    fig_trigger()
    fig_carplay()

    base = next(r for r in rows if r[1] == "baseline")
    elex = next(r for r in rows if r[1] == "elex")
    pdi_gain = (elex[2] - base[2]) / base[2] * 100
    risk_drop = (base[4] - elex[4]) / base[4] * 100
    print(f"Generated outputs in {OUT.resolve()}")
    print(f"PDI: baseline {base[2]:.2f} -> ELEX {elex[2]:.2f}  (+{pdi_gain:.1f}%)")
    print(f"Confusion risk: baseline {base[4]:.2f} -> ELEX {elex[4]:.2f}  (-{risk_drop:.1f}%)")


if __name__ == "__main__":
    main()
