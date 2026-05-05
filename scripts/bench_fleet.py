"""Fleet-build wall-clock micro-benchmark.

Stdlib + numpy only. Wraps the public Python fleet-builder API
(:func:`spaceship_generator.fleet.generate_fleet` for the plan +
:func:`spaceship_generator.generator.generate` per planned ship) in
:func:`time.perf_counter` over N iterations so we can budget the *fleet*
code path — planning N ships and writing N ``.litematic`` files — as a
single unit of work.

Complements ``scripts/bench_full_pipeline.py`` (one ship, deeper N) and
``scripts/bench_palette.py`` (per-palette one-ship) by surfacing the cost
of the multi-ship fleet path which the CLI exercises via ``--fleet-count``.
We deliberately call the in-process Python API rather than shelling out
to ``python -m spaceship_generator --fleet-count N`` so the timing
reflects only the build cost, not interpreter startup.

Usage:
    .venv/Scripts/python scripts/bench_fleet.py
    .venv/Scripts/python scripts/bench_fleet.py --fleet-count 8 --iterations 5
    .venv/Scripts/python scripts/bench_fleet.py --fleet-count 4 --seed 42
    .venv/Scripts/python scripts/bench_fleet.py --csv --iterations 2

The bench writes each iteration's ``.litematic`` files into a
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

from spaceship_generator.fleet import (  # noqa: E402
    FleetParams,
    generate_fleet,
)
from spaceship_generator.generator import generate  # noqa: E402
from spaceship_generator.shape import ShapeParams  # noqa: E402

_DEFAULT_PALETTE = "sci_fi_industrial"


def _build_one_ship(
    planned,
    *,
    iter_idx: int,
    ship_idx: int,
    out_dir: Path,
) -> None:
    """Build one ship from a fleet plan into ``out_dir``.

    Mirrors the parameter-threading done by ``cli._run_fleet_ship`` —
    copy the planned dims/wing onto a fresh :class:`ShapeParams`, then
    forward the planned hull/engine styles + greeble density to
    :func:`generate`. Filename is namespaced by both the iteration and
    the ship index so nothing collides inside the shared tmpdir across
    iterations.
    """
    shape_params = ShapeParams(
        width_max=int(planned.dims[0]),
        height_max=int(planned.dims[1]),
        length=int(planned.dims[2]),
        wing_style=planned.wing_style,
    )
    filename = f"bench_fleet_iter{iter_idx}_ship{ship_idx}_{planned.seed}.litematic"
    generate(
        seed=int(planned.seed),
        palette=planned.palette,
        shape_params=shape_params,
        out_dir=out_dir,
        filename=filename,
        hull_style=planned.hull_style,
        engine_style=planned.engine_style,
        greeble_density=float(planned.greeble_density),
    )


def run_iteration(
    *,
    iter_idx: int,
    seed: int,
    fleet_count: int,
    palette: str,
    out_dir: Path,
) -> float:
    """Build one full fleet of ``fleet_count`` ships, returning seconds.

    Times planning + every per-ship :func:`generate` call inside a single
    ``perf_counter`` window so the sample reflects the whole fleet code
    path. Each iteration uses ``seed`` (already offset by the caller) so
    repeated samples don't replay byte-identical builds.
    """
    fleet_params = FleetParams(
        count=fleet_count,
        palette=palette,
        size_tier="mixed",
        seed=seed,
    )
    t0 = time.perf_counter()
    planned_ships = generate_fleet(fleet_params)
    for ship_idx, planned in enumerate(planned_ships):
        _build_one_ship(
            planned,
            iter_idx=iter_idx,
            ship_idx=ship_idx,
            out_dir=out_dir,
        )
    return time.perf_counter() - t0


def _aggregate_stats(
    fleet_ms: np.ndarray,
    fleet_count: int,
) -> tuple[float, float, float, float]:
    """Compute the per_ship + fleet (mean_ms, p95_ms) tuple.

    Single source of truth for the summary numbers — both
    :func:`print_table` and :func:`print_csv` consume this so the two
    output paths can never drift on the per-stage stats. Returns
    ``(per_ship_mean, per_ship_p95, fleet_mean, fleet_p95)``.
    """
    if fleet_ms.size:
        per_ship_ms = fleet_ms / float(fleet_count)
        per_ship_mean = float(per_ship_ms.mean())
        per_ship_p95 = float(np.percentile(per_ship_ms, 95))
        fleet_mean = float(fleet_ms.mean())
        fleet_p95 = float(np.percentile(fleet_ms, 95))
    else:
        per_ship_mean = per_ship_p95 = 0.0
        fleet_mean = fleet_p95 = 0.0
    return per_ship_mean, per_ship_p95, fleet_mean, fleet_p95


def print_table(
    fleet_ms: np.ndarray,
    fleet_count: int,
    iterations: int,
) -> None:
    """Emit a fixed-width per-ship + total-fleet ms table to stdout.

    Layout mirrors ``bench_full_pipeline.py`` so an operator can eyeball
    both benches side-by-side. ``fleet_ms`` is one wall-clock sample per
    iteration covering the whole fleet build; per-ship stats are derived
    by dividing each sample by ``fleet_count`` (so the per-ship row is
    the *average* per-ship cost across the fleet, not a per-ship
    distribution — that would require timing each ``generate()`` call
    individually and is intentionally out of scope for this bench).
    """
    per_ship_mean, per_ship_p95, fleet_mean, fleet_p95 = _aggregate_stats(
        fleet_ms, fleet_count,
    )

    print()
    print(f"{'stage':<10} {'mean_ms':>12} {'p95_ms':>12}")
    print("-" * 38)
    print(f"{'per_ship':<10} {per_ship_mean:>12.3f} {per_ship_p95:>12.3f}")
    print(f"{'fleet':<10} {fleet_mean:>12.3f} {fleet_p95:>12.3f}")
    print("-" * 38)
    print(
        f"{'TOTAL':<10} {fleet_mean:>12.3f} {fleet_p95:>12.3f}  "
        f"(ships={fleet_count}, n={iterations})"
    )


def print_csv(
    fleet_ms: np.ndarray,
    fleet_count: int,
) -> None:
    """Emit the per-stage summary as CSV to stdout.

    Header row is ``stage,mean_ms,p95_ms`` followed by one row per stage
    (``per_ship``, ``fleet``, ``TOTAL``). The TOTAL row mirrors the
    fixed-width formatter's TOTAL line which uses the *fleet* mean/p95
    (the per-ship row is the divided-by-N average) so the two output
    paths cannot drift on the summary numbers — both consume the same
    ``_aggregate_stats`` aggregate. Uses the stdlib :mod:`csv` module so
    quoting / escaping (e.g. a future stage label containing a comma) is
    handled correctly without us reinventing it.
    """
    per_ship_mean, per_ship_p95, fleet_mean, fleet_p95 = _aggregate_stats(
        fleet_ms, fleet_count,
    )
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["stage", "mean_ms", "p95_ms"])
    writer.writerow(["per_ship", f"{per_ship_mean:.3f}", f"{per_ship_p95:.3f}"])
    writer.writerow(["fleet", f"{fleet_mean:.3f}", f"{fleet_p95:.3f}"])
    writer.writerow(["TOTAL", f"{fleet_mean:.3f}", f"{fleet_p95:.3f}"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--fleet-count", type=int, default=4,
        help="number of ships per fleet build (default: 4)",
    )
    p.add_argument(
        "--iterations", type=int, default=3,
        help="number of fleet-build iterations to time (default: 3)",
    )
    p.add_argument(
        "--seed", type=int, default=0,
        help="base seed; fleet_seed_i = seed + i (default: 0)",
    )
    p.add_argument(
        "--palette", type=str, default=_DEFAULT_PALETTE,
        help=(
            "palette name passed through to every ship in the fleet "
            f"(default: {_DEFAULT_PALETTE})"
        ),
    )
    p.add_argument(
        "--csv", action="store_true", default=False,
        help=(
            "Emit CSV (stage,mean_ms,p95_ms) instead of fixed-width "
            "table; useful for CI / spreadsheet ingest."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2
    if args.fleet_count < 1:
        print("--fleet-count must be >= 1", file=sys.stderr)
        return 2

    # In CSV mode the run banner goes to stderr so the stdout stream stays
    # a clean CSV document an operator can pipe straight into a spreadsheet
    # / CI parser. In the default fixed-width-table mode it stays on stdout
    # where it's always been (preserves backwards-compatible output for
    # existing callers).
    progress_stream = sys.stderr if args.csv else sys.stdout
    print(
        f"bench_fleet: fleet_count={args.fleet_count}  "
        f"iterations={args.iterations}  seed={args.seed}  "
        f"palette={args.palette}  py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}",
        file=progress_stream,
    )

    with tempfile.TemporaryDirectory(prefix="bench_fleet_") as tmp:
        tmp_path = Path(tmp)

        # Warm-up: one untimed iteration so import-time caching and any
        # palette-load work do not skew the first sample. Mirrors
        # bench_full_pipeline / bench_palette / bench_mem.
        run_iteration(
            iter_idx=-1,
            seed=args.seed,
            fleet_count=args.fleet_count,
            palette=args.palette,
            out_dir=tmp_path,
        )

        fleet_ms = np.empty(args.iterations, dtype=np.float64)
        for i in range(args.iterations):
            secs = run_iteration(
                iter_idx=i,
                seed=args.seed + i,
                fleet_count=args.fleet_count,
                palette=args.palette,
                out_dir=tmp_path,
            )
            fleet_ms[i] = secs * 1000.0

    if args.csv:
        print_csv(fleet_ms, args.fleet_count)
    else:
        print_table(fleet_ms, args.fleet_count, args.iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
