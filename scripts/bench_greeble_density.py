"""Per-greeble-density wall-clock micro-benchmark for ``generate()``.

Stdlib + numpy only. Wraps :func:`spaceship_generator.generator.generate`
in :func:`time.perf_counter` over N iterations *for each greeble-density
value* in a user-supplied (or default) sweep so we can surface the cost
slope vs greeble density — a single mean/p95 row per density plus a
TOTAL summary aggregating the per-iter samples across every density.

Mirrors the schema of ``scripts/bench_palette.py`` (per-palette sibling)
so an operator can eyeball both side-by-side. Where ``bench_palette.py``
varies the *palette* axis with `greeble_density` left at the
``generate()`` default, this script pins a single palette and varies the
*greeble-density* axis instead — the missing dimension for the
``shapes-*`` perf work.

Usage:
    .venv/Scripts/python scripts/bench_greeble_density.py
    .venv/Scripts/python scripts/bench_greeble_density.py --iterations 5 --seed 42
    .venv/Scripts/python scripts/bench_greeble_density.py --densities 0.0,0.5,1.0

The bench writes each iteration's ``.litematic`` into a
:class:`tempfile.TemporaryDirectory` so no files leak onto disk between
runs. A small fixed ship footprint (length=16, width=8, height=6) is
used so a sweep across multiple densities completes in seconds rather
than minutes — the *slope* is what matters here, not the absolute
wall-clock at production-sized footprints.
"""

from __future__ import annotations

import argparse
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
from spaceship_generator.shape import ShapeParams  # noqa: E402

# Palette held constant across the sweep so the only varying axis is
# greeble density. Matches ``bench_full_pipeline.py``'s default so the
# two benches stay apples-to-apples on the palette dimension.
DEFAULT_PALETTE = "sci_fi_industrial"

# Small, fixed ship footprint — keeps the multi-density sweep cheap
# enough to run interactively while still exercising every stage of the
# pipeline. The slope vs density is what this bench surfaces, not the
# absolute wall-clock at larger footprints.
SHIP_LENGTH = 16
SHIP_WIDTH = 8
SHIP_HEIGHT = 6


def _shape_params() -> ShapeParams:
    """Build the fixed-footprint :class:`ShapeParams` used by every run.

    Centralised so the warm-up and the timed loop cannot drift apart on
    the dimensions they pass into ``generate()``.
    """
    return ShapeParams(
        length=SHIP_LENGTH,
        width_max=SHIP_WIDTH,
        height_max=SHIP_HEIGHT,
    )


def run_iteration(seed: int, density: float, out_dir: Path) -> float:
    """Run one full ``generate()`` call, returning wall-clock seconds.

    Mirrors ``bench_palette.run_iteration`` so the two benches stay
    apples-to-apples in what they measure (the full ship build, including
    ``.litematic`` write). The ``greeble_density`` argument is passed
    directly to :func:`generate` (which accepts ``[0.0, 1.0]``) rather
    than via :class:`ShapeParams.greeble_density` (which is capped at
    ``0.5``) so the sweep can include the upper-bound 1.0 sample.
    """
    # Filename includes the density (rounded to 3 dp to keep it
    # filesystem-safe) so concurrent iterations cannot collide inside
    # the shared tmpdir.
    density_tag = f"{density:.3f}".replace(".", "p")
    filename = f"bench_greeble_{density_tag}_{seed}.litematic"
    t0 = time.perf_counter()
    generate(
        seed=seed,
        palette=DEFAULT_PALETTE,
        shape_params=_shape_params(),
        out_dir=out_dir,
        filename=filename,
        greeble_density=density,
    )
    return time.perf_counter() - t0


def print_table(
    rows: list[tuple[float, float, float]],
    iterations: int,
) -> None:
    """Emit a fixed-width density × mean/p95 ms table to stdout.

    Layout mirrors ``bench_palette.py`` so an operator can eyeball both
    side-by-side. ``rows`` is a list of ``(density, mean_ms, p95_ms)``
    tuples in the user-supplied density order. The final TOTAL row
    (printed by :func:`print_total`) aggregates the per-iter samples
    across every density so a regression in any single density also
    shows up in the sweep-wide p95.
    """
    # Format each density with three decimal places so the column stays
    # the same width across the sweep ("0.000".."1.000" all fit in 5
    # chars; we widen to the literal "density" header below).
    formatted = [(f"{d:.3f}", m, p) for d, m, p in rows]
    name_width = max((len(label) for label, _m, _p in formatted), default=8)
    name_width = max(name_width, len("density"))

    print()
    print(f"{'density':<{name_width}} {'mean_ms':>12} {'p95_ms':>12}")
    print("-" * (name_width + 2 + 12 + 1 + 12))
    for label, mean_ms, p95_ms in formatted:
        print(f"{label:<{name_width}} {mean_ms:>12.3f} {p95_ms:>12.3f}")
    print("-" * (name_width + 2 + 12 + 1 + 12))


def print_total(
    all_samples_ms: np.ndarray,
    density_count: int,
    iterations: int,
    name_width: int,
) -> None:
    """Emit the TOTAL summary row aggregating every density's samples."""
    if all_samples_ms.size:
        mean_ms = float(all_samples_ms.mean())
        p95_ms = float(np.percentile(all_samples_ms, 95))
    else:
        mean_ms = 0.0
        p95_ms = 0.0
    print(
        f"{'TOTAL':<{name_width}} {mean_ms:>12.3f} {p95_ms:>12.3f}  "
        f"(densities={density_count}, n={iterations})"
    )


def _parse_densities(raw: str) -> list[float]:
    """Parse a comma-separated list of floats in ``[0.0, 1.0]``.

    Raises :class:`argparse.ArgumentTypeError` on any unparseable token
    or any value outside the closed unit interval so argparse surfaces
    a clean ``error:`` line on stderr rather than a stack trace.
    """
    out: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"--densities: cannot parse {token!r} as float"
            ) from exc
        if not 0.0 <= value <= 1.0:
            raise argparse.ArgumentTypeError(
                f"--densities: {value} not in [0.0, 1.0]"
            )
        out.append(value)
    if not out:
        raise argparse.ArgumentTypeError(
            "--densities: at least one density value required"
        )
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--iterations", type=int, default=3,
        help="number of generate() iterations per density (default: 3)",
    )
    p.add_argument(
        "--densities", type=_parse_densities,
        default=_parse_densities("0.0,0.25,0.5,0.75,1.0"),
        help=(
            "comma-separated list of greeble-density floats in [0.0, 1.0] "
            "(default: 0.0,0.25,0.5,0.75,1.0)"
        ),
    )
    p.add_argument(
        "--seed", type=int, default=0,
        help="base seed; seed_i = seed + i (default: 0)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2

    densities: list[float] = args.densities
    if not densities:
        print("no densities supplied", file=sys.stderr)
        return 2

    print(
        f"bench_greeble_density: densities={len(densities)}  "
        f"iterations={args.iterations}  seed={args.seed}  "
        f"py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}"
    )

    rows: list[tuple[float, float, float]] = []
    all_samples: list[float] = []

    with tempfile.TemporaryDirectory(prefix="bench_greeble_density_") as tmp:
        tmp_path = Path(tmp)

        # Warm-up: one untimed iteration on the first density so
        # import-time caching and initial palette-load work do not skew
        # the first sample. Mirrors bench_palette / bench_full_pipeline.
        run_iteration(args.seed, densities[0], tmp_path)

        for density in densities:
            per_iter_ms = np.empty(args.iterations, dtype=np.float64)
            for i in range(args.iterations):
                secs = run_iteration(args.seed + i, density, tmp_path)
                per_iter_ms[i] = secs * 1000.0
            mean_ms = float(per_iter_ms.mean())
            p95_ms = float(np.percentile(per_iter_ms, 95))
            rows.append((density, mean_ms, p95_ms))
            all_samples.extend(per_iter_ms.tolist())

    print_table(rows, args.iterations)
    # Recompute the column width the table just used so the TOTAL row
    # lines up cleanly under it.
    name_width = max((len(f"{d:.3f}") for d, _m, _p in rows), default=8)
    name_width = max(name_width, len("density"))
    print_total(
        np.asarray(all_samples, dtype=np.float64),
        density_count=len(densities),
        iterations=args.iterations,
        name_width=name_width,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
