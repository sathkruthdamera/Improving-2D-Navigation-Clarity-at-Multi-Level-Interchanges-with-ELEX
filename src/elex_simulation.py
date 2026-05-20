"""
ELEX: Elevation-Aware Exploded Layout prototype for 2D navigation clarity
at multi-level interchanges.

Run:
    pip install numpy matplotlib
    python src/elex_simulation.py

Outputs:
    outputs/algorithm_variants.png
    outputs/simulation_steps.png
    outputs/pdi_barplot.png
    outputs/confusion_risk_barplot.png
    outputs/metrics.csv
"""

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
np.random.seed(7)

@dataclass
class Road:
    name: str
    x: np.ndarray
    y: np.ndarray
    level: int
    route: bool = False


def bezier(p0, p1, p2, p3, n=180):
    t = np.linspace(0, 1, n)
    pts = ((1-t)**3)[:,None]*np.array(p0) + (3*(1-t)**2*t)[:,None]*np.array(p1) + (3*(1-t)*t**2)[:,None]*np.array(p2) + (t**3)[:,None]*np.array(p3)
    return pts[:,0], pts[:,1]


def line(p0, p1, n=180):
    return np.linspace(p0[0], p1[0], n), np.linspace(p0[1], p1[1], n)


def build_roads():
    roads = []
    x,y = line((-6,0), (6,0)); roads.append(Road("east-west mainline", x,y,0))
    x,y = line((0,-5.5),(0,5.5)); roads.append(Road("north-south mainline", x,y,1))
    x,y = line((-6,-0.75),(6,-0.75)); roads.append(Road("frontage road", x,y,-1))
    x,y = line((0.75,-5.5),(0.75,5.5)); roads.append(Road("collector road", x,y,0))
    x,y = bezier((-5,-0.1),(-2,3.5),(2.5,3.4),(5.5,0.15)); roads.append(Road("upper direct connector", x,y,3))
    x,y = bezier((-5,0.25),(-2.4,-3.1),(2.4,-3.25),(5.5,-0.15)); roads.append(Road("lower sweeping connector", x,y,2))
    x,y = bezier((-0.25,-5),(3.6,-2.3),(3.7,1.6),(0.25,5)); roads.append(Road("active route loop ramp", x,y,4, True))
    x,y = bezier((0.15,-5.2),(-3.8,-1.7),(-3.2,2.4),(-0.2,5.2)); roads.append(Road("competing flyover", x,y,2))
    x,y = bezier((-5.2,-3.7),(-3,-0.1),(1.5,1.8),(5.3,3.4)); roads.append(Road("diagonal distributor", x,y,1))
    x,y = bezier((-5.4,3.6),(-2.7,1),(1.7,-1.1),(5.4,-3.7)); roads.append(Road("opposing connector", x,y,2))
    return roads

roads = build_roads()
levels = np.array([r.level for r in roads])
MIN_L, MAX_L = levels.min(), levels.max()


def norm_level(level):
    return (level - MIN_L) / max(1, MAX_L - MIN_L)


def poly_normal(x, y):
    dx, dy = np.gradient(x), np.gradient(y)
    n = np.sqrt(dx*dx + dy*dy) + 1e-9
    return -dy/n, dx/n


def transform(mode, roads):
    out = []
    for r in roads:
        x, y = r.x.copy(), r.y.copy()
        if mode == "offset":
            nx, ny = poly_normal(x, y)
            sep = 0.16 * (r.level - MIN_L)
            x, y = x + sep*nx, y + sep*ny
        elif mode in {"explode", "elex"}:
            d = np.sqrt(x*x + y*y)
            gate = np.clip(1 - d/4.2, 0, 1)
            ux, uy = x/(d+1e-8), y/(d+1e-8)
            amp = 0.72 + 0.06*(r.level - MIN_L)
            if r.route:
                amp *= 0.38 if mode == "elex" else 0.55
            x, y = x + amp*gate*ux, y + amp*gate*uy
            if mode == "elex":
                nx, ny = poly_normal(x, y)
                x, y = x + 0.08*(r.level-MIN_L)*gate*nx, y + 0.08*(r.level-MIN_L)*gate*ny
        out.append(Road(r.name, x, y, r.level, r.route))
    return out


def style(mode, r):
    h = norm_level(r.level)
    if mode == "baseline":
        return (3.2 if r.route else 2.2), 1.0, ("#0b5cff" if r.route else "0.55"), False, False
    if mode == "luminance":
        light = 0.78 - 0.46*h
        return (3.2 if r.route else 2.4), 1.0, ("#0b5cff" if r.route else str(light)), False, False
    if mode in {"offset", "explode"}:
        return (3.2 if r.route else 2.2), 1.0, ("#0b5cff" if r.route else "0.58"), False, False
    if mode == "elex":
        light = 0.83 - 0.45*h
        return (5.4 if r.route else 2.4), (1.0 if r.route else 0.42), ("#00a7ff" if r.route else str(light)), r.route, r.route


def setup(ax, title):
    ax.set_xlim(-6.2, 6.2); ax.set_ylim(-5.7, 5.7); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_facecolor("#f6f4ec")


def arrow(ax, x, y):
    i = int(len(x)*0.66)
    ax.annotate("", xy=(x[i+5], y[i+5]), xytext=(x[i-5], y[i-5]),
                arrowprops=dict(arrowstyle="-|>", lw=2.1, color="#005fb8", mutation_scale=14))


def draw(ax, mode, title):
    setup(ax, title)
    rr = transform(mode, roads) if mode in {"offset", "explode", "elex"} else roads
    for r in sorted(rr, key=lambda z: z.level):
        lw, alpha, color, halo, arrows = style(mode, r)
        if mode == "elex" and not r.route and r.level > 0:
            ax.plot(r.x+0.05, r.y-0.05, color="black", lw=lw+1.5, alpha=0.11, solid_capstyle="round")
        if halo:
            ax.plot(r.x, r.y, color="#b9ecff", lw=lw+5.5, alpha=0.72, solid_capstyle="round")
            ax.plot(r.x, r.y, color="white", lw=lw+2.5, alpha=0.95, solid_capstyle="round")
        ax.plot(r.x, r.y, color=color, lw=lw, alpha=alpha, solid_capstyle="round")
        if arrows:
            arrow(ax, r.x, r.y)
    ax.text(-5.9, -5.25, "Route: blue | higher roads: darker | ELEX: halo + explode + suppression", fontsize=7)


def sample_poly(r, m=90):
    pts = np.c_[r.x, r.y]
    seg = np.diff(pts, axis=0)
    seglen = np.sqrt((seg**2).sum(axis=1))
    s = np.r_[0, np.cumsum(seglen)]
    target = np.linspace(0, s[-1], m)
    return np.c_[np.interp(target, s, r.x), np.interp(target, s, r.y)]


def point_dist(q, r):
    p = np.c_[r.x[::2], r.y[::2]]
    return np.sqrt(((p-q)**2).sum(axis=1)).min()


def metrics_for(mode):
    rr = transform(mode, roads) if mode in {"offset", "explode", "elex"} else roads
    route = [r for r in rr if r.route][0]
    samples = sample_poly(route)
    samples = samples[np.sqrt((samples**2).sum(axis=1)) < 4.2]
    non = [r for r in rr if not r.route]
    cand_counts, min_dists = [], []
    for q in samples:
        ds = np.array([point_dist(q, r) for r in non])
        cand_counts.append((ds < 0.65).sum())
        min_dists.append(ds.min())
    route_lw, route_alpha, route_color, halo, arrows = style(mode, route)
    visual = 20 if mode == "elex" else (6 if mode == "luminance" else 3)
    spatial = 20*np.tanh(1.7*np.mean(min_dists))
    pdi = max(0, min(100, 18 + spatial + visual + (11 if halo else 0) + (6 if arrows else 0)))
    risk = 100*(np.mean(cand_counts)+0.3)/(pdi+1)
    return pdi, np.mean(cand_counts), risk, np.mean(np.array(cand_counts) >= 2), np.mean(min_dists)


def main():
    modes = [("baseline", "A. Baseline flat 2D"), ("luminance", "B. Elevation luminance"), ("offset", "C. Normal-offset layering"), ("explode", "D. Triggered explode"), ("elex", "E. Full ELEX")]

    fig, axs = plt.subplots(1, 5, figsize=(18, 4))
    for ax, (m, t) in zip(axs, modes): draw(ax, m, t)
    fig.tight_layout(); fig.savefig(OUT/"algorithm_variants.png", dpi=180); plt.close(fig)

    fig, axs = plt.subplots(1, 4, figsize=(16, 4))
    for ax, (m, t) in zip(axs, [("baseline","1. Raw overlap"),("luminance","2. Elevation cue"),("explode","3. Local explode"),("elex","4. Final ELEX")]): draw(ax, m, t)
    fig.tight_layout(); fig.savefig(OUT/"simulation_steps.png", dpi=180); plt.close(fig)

    rows = []
    for m,t in modes:
        pdi,cand,risk,amb,sep = metrics_for(m)
        rows.append((t[3:], m, pdi, cand, risk, amb, sep))
    with open(OUT/"metrics.csv", "w") as f:
        f.write("algorithm,mode,PDI,Mean candidate roads,Confusion risk,Ambiguous-share,Mean separation\n")
        for row in rows: f.write(",".join(map(str,row)) + "\n")

    labels = [r[0] for r in rows]
    pdi = [r[2] for r in rows]
    risk = [r[4] for r in rows]
    plt.figure(figsize=(9,4)); plt.bar(labels, pdi); plt.ylabel("PDI ↑"); plt.xticks(rotation=20, ha="right"); plt.tight_layout(); plt.savefig(OUT/"pdi_barplot.png", dpi=180); plt.close()
    plt.figure(figsize=(9,4)); plt.bar(labels, risk); plt.ylabel("Confusion risk ↓"); plt.xticks(rotation=20, ha="right"); plt.tight_layout(); plt.savefig(OUT/"confusion_risk_barplot.png", dpi=180); plt.close()
    print("Generated outputs in", OUT.resolve())

if __name__ == "__main__":
    main()
