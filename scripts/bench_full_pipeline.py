"""End-to-end micro-benchmark for the full ship-build pipeline.

Stdlib + numpy only. Wraps :func:`spaceship_generator.generator.generate`
in :func:`time.perf_counter` over N iterations so we can budget the
*entire* ship build — shape + texture + weapons + ``.litematic`` write —
not just the shape stages covered by ``scripts/bench_shape.py``.

Output is a single mean / p95 / total table over the timed iterations.

Usage:
    .venv/Scripts/python scripts/bench_full_pipeline.py
    .venv/Scripts/python scripts/bench_full_pipeline.py --iterations 100 --seed 42
    .venv/Scripts/python scripts/bench_full_pipeline.py --palette stealth_black
    .venv/Scripts/python scripts/bench_full_pipeline.py --csv --iterations 2

The bench writes each iteration's ``.litematic`` into a
:class:`tempfile.TemporaryDirectory` so no files leak onto disk between
runs.
"""

from __future__ import annotations

import argparse
import csv
import platform
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

# Make ``src/`` importable when the script is run directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spaceship_generator.generator import generate  # noqa: E402


def run_iteration(seed: int, palette: str, out_dir: Path) -> float:
    """Run one full ``generate()`` call, returning wall-clock seconds.

    The output ``.litematic`` is written into ``out_dir`` (a tmpdir owned
    by the caller) so the bench leaves no files behind.
    """
    filename = f"bench_{seed}.litematic"
    t0 = time.perf_counter()
    generate(
        seed=seed,
        palette=palette,
        out_dir=out_dir,
        filename=filename,
    )
    return time.perf_counter() - t0


def _aggregate_stats(per_iter_ms: np.ndarray) -> tuple[float, float, float]:
    """Compute the ``(mean_ms, p95_ms, total_ms)`` aggregate.

    Single source of truth for the summary numbers — both
    :func:`print_table` and :func:`print_csv` consume this so the two
    output paths can never drift on the summary numbers.
    """
    mean_ms = float(per_iter_ms.mean()) if per_iter_ms.size else 0.0
    p95_ms = float(np.percentile(per_iter_ms, 95)) if per_iter_ms.size else 0.0
    total_ms = float(per_iter_ms.sum())
    return mean_ms, p95_ms, total_ms


def print_table(per_iter_ms: np.ndarray, iterations: int) -> None:
    """Emit a fixed-width mean/p95/total table to stdout.

    Mirrors the layout of ``bench_shape.py`` so operators can eyeball both
    benches side-by-side. There is only one row here — the whole pipeline
    is the unit of work — so the table is intentionally compact.
    """
    mean_ms, p95_ms, total_ms = _aggregate_stats(per_iter_ms)
    print()
    print(f"{'stage':<10} {'mean_ms':>12} {'p95_ms':>12} {'total_ms':>12}")
    print("-" * 50)
    print(
        f"{'pipeline':<10} {mean_ms:>12.3f} {p95_ms:>12.3f} "
        f"{total_ms:>12.3f}"
    )
    print("-" * 50)
    print(
        f"{'TOTAL':<10} {mean_ms:>12.3f} {p95_ms:>12.3f} "
        f"{total_ms:>12.3f}  (n={iterations})"
    )


def print_csv(per_iter_ms: np.ndarray) -> None:
    """Emit the per-stage summary as CSV to stdout.

    Header row is ``stage,mean_ms,p95_ms,total_ms`` followed by one row
    per stage (``pipeline``, ``TOTAL``). Both rows share the same
    ``_aggregate_stats`` aggregate as the fixed-width formatter so the
    two output paths cannot drift on the summary numbers. Uses the
    stdlib :mod:`csv` module so quoting / escaping (e.g. a future stage
    label containing a comma) is handled correctly without us
    reinventing it.
    """
    mean_ms, p95_ms, total_ms = _aggregate_stats(per_iter_ms)
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["stage", "mean_ms", "p95_ms", "total_ms"])
    writer.writerow(
        ["pipeline", f"{mean_ms:.3f}", f"{p95_ms:.3f}", f"{total_ms:.3f}"]
    )
    writer.writerow(
        ["TOTAL", f"{mean_ms:.3f}", f"{p95_ms:.3f}", f"{total_ms:.3f}"]
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
        help="palette name passed through to generate() (default: sci_fi_industrial)",
    )
    p.add_argument(
        "--csv", action="store_true", default=False,
        help=(
            "Emit CSV (stage,mean_ms,p95_ms,total_ms) instead of fixed-width "
            "table; useful for CI / spreadsheet ingest."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2

    # In CSV mode the run banner goes to stderr so the stdout stream stays
    # a clean CSV document an operator can pipe straight into a spreadsheet
    # / CI parser. In the default fixed-width-table mode it stays on stdout
    # where it's always been (preserves backwards-compatible output for
    # existing callers).
    progress_stream = sys.stderr if args.csv else sys.stdout
    print(
        f"bench_full_pipeline: iterations={args.iterations}  seed={args.seed}  "
        f"palette={args.palette}  py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}",
        file=progress_stream,
    )

    with tempfile.TemporaryDirectory(prefix="bench_full_pipeline_") as tmp:
        tmp_path = Path(tmp)

        # Warm-up: one untimed iteration so import-time caching and any
        # palette-load work do not skew the first sample.
        run_iteration(args.seed, args.palette, tmp_path)

        per_iter_ms = np.empty(args.iterations, dtype=np.float64)
        for i in range(args.iterations):
            secs = run_iteration(args.seed + i, args.palette, tmp_path)
            per_iter_ms[i] = secs * 1000.0

    if args.csv:
        print_csv(per_iter_ms)
    else:
        print_table(per_iter_ms, args.iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
