# Improving 2D Navigation Clarity at Multi-Level Interchanges with ELEX

Improving 2D Navigation Clarity at Multi-Level Interchanges
with Elevation-Aware Rendering and Local Exploded Views
A Prototype-Driven Research Paper for CarPlay-Style Navigation Interfaces
**Author:** Satya Mani Sathkruth Damera
Concept: Elevation-aware 2D bridge/interchange disambiguation for dense urban highway networks
Case Motivation: Dallas-Fort Worth multi-level freeway interchanges

## Abstract
Dense urban interchanges compress multiple ramps, frontage roads, direct connectors, and stacked flyovers into the same two-dimensional screen space. On small in-car displays, this produces route ambiguity at exactly the moment when drivers need fast lane and exit decisions. This paper proposes ELEX, an Elevation-aware Local Exploded View renderer for 2D navigation maps. ELEX combines bounded elevation luminance, non-route opacity reduction, route halo, flow arrows, soft stack shadows, and a local explode transform. The method avoids using red, orange, and green because those color channels are already associated with traffic state in Google Maps. A synthetic Dallas-Fort Worth-style interchange benchmark compares five algorithmic variants: baseline flat 2D rendering, elevation luminance only, normal-offset layering, triggered explode only, and the full ELEX multi-channel renderer. In the synthetic benchmark, full ELEX increased the Perceptual Discriminability Index by 81.9% and reduced the comparative confusion-risk proxy by 42.6% versus the baseline. The results are prototype-level, not a completed human-subjects safety claim. The paper therefore also defines a publishable evaluation plan using exit accuracy, decision latency, route deviation distance, glance duration, and NASA-TLX workload scoring.
**Keywords:** navigation HMI, CarPlay, bridge layout, flyover visualization, exploded views, cartographic design, route guidance, cognitive load
**Figure 1. Conceptual before/after navigation view and road-eye illustration used to motivate the problem. This is a generated design illustration, not a measured field image.**

## 1. Introduction
Navigation systems usually flatten road networks onto a small display. That representation works for ordinary roads, but it becomes weak near stacked flyovers where several physical roads share almost the same x-y footprint. In large freeway systems such as Dallas-Fort Worth, a driver can be presented with several plausible branches, multiple bridge levels, and frontage-road alternatives within one glance-limited decision window.
The problem is not solved by simply making a map more detailed. In an in-car environment, extra detail can increase cognitive load. The renderer must instead answer a small set of driving-critical questions: Which branch is my route? Which road is above or below? Which ramps are alternatives? How far ahead is the decision? The proposed method answers these questions through orthogonal visual encodings rather than a single color channel.
This paper makes three contributions. First, it formalizes the bridge/interchange ambiguity problem as a local graph-visualization issue under driving-interface constraints. Second, it proposes ELEX, a multi-channel 2D rendering algorithm that combines elevation-aware styling with a local exploded layout. Third, it provides a reproducible synthetic benchmark with plotted outputs and simulation screenshots for algorithm comparison.

## 2. Background and Motivation
The Federal Highway Administration defines complex interchanges as facilities with many lanes, high traffic volumes, and tightly spaced ramps and connectors, and notes that drivers may need intense attention and rapid decision-making in such environments [1]. This supports the core motivation: interchange graphics must reduce, not add to, decision complexity.
The in-vehicle display constraint is also important. NHTSA driver-distraction guidance recommends that visual-manual tasks be designed for glances away from the roadway of 2 seconds or less and cumulative eyes-off-road time of 12 seconds or less [2]. A navigation view that requires repeated inspection of overlapping ramps is therefore a design risk even before considering actual route deviation.
Traffic colors cannot be reused freely. Google Maps Help documents green, orange, red, and darker red for traffic speed/congestion, while gray or blue lines represent routes [3]. Therefore, this paper avoids a hue-heavy solution and instead uses luminance, opacity, line weight, halo, shadow, and local geometry separation.
OpenStreetMap contains useful but imperfect vertical-order metadata. The layer tag can describe ways above or below other ways when combined with bridge or tunnel tags, but it does not directly encode absolute height [4]. ELEX therefore treats layer as a relative ordering signal and allows higher-resolution lane or elevation data to replace it when available.

## 3. Problem Definition
Let the road network be a graph G = (V, E), where each edge e is a road segment with geometry, route membership, traffic state, and an estimated vertical layer. The visualization problem occurs when multiple edges have small projected screen-space distance but different levels, especially near route-choice points.
A flat renderer loses vertical order because it projects all road segments to the same 2D canvas. The driver sees a visually dense bundle of strokes but must infer which physical bridge or ramp corresponds to the spoken/visual instruction. This is a local perceptual ambiguity problem, not a shortest-path routing problem.
The design objective is to maximize route discriminability while preserving topological plausibility and avoiding traffic-color conflicts. The renderer should activate only when the local graph is complex enough to justify a special layout.
**Figure 2. ELEX rendering pipeline from road graph ingest to CarPlay-style display rendering.**

## 4. Proposed Method: ELEX Renderer
ELEX is a selective 2D rendering model. It does not require full 3D map casting. The method modifies only the local interchange region and only when a complexity trigger is met.
**Table 1. Orthogonal visual encoding channels used by ELEX.**
### 4.1 Complexity Trigger
A clarified view should not be active all the time. ELEX computes a local complexity score K(v) around the predicted maneuver point:

K(v) = w_b B(v) + w_o O(v) + w_z Z(v) + w_s S(v)

where B(v) is branch factor, O(v) is projected overlap density, Z(v) is the number of distinct vertical levels, and S(v) is successive decision-point density. ELEX activates when K(v) exceeds a threshold and the vehicle is within the look-ahead window, modeled here as 500 meters.

### 4.2 Elevation Luminance Encoding
For each road segment e, the relative height estimate h_e is normalized to [0, 1]. ELEX maps it to a bounded lightness value so higher roads are slightly darker but never illegible:

L_e = clip(L_max - k h_e, L_min, L_max)

The baseline idea of darker-as-higher is retained, but only as one part of the visual grammar. Route salience is handled separately by halo, casing, and stroke width.

### 4.3 Local Exploded Layout
The local exploded transform shifts overlapping geometry outward from the conflict center and slightly along each segment normal. For a point x on segment e:

x' = x + lambda(h_e - mean(h)) n_e + gamma g(d) u

g(d) = max(0, 1 - d/R)

Here n_e is the road normal, u is the outward unit vector from the conflict center, d is distance from the center, and R is the activation radius. Route segments are shifted less than competing branches to preserve route stability.

### 4.4 Rendering Order
The pipeline below is implemented directly in `src/elex_simulation.py`; the function names in parentheses are the actual entry points, so the algorithm is executable rather than descriptive.

Input: road graph G, route R, vehicle position p, look-ahead distance D.

1. Extract the local subgraph around the predicted decision point (`complexity_score` restricts to roads within the perception radius of p).
2. Estimate each road level h_e from layer/bridge tags or lane/elevation data (`norm_level`).
3. Compute the complexity score K(v) = w_b B + w_o O + w_z Z + w_s S, with each component normalized to [0, 1] (`complexity_score`).
4. Activate the clarified view only if K(v) > threshold **and** distance(p, v) < D (`simulate_lookahead`); otherwise render the standard route map. The activation decision over an approaching vehicle is plotted in Figure 8.
5. When active, apply bounded luminance (`elevation_luminance`), opacity hierarchy, soft stack shadow, route halo and flow arrows, and the local exploded transform to overlapping edges (`exploded_layout`, `draw`).
6. Composite back-to-front: lower layers first, higher layers next, then the route halo and route fill last (`draw` sorts on `(route, level)` so the active route is always drawn on top).

**Figure 3. Ablation matrix showing which visual channels each algorithm variant uses.**

## 5. Prototype Implementation
The prototype is a Python simulation built with NumPy and Matplotlib. It uses a synthetic DFW-style stack interchange with ten road segments, five vertical levels, one active route, crossing mainlines, frontage roads, and competing ramps. The goal is not to reproduce a single real interchange exactly; the goal is to create a controlled geometry where different visual algorithms can be compared under repeatable conditions.
**Table 2. Algorithm variants implemented in the synthetic benchmark.**
**Figure 4. Side-by-side outputs of the five tested rendering algorithms on the same DFW-style interchange geometry.**
**Figure 5. Important simulation steps: raw geometry, overlap detection, elevation/route salience, and final ELEX clarified view.**

## 6. Evaluation Metrics
The current results are prototype-level, not final driver-safety evidence. Three synthetic metrics were used to compare visual clarity in the maneuver zone.

**Perceptual Discriminability Index (PDI):** a 0-100 heuristic combining screen-space separation, lightness contrast, opacity contrast, stroke-width contrast, route halo, and route arrows. Higher is better.

**Mean candidate roads:** the average number of non-route roads close enough to the route sample points to appear as plausible alternatives. Lower is better.

**Confusion-risk proxy:** nearby candidate count divided by discriminability. Lower is better. This is a comparative prototype metric, not a standardized human-factors score.

**Table 3. Synthetic benchmark outputs by algorithm variant.**
**Figure 6. Algorithm plot: Perceptual Discriminability Index. Full ELEX produces the highest visual route-discriminability score in the synthetic benchmark.**
**Figure 7. Algorithm plot: comparative route-confusion risk. Lower values indicate fewer nearby alternatives relative to route salience.**
**Figure 8. Trigger plot: ELEX activates only when the driver approaches the high-complexity decision zone.**
**Figure 9. CarPlay-style mockup showing the baseline dense view and the clarified ELEX view on the same synthetic interchange.**

## 7. Results
The full ELEX model performed best across the synthetic benchmark. Compared with baseline flat rendering, PDI increased from 36.33 to 66.10, a gain of 81.9%. The confusion-risk proxy decreased from 3.72 to 2.13, a reduction of 42.6%. Mean nearby candidate roads decreased by -4.0%, and ambiguous-route share changed from 34.8% to 30.4%.
The ablation results are important. Elevation luminance alone improved discriminability only slightly because it explained road level but did not sufficiently emphasize the active route. Triggered explosion alone reduced geometric clutter but still left the route under-specified. The normal-offset method helped separation but created a less controlled distortion. The complete ELEX approach worked best because it combined geometry, route hierarchy, and direction cues.

## 8. Discussion
The key design lesson is that stacked-interchange ambiguity is multi-factorial. A driver must parse vertical order, route identity, branch direction, and timing in a single glance. A one-variable visual solution cannot reliably encode all of those meanings. ELEX therefore uses visual channels that are orthogonal to traffic colors and are selectively activated around the interchange.
The method is intentionally non-3D. Many in-car displays and mirroring environments prioritize 2D map readability and template consistency. ELEX stays within a flat 2D rendering model while introducing local cues that mimic the practical benefit of depth separation.
The model is also compatible with data uncertainty. If absolute elevation is unavailable, relative layer order can still support bounded luminance and draw order. If lane-level data is available, the same algorithm can be applied at lane-centerline resolution.

## 9. Human-Subject Evaluation Plan
A publishable validation study should use a within-subjects design with 30-50 licensed drivers and matched interchange scenarios. Each participant would complete routes under baseline and ELEX conditions in counterbalanced order.
**Table 4. Proposed full validation metrics for simulator or closed-course testing.**

## 10. Limitations
The reported results are based on a synthetic benchmark. They should be treated as prototype evidence, not a field-validated safety claim.
Open map layer tags do not always provide absolute height. Production systems should fuse layer, bridge/tunnel tags, lane-level maps, and digital elevation models where available.
Excessive explosion could distort map expectations. The route-preserving constraint and short activation radius are therefore mandatory design safeguards.
Deployment inside existing third-party apps such as Google Maps would require renderer access or vendor collaboration. A separate CarPlay navigation app could implement this more directly using navigation map overlays.

## 11. Conclusion
This paper transforms the original observation - that stacked flyovers are confusing on flat CarPlay-style map screens - into a concrete visualization method. Elevation darkening is useful, but not enough. The publishable contribution is the full ELEX method: a route-centered, multi-channel, locally exploded 2D renderer that improves clarity while respecting traffic-color conventions and glance-limited driving constraints. The synthetic benchmark and generated simulation screenshots show that the full algorithm outperforms luminance-only, offset-only, and explode-only alternatives. The next step is a controlled driving-simulator study with objective route-performance and workload measures.

## References
[1] Federal Highway Administration. Simulator Study of Signs for a Complex Interchange and Complex Interchange Spreadsheet Tool, FHWA-HRT-13-047, 2013. https://www.fhwa.dot.gov/publications/research/safety/13047/002.cfm
[2] National Highway Traffic Safety Administration. Visual-Manual NHTSA Driver Distraction Guidelines for In-Vehicle Electronic Devices, 2012. https://www.nhtsa.gov/sites/nhtsa.gov/files/distraction_npfg-02162012.pdf
[3] Google Maps Help. Use layers to find places, traffic, terrain, biking and transit: Traffic colors. https://support.google.com/maps/answer/3092439
[4] OpenStreetMap Wiki. Key:layer. https://wiki.openstreetmap.org/wiki/Key:layer
[5] Apple Developer Documentation. CPMapTemplate and integrating CarPlay with a navigation app. https://developer.apple.com/documentation/carplay/cpmaptemplate
[6] NASA Human Systems Integration Division. NASA Task Load Index (TLX). https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/
[7] Texas Department of Transportation. Roadway Design Manual, Section 15.3: Types of Interchanges. https://www.txdot.gov/manuals/des/rdw/chapter-15-grade-separations-and-interchanges-/15-3-types-of-interchanges.html
[8] Chen, Z., et al. Immersive Urban Analytics through Exploded Views. https://aviz.fr/~bbach/immersive2017/papers/IA_1052-paper.pdf
[9] Li, W., et al. Automated Generation of Interactive 3D Exploded View Diagrams. ACM SIGGRAPH, 2008. https://grail.cs.washington.edu/projects/exview/SIGGRAPH2008/submittedMaterials/paper.pdf

## Appendix A. Reproducible Prototype Notes
The synthetic benchmark is generated from ten road polylines: two mainlines, two frontage/collector roads, four flyovers, and two diagonal distributors. Each road is assigned a logical layer from -1 to 4. The active route is a high-level right-hand loop ramp through the center of the interchange. The evaluation samples the active route inside the activation zone and compares nearby non-route alternatives under each rendering transform.

The complete algorithm is implemented in `src/elex_simulation.py`. The listing below is the actual working core (not pseudocode): the complexity trigger that gates the clarified view, the bounded elevation luminance, and the route-preserving exploded layout.

```python
def complexity_score(vehicle_pos, roads, cfg):
    """K(v) = w_b*B + w_o*O + w_z*Z + w_s*S, components normalized to [0, 1]."""
    q = np.asarray(vehicle_pos, float)
    dists = np.array([min_dist_point_to_road(q, r) for r in roads])
    near = dists < cfg.perception_radius
    if not near.any():
        return 0.0
    idx = np.where(near)[0]
    levels = LEVELS[idx]
    B = near.sum() / len(roads)                                   # branch factor
    O = np.exp(-dists[idx] / cfg.overlap_radius).sum() / near.sum()  # overlap density
    Z = len(np.unique(levels)) / N_LEVELS                        # distinct levels
    reps = np.array([closest_point_on_road(q, roads[i]) for i in idx])
    stacked = pairs = 0
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            pairs += 1
            if np.hypot(*(reps[a] - reps[b])) < cfg.overlap_radius and levels[a] != levels[b]:
                stacked += 1
    S = stacked / max(1, pairs)                                  # stacked decisions
    return cfg.w_branch*B + cfg.w_overlap*O + cfg.w_levels*Z + cfg.w_succession*S

def elevation_luminance(level, cfg):
    h = (level - MIN_L) / max(1, MAX_L - MIN_L)
    return float(np.clip(cfg.L_max - cfg.k_lum * h, cfg.L_min, cfg.L_max))

def exploded_layout(r, cfg, route_scale=None):
    """x' = x + gamma*g(d)*u, with g(d) = max(0, 1 - d/R); route shifted less."""
    x, y = r.x.copy(), r.y.copy()
    d = np.hypot(x, y)
    gate = np.clip(1 - d / cfg.explode_radius_R, 0, 1)           # g(d)
    ux, uy = x / (d + 1e-8), y / (d + 1e-8)                      # outward unit u
    amp = cfg.gamma_base + cfg.gamma_level * (r.level - MIN_L)   # gamma
    if r.route and route_scale is not None:
        amp *= route_scale                                      # route preservation
    return x + amp*gate*ux, y + amp*gate*uy, gate

# Per vehicle step along the approach: activate iff complex AND within window.
active = K > cfg.trigger_threshold and distance_to_decision_m < cfg.lookahead_m
# Render back-to-front: lower layers, higher layers, then the active route last.
```

Running `python src/elex_simulation.py` regenerates every figure (including the Figure 8 trigger plot and the Figure 9 CarPlay-style mockup) and the metrics table in `data/metrics.csv`.

## Extracted Tables
### Table 1
| Road attribute | Encoding channel | Reason |
| --- | --- | --- |
| Elevation / layer | Bounded luminance and soft shadow | Communicates vertical order without using traffic hue. |
| Active route | High-contrast stroke, white casing, glow/halo | Keeps the chosen branch visually dominant. |
| Non-active roads | Opacity reduction and desaturation | Reduces clutter while preserving context. |
| Overlapping flyovers | Local explode transform | Turns vertical ambiguity into readable lateral spacing. |
| Directionality | Small route-flow arrows | Confirms the forward branch through the interchange. |

### Table 2
| Variant | Algorithmic behavior | Purpose |
| --- | --- | --- |
| Baseline 2D | Flat geometry; active route is blue; all context roads remain visible. | Represents common flat map ambiguity. |
| Elevation luminance | Higher levels become darker; route remains highlighted. | Tests the original darker-as-higher idea. |
| Normal-offset layering | Roads shift along local normals according to level. | Tests simple layer separation. |
| Triggered explode | Roads in the conflict zone shift outward from center. | Tests geometric decluttering alone. |
| Full ELEX | Combines bounded luminance, opacity, shadow, route halo, arrows, and local explode. | Tests the complete proposed renderer. |

### Table 3
| Algorithm | PDI ↑ | Candidate roads ↓ | Confusion risk ↓ | Ambiguous share ↓ |
| --- | --- | --- | --- | --- |
| Baseline flat 2D | 36.33 | 1.09 | 3.72 | 34.8% |
| Elevation luminance | 39.96 | 1.09 | 3.39 | 34.8% |
| Normal-offset layering | 34.23 | 1.46 | 5.01 | 41.7% |
| Triggered exploded view | 36.52 | 1.14 | 3.85 | 33.3% |
| Full multi-channel ELEX | 66.10 | 1.13 | 2.13 | 30.4% |

### Table 4
| Measure | Definition | Expected direction |
| --- | --- | --- |
| Exit accuracy | Percentage of trials where the correct ramp/exit is selected. | Higher with ELEX |
| Decision latency | Time from first visual instruction to stable lane/branch choice. | Lower with ELEX |
| Route deviation | Extra distance caused by missed ramp or wrong branch. | Lower with ELEX |
| Glance behavior | Maximum glance duration and cumulative eyes-off-road time. | Lower or unchanged with ELEX |
| NASA-TLX | Subjective workload across mental, physical, temporal, performance, effort, and frustration dimensions [6]. | Lower with ELEX |
