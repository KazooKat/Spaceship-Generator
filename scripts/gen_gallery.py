"""Render a palette x seed gallery of spaceship previews.

Bypasses the .litematic export path entirely — goes straight from shape +
texture to a matplotlib PNG. One render per (palette, seed) cell.

Usage
-----
    .venv/Scripts/python scripts/gen_gallery.py --out docs/gallery
    .venv/Scripts/python scripts/gen_gallery.py --out docs/gallery \\
        --palettes sci_fi_industrial,sleek_modern \\
        --seeds 1,42

Defaults: 6 hand-picked palettes x 4 seeds = 24 renders at ~800 px wide.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spaceship_generator.palette import load_palette  # noqa: E402
from spaceship_generator.preview import render_preview  # noqa: E402
from spaceship_generator.shape import ShapeParams, generate_shape  # noqa: E402
from spaceship_generator.texture import TextureParams, assign_roles  # noqa: E402

DEFAULT_PALETTES: tuple[str, ...] = (
    "sci_fi_industrial",
    "sleek_modern",
    "neon_arcade",
    "alien_bio",
    "amethyst_crystal",
    "cyberpunk_neon",
)
DEFAULT_SEEDS: tuple[int, ...] = (1, 42, 1234, 99999)
PREVIEW_SIZE: tuple[int, int] = (800, 800)


def _parse_csv_str(value: str) -> list[str]:
    items = [x.strip() for x in value.split(",") if x.strip()]
    if not items:
        raise argparse.ArgumentTypeError(f"expected comma-separated list, got {value!r}")
    return items


def _parse_csv_int(value: str) -> list[int]:
    items: list[int] = []
    for tok in value.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            items.append(int(tok))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"seed must be an integer, got {tok!r}"
            ) from exc
    if not items:
        raise argparse.ArgumentTypeError(f"expected comma-separated ints, got {value!r}")
    return items


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="gen_gallery",
        description="Render a palette x seed gallery of spaceship previews.",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for the PNG files.",
    )
    p.add_argument(
        "--palettes",
        type=_parse_csv_str,
        default=list(DEFAULT_PALETTES),
        help="Comma-separated palette names (default: 6 hand-picked).",
    )
    p.add_argument(
        "--seeds",
        type=_parse_csv_int,
        default=list(DEFAULT_SEEDS),
        help="Comma-separated integer seeds (default: 1,42,1234,99999).",
    )
    return p.parse_args(argv)


def _render_cell(palette_name: str, seed: int) -> bytes:
    """Generate a ship + preview PNG for a single (palette, seed) cell."""
    pal = load_palette(palette_name)
    shape_params = ShapeParams()
    texture_params = TextureParams()
    shape_grid = generate_shape(seed, shape_params)
    role_grid = assign_roles(shape_grid, texture_params)
    return render_preview(role_grid, pal, size=PREVIEW_SIZE)


def _fmt_size(n_bytes: int) -> str:
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    return f"{n_bytes / (1024 * 1024):.2f} MB"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    palettes: list[str] = args.palettes
    seeds: list[int] = args.seeds

    rows: list[tuple[str, int, Path, int, float]] = []
    total_started = time.perf_counter()

    for palette_name in palettes:
        for seed in seeds:
            cell_started = time.perf_counter()
            try:
                png_bytes = _render_cell(palette_name, seed)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"ERROR rendering {palette_name}/{seed}: {exc}",
                    file=sys.stderr,
                )
                continue
            cell_elapsed = time.perf_counter() - cell_started

            out_path = out_dir / f"{palette_name}_{seed}.png"
            out_path.write_bytes(png_bytes)
            rows.append((palette_name, seed, out_path, len(png_bytes), cell_elapsed))
            print(
                f"  {palette_name:<22} seed={seed:<6} "
                f"{_fmt_size(len(png_bytes)):>10}  {cell_elapsed:.2f}s"
            )

    total_elapsed = time.perf_counter() - total_started

    # Summary table.
    print()
    print("=== GALLERY SUMMARY ===")
    print(
        f"{'palette':<22} {'seed':>8} {'size':>10} {'time_s':>8}   file"
    )
    print("-" * 88)
    total_bytes = 0
    for palette_name, seed, path, nbytes, elapsed in rows:
        total_bytes += nbytes
        print(
            f"{palette_name:<22} {seed:>8} {_fmt_size(nbytes):>10} "
            f"{elapsed:>8.2f}   {path.as_posix()}"
        )
    print("-" * 88)
    print(
        f"TOTAL  palettes={len(palettes)}  seeds={len(seeds)}  "
        f"renders={len(rows)}  size={_fmt_size(total_bytes)}  "
        f"wall={total_elapsed:.2f}s"
    )
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
