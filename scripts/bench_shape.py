"""Per-stage micro-benchmark for the shape pipeline.

Stdlib + numpy only. Re-implements the stage-ordering of
:func:`spaceship_generator.shape.generate_shape` while wrapping each stage
in :func:`time.perf_counter` so we can attribute time to:

    hull -> cockpit -> engines -> wings -> greebles -> assembly

"assembly" covers the post-pass that wires the parts together
(``_enforce_x_symmetry`` -> ``_connect_floaters`` -> ``_enforce_x_symmetry``).

Usage:
    .venv/Scripts/python scripts/bench_shape.py
    .venv/Scripts/python scripts/bench_shape.py --iterations 100 --seed 42
    .venv/Scripts/python scripts/bench_shape.py --palette stealth_black

The ``--palette`` flag is only echoed in the run header — the shape pipeline
does not consume palettes (those are applied during the texture stage). It
is accepted for symmetry with other bench scripts and so future palette-aware
stages have a place to plug in.
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

# Make ``src/`` importable when the script is run directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spaceship_generator.shape import (  # noqa: E402
    ShapeParams,
    _connect_floaters,
    _enforce_x_symmetry,
    _place_cockpit,
    _place_engines,
    _place_greebles,
    _place_hull,
    _place_wings,
)
from spaceship_generator.structure_styles import wing_prob_override  # noqa: E402

# Stage names in canonical pipeline order. Used as the row order for the
# summary table so output is deterministic across runs.
STAGES: tuple[str, ...] = (
    "hull",
    "cockpit",
    "engines",
    "wings",
    "greebles",
    "assembly",
)


def _percentile(values: list[float], pct: float) -> float:
    """Return the ``pct`` (0-100) percentile of ``values`` via linear interp.

    Mirrors ``numpy.percentile`` semantics on a small list without dragging
    in the full numpy machinery for what is just a tiny sort-and-index.
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + frac * (ordered[hi] - ordered[lo])


def run_iteration(seed: int, params: ShapeParams) -> dict[str, float]:
    """Run one full shape pipeline, returning per-stage seconds.

    Mirrors the stage order of :func:`generate_shape` exactly so the totals
    line up with the public API. Each stage is wrapped in ``perf_counter``
    so we measure wall-clock time, including any numpy work.
    """
    rng = np.random.default_rng(seed)
    W, H, L = params.width_max, params.height_max, params.length
    grid = np.zeros((W, H, L), dtype=np.int8)
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    _place_hull(grid, rng, params)
    timings["hull"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    _place_cockpit(grid, rng, params)
    timings["cockpit"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    _place_engines(grid, rng, params)
    timings["engines"] = time.perf_counter() - t0

    # Wings only fire probabilistically — match the gating in generate_shape
    # so timings reflect realistic per-iteration cost. Iterations that skip
    # wings record 0.0 and are still counted in the mean (this is what an
    # operator wants: "what does this stage cost, amortized over a run?").
    effective_wing_prob = wing_prob_override(params.structure_style, params.wing_prob)
    t0 = time.perf_counter()
    if rng.random() < effective_wing_prob:
        _place_wings(grid, rng, params)
    timings["wings"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    _place_greebles(grid, rng, params)
    timings["greebles"] = time.perf_counter() - t0

    # Assembly = symmetry enforce -> connect floaters -> symmetry enforce.
    # We bundle all three because they form a single post-pass with no
    # public sub-hooks; splitting them would just add noise.
    t0 = time.perf_counter()
    _enforce_x_symmetry(grid)
    _connect_floaters(grid)
    _enforce_x_symmetry(grid)
    timings["assembly"] = time.perf_counter() - t0

    return timings


def summarize(per_iter: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """Collapse a list of per-iteration timing dicts into mean/p95/total."""
    summary: dict[str, dict[str, float]] = {}
    for stage in STAGES:
        # Convert seconds -> milliseconds here so the table is operator-friendly.
        values_ms = [row[stage] * 1000.0 for row in per_iter]
        summary[stage] = {
            "mean_ms": statistics.fmean(values_ms) if values_ms else 0.0,
            "p95_ms": _percentile(values_ms, 95.0),
            "total_ms": sum(values_ms),
        }
    # Whole-pipeline total per iteration -> stats over those.
    totals_ms = [sum(row.values()) * 1000.0 for row in per_iter]
    summary["__total__"] = {
        "mean_ms": statistics.fmean(totals_ms) if totals_ms else 0.0,
        "p95_ms": _percentile(totals_ms, 95.0),
        "total_ms": sum(totals_ms),
    }
    return summary


def print_table(summary: dict[str, dict[str, float]], iterations: int) -> None:
    """Emit a fixed-width per-stage table to stdout."""
    print()
    print(f"{'stage':<10} {'mean_ms':>12} {'p95_ms':>12} {'total_ms':>12}")
    print("-" * 50)
    for stage in STAGES:
        s = summary[stage]
        print(
            f"{stage:<10} {s['mean_ms']:>12.3f} {s['p95_ms']:>12.3f} "
            f"{s['total_ms']:>12.3f}"
        )
    print("-" * 50)
    t = summary["__total__"]
    print(
        f"{'TOTAL':<10} {t['mean_ms']:>12.3f} {t['p95_ms']:>12.3f} "
        f"{t['total_ms']:>12.3f}  (n={iterations})"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--iterations", type=int, default=50,
        help="number of full-pipeline iterations to time (default: 50)",
    )
    p.add_argument(
        "--seed", type=int, default=0,
        help="base seed; seed_i = seed + i (default: 0)",
    )
    p.add_argument(
        "--palette", type=str, default="sci_fi_industrial",
        help="palette name (echoed only — shape pipeline is palette-agnostic)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2

    print(
        f"bench_shape: iterations={args.iterations}  seed={args.seed}  "
        f"palette={args.palette}  py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}"
    )

    params = ShapeParams()  # default-sized ship, matches generate_shape default

    # Warm-up: one untimed iteration so JIT-y numpy paths and import-time
    # caching do not skew the first sample.
    run_iteration(args.seed, params)

    per_iter: list[dict[str, float]] = []
    for i in range(args.iterations):
        per_iter.append(run_iteration(args.seed + i, params))

    summary = summarize(per_iter)
    print_table(summary, args.iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
