"""Command-line interface: ``python -m spaceship_generator`` / ``spaceship-generator``."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .generator import generate
from .palette import list_palettes
from .shape import CockpitStyle, ShapeParams
from .texture import TextureParams


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spaceship-generator",
        description="Procedurally generate a Minecraft spaceship and export it as a Litematica (.litematic) schematic.",
    )
    p.add_argument("--seed", type=int, default=None,
                   help="Integer seed (default: random).")
    p.add_argument("--palette", type=str, default="sci_fi_industrial",
                   help="Palette name to use (default: sci_fi_industrial).")
    p.add_argument("--list-palettes", action="store_true",
                   help="List available palettes and exit.")

    # Shape params
    p.add_argument("--length", type=int, default=40, help="Ship length in blocks (Z axis).")
    p.add_argument("--width", type=int, default=20, help="Ship max width in blocks (X axis).")
    p.add_argument("--height", type=int, default=12, help="Ship max height in blocks (Y axis).")
    p.add_argument("--engines", type=int, default=2, help="Number of engines (0..6).")
    p.add_argument("--wing-prob", type=float, default=0.75,
                   help="Probability of wings (0..1).")
    p.add_argument("--greeble-density", type=float, default=0.05,
                   help="Density of surface greebles (0..0.5).")
    p.add_argument("--cockpit", choices=[c.value for c in CockpitStyle],
                   default=CockpitStyle.BUBBLE.value, help="Cockpit style.")

    # Texture params
    p.add_argument("--window-period", type=int, default=4,
                   help="Window every N cells along Z.")
    p.add_argument("--stripe-period", type=int, default=8,
                   help="Accent stripe every N cells along Z.")
    p.add_argument("--engine-glow-depth", type=int, default=1,
                   help="Engine-glow core thickness in cells.")

    # Output
    p.add_argument("--out", type=Path, default=Path("out"),
                   help="Output directory (default: ./out).")
    p.add_argument("--filename", type=str, default=None,
                   help="Output filename (default: ship_<seed>.litematic).")
    p.add_argument("--author", type=str, default="spaceship-generator",
                   help="Schematic author metadata.")
    p.add_argument("--name", type=str, default=None,
                   help="Schematic name metadata (default: 'Ship <seed>').")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_palettes:
        names = list_palettes()
        if not names:
            print("(no palettes found)")
            return 0
        for n in names:
            print(n)
        return 0

    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)

    try:
        shape_params = ShapeParams(
            length=args.length,
            width_max=args.width,
            height_max=args.height,
            engine_count=args.engines,
            wing_prob=args.wing_prob,
            greeble_density=args.greeble_density,
            cockpit_style=CockpitStyle(args.cockpit),
        )
        texture_params = TextureParams(
            window_period_cells=args.window_period,
            accent_stripe_period=args.stripe_period,
            engine_glow_depth=args.engine_glow_depth,
        )

        result = generate(
            seed,
            palette=args.palette,
            shape_params=shape_params,
            texture_params=texture_params,
            out_dir=args.out,
            filename=args.filename,
            author=args.author,
            name=args.name,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Available palettes:", ", ".join(list_palettes()), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Seed: {result.seed}")
    print(f"Palette: {result.palette_name}")
    print(f"Grid shape (W x H x L): {result.shape[0]} x {result.shape[1]} x {result.shape[2]}")
    print(f"Blocks: {result.block_count}")
    print(f"Wrote: {result.litematic_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
