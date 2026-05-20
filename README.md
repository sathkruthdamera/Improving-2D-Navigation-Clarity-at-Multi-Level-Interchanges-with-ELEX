# Improving 2D Navigation Clarity at Multi-Level Interchanges with ELEX

**ELEX** stands for **Elevation-Aware Exploded Layout**. This project proposes, prototypes, and documents a 2D navigation visualization method for complex flyover-heavy interchanges such as Dallas-Fort Worth highway networks.

## Problem

CarPlay-style 2D navigation screens become difficult to interpret at stacked bridges, flyovers, braided ramps, frontage roads, and multi-level exits. Multiple road layers collapse into the same screen space, while red/yellow/green are already reserved for traffic speed. Drivers may miss exits, choose the wrong ramp, add miles, delay deliveries, or increase risk during urgent trips.

## Proposed Solution

ELEX combines multiple visual channels rather than relying on only color or darkness:

- Elevation-aware luminance for relative bridge/flyover height.
- Active-route halo, casing, width, and arrows.
- Non-route opacity reduction to reduce visual clutter.
- Local exploded layout near dense overlapping ramps.
- Complexity-triggered activation so the enhanced view appears only near decision-heavy interchanges.

## Repository Structure

```text
.
├── README.md
├── paper/
│   └── ELEX_Research_Paper.md
├── src/
│   └── elex_simulation.py
├── data/
│   └── metrics.csv
└── artifacts/
    └── artifact_links.md
```

## Algorithms Compared

1. Baseline flat 2D map rendering
2. Elevation luminance encoding
3. Normal-offset layer separation
4. Triggered exploded interchange view
5. Full multi-channel ELEX rendering

## Reproduce Locally

```bash
pip install numpy matplotlib
python src/elex_simulation.py
```

The script generates comparison figures, simulation-stage screenshots, and metrics for the proposed renderer.

## Research Status

This is a prototype and paper-ready research package. The simulation outputs support the design rationale, while the paper proposes a future human-subjects validation using exit accuracy, decision latency, route deviation, glance duration, and NASA-TLX workload.

## Author

Satya Mani Sathkruth Damera
