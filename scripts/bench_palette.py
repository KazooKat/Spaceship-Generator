"""Per-palette wall-clock micro-benchmark for ``generate()``.

Stdlib + numpy only. Wraps :func:`spaceship_generator.generator.generate`
in :func:`time.perf_counter` over N iterations *for each shipped palette*
so we can surface per-palette cost variance — a single mean/p95 row per
palette plus a TOTAL summary across the whole catalog.

Complements ``scripts/bench_full_pipeline.py`` (one palette, deeper N) by
spotting palette-driven slow paths early — e.g. a future palette whose
texture pass is materially heavier than the rest of the catalog.

Usage:
    .venv/Scripts/python scripts/bench_palette.py
    .venv/Scripts/python scripts/bench_palette.py --iterations 5 --seed 42
    .venv/Scripts/python scripts/bench_palette.py --limit 4 --iterations 3

Palettes are discovered dynamically via
:func:`spaceship_generator.palette.list_palettes` (the same enumeration
``tests/test_palette_lint.py`` and ``tests/test_properties.py`` use), so
adding a new YAML under ``palettes/`` automatically widens this bench's
matrix without any code changes here.

The bench writes each iteration's ``.litematic`` into a
:class:`tempfile.TemporaryDirectory` so no files leak onto disk between
runs.
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
from spaceship_generator.palette import list_palettes  # noqa: E402


def run_iteration(seed: int, palette: str, out_dir: Path) -> float:
    """Run one full ``generate()`` call, returning wall-clock seconds.

    Mirrors ``bench_full_pipeline.run_iteration`` so the two benches stay
    apples-to-apples in what they measure (the full ship build, including
    ``.litematic`` write).
    """
    filename = f"bench_{palette}_{seed}.litematic"
    t0 = time.perf_counter()
    generate(
        seed=seed,
        palette=palette,
        out_dir=out_dir,
        filename=filename,
    )
    return time.perf_counter() - t0


def print_table(
    rows: list[tuple[str, float, float]],
    iterations: int,
) -> None:
    """Emit a fixed-width palette × mean/p95 ms table to stdout.

    Layout mirrors ``bench_shape.py`` / ``bench_full_pipeline.py`` so an
    operator can eyeball all three side-by-side. ``rows`` is a list of
    ``(palette_name, mean_ms, p95_ms)`` tuples in palette-name order. The
    final TOTAL row aggregates the per-iter samples across every palette
    so a regression in any single palette shows up in the catalog-wide
    p95 as well.
    """
    # Match column width to the longest palette name so the table stays
    # readable even when a future palette pushes past the 16-char default.
    name_width = max((len(name) for name, _m, _p in rows), default=8)
    name_width = max(name_width, len("palette"))

    print()
    print(f"{'palette':<{name_width}} {'mean_ms':>12} {'p95_ms':>12}")
    print("-" * (name_width + 2 + 12 + 1 + 12))
    for name, mean_ms, p95_ms in rows:
        print(f"{name:<{name_width}} {mean_ms:>12.3f} {p95_ms:>12.3f}")
    print("-" * (name_width + 2 + 12 + 1 + 12))


def print_total(
    all_samples_ms: np.ndarray,
    palette_count: int,
    iterations: int,
    name_width: int,
) -> None:
    """Emit the TOTAL summary row aggregating every palette's samples."""
    if all_samples_ms.size:
        mean_ms = float(all_samples_ms.mean())
        p95_ms = float(np.percentile(all_samples_ms, 95))
    else:
        mean_ms = 0.0
        p95_ms = 0.0
    print(
        f"{'TOTAL':<{name_width}} {mean_ms:>12.3f} {p95_ms:>12.3f}  "
        f"(palettes={palette_count}, n={iterations})"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--iterations", type=int, default=3,
        help="number of generate() iterations per palette (default: 3)",
    )
    p.add_argument(
        "--limit", type=int, default=0,
        help=(
            "max number of palettes to bench (default: 0 = all). Useful for "
            "quick smoke runs and the bench_smoke test."
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
    if args.limit < 0:
        print("--limit must be >= 0", file=sys.stderr)
        return 2

    palettes = list_palettes()
    # ``list_palettes()`` with default args returns ``list[str]``; assert
    # that contract so a future signature change fails loud here rather
    # than mis-typing the loop below.
    assert isinstance(palettes, list) and all(
        isinstance(name, str) for name in palettes
    ), "list_palettes() must return list[str] when called without flags"

    if args.limit > 0:
        palettes = palettes[: args.limit]

    if not palettes:
        print("no palettes discovered", file=sys.stderr)
        return 2

    print(
        f"bench_palette: palettes={len(palettes)}  iterations={args.iterations}  "
        f"seed={args.seed}  py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}"
    )

    rows: list[tuple[str, float, float]] = []
    all_samples: list[float] = []

    with tempfile.TemporaryDirectory(prefix="bench_palette_") as tmp:
        tmp_path = Path(tmp)

        # Warm-up: one untimed iteration on the first palette so
        # import-time caching and initial palette-load work do not skew
        # the first sample. Mirrors bench_full_pipeline / bench_mem.
        run_iteration(args.seed, palettes[0], tmp_path)

        for palette in palettes:
            per_iter_ms = np.empty(args.iterations, dtype=np.float64)
            for i in range(args.iterations):
                secs = run_iteration(args.seed + i, palette, tmp_path)
                per_iter_ms[i] = secs * 1000.0
            mean_ms = float(per_iter_ms.mean())
            p95_ms = float(np.percentile(per_iter_ms, 95))
            rows.append((palette, mean_ms, p95_ms))
            all_samples.extend(per_iter_ms.tolist())

    print_table(rows, args.iterations)
    name_width = max((len(name) for name, _m, _p in rows), default=8)
    name_width = max(name_width, len("palette"))
    print_total(
        np.asarray(all_samples, dtype=np.float64),
        palette_count=len(palettes),
        iterations=args.iterations,
        name_width=name_width,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
