"""Peak-memory micro-benchmark for the full ship-build pipeline.

Stdlib only. Wraps :func:`spaceship_generator.generator.generate` in
:mod:`tracemalloc` over N iterations so we can budget the *peak* Python
heap allocation of an end-to-end ship build — shape + texture + weapons
+ ``.litematic`` write — alongside the wall-clock budget reported by
``scripts/bench_full_pipeline.py``.

Output is a single mean / p95 / max table (in MB) over the timed
iterations. ``tracemalloc`` only tracks Python-managed allocations, so
this is a *Python-heap* peak rather than full RSS — sufficient to spot
regressions in the shape/texture/weapon paths and stable across OSes
without dragging in ``psutil``.

Usage:
    .venv/Scripts/python scripts/bench_mem.py
    .venv/Scripts/python scripts/bench_mem.py --iterations 20 --seed 42
    .venv/Scripts/python scripts/bench_mem.py --palette stealth_black

The bench writes each iteration's ``.litematic`` into a
:class:`tempfile.TemporaryDirectory` so no files leak onto disk between
runs. ``tracemalloc.reset_peak()`` is called between iterations so each
sample reflects only that iteration's peak.
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import tempfile
import tracemalloc
from pathlib import Path

# Make ``src/`` importable when the script is run directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spaceship_generator.generator import generate  # noqa: E402

# bytes -> megabytes (decimal MB, matching how ops/dashboards usually
# report process memory).
_BYTES_PER_MB = 1024.0 * 1024.0


def _percentile(values: list[float], pct: float) -> float:
    """Return the ``pct`` (0-100) percentile of ``values`` via linear interp.

    Mirrors the helper in ``bench_shape.py`` so output formatting is
    consistent across the bench family without dragging numpy in for
    something this small.
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


def run_iteration(seed: int, palette: str, out_dir: Path) -> float:
    """Run one full ``generate()`` call, returning peak heap MB.

    Assumes ``tracemalloc`` is already started by the caller and that the
    caller resets the peak before invoking us. The output ``.litematic``
    is written into ``out_dir`` (a tmpdir owned by the caller) so the
    bench leaves no files behind.
    """
    filename = f"bench_{seed}.litematic"
    generate(
        seed=seed,
        palette=palette,
        out_dir=out_dir,
        filename=filename,
    )
    _current, peak = tracemalloc.get_traced_memory()
    return peak / _BYTES_PER_MB


def print_table(per_iter_mb: list[float], iterations: int) -> None:
    """Emit a fixed-width mean/p95/max table to stdout.

    Mirrors the layout of ``bench_full_pipeline.py`` so operators can
    eyeball the time and memory benches side-by-side. The unit of work
    is one whole-pipeline iteration, so the table is intentionally
    compact (one row + a TOTAL summary).
    """
    mean_mb = statistics.fmean(per_iter_mb) if per_iter_mb else 0.0
    p95_mb = _percentile(per_iter_mb, 95.0)
    max_mb = max(per_iter_mb) if per_iter_mb else 0.0
    print()
    print(f"{'stage':<10} {'mean_mb':>12} {'p95_mb':>12} {'max_mb':>12}")
    print("-" * 50)
    print(
        f"{'pipeline':<10} {mean_mb:>12.3f} {p95_mb:>12.3f} "
        f"{max_mb:>12.3f}"
    )
    print("-" * 50)
    print(
        f"{'TOTAL':<10} {mean_mb:>12.3f} {p95_mb:>12.3f} "
        f"{max_mb:>12.3f}  (n={iterations})"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--iterations", type=int, default=5,
        help="number of full-pipeline iterations to sample (default: 5)",
    )
    p.add_argument(
        "--seed", type=int, default=0,
        help="base seed; seed_i = seed + i (default: 0)",
    )
    p.add_argument(
        "--palette", type=str, default="sci_fi_industrial",
        help="palette name passed through to generate() (default: sci_fi_industrial)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2

    print(
        f"bench_mem: iterations={args.iterations}  seed={args.seed}  "
        f"palette={args.palette}  py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}"
    )

    tracemalloc.start()
    try:
        with tempfile.TemporaryDirectory(prefix="bench_mem_") as tmp:
            tmp_path = Path(tmp)

            # Warm-up: one untimed iteration so import-time caching and
            # palette-load work do not skew the first sample's peak.
            run_iteration(args.seed, args.palette, tmp_path)

            per_iter_mb: list[float] = []
            for i in range(args.iterations):
                # Reset peak so each sample reflects only this
                # iteration's allocations, not cumulative high-water.
                tracemalloc.reset_peak()
                peak_mb = run_iteration(args.seed + i, args.palette, tmp_path)
                per_iter_mb.append(peak_mb)
    finally:
        tracemalloc.stop()

    print_table(per_iter_mb, args.iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
