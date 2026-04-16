"""Command-line interface: ``python -m spaceship_generator`` / ``spaceship-generator``."""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from .generator import GenerationResult, generate
from .palette import list_palettes
from .shape import CockpitStyle, ShapeParams, StructureStyle
from .texture import TextureParams


def _parse_preview_size(value: str) -> tuple[int, int]:
    """Parse a ``WxH`` string into ``(W, H)``.

    Raises :class:`argparse.ArgumentTypeError` on malformed input.
    """
    try:
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise ValueError
        w, h = int(parts[0]), int(parts[1])
        if w <= 0 or h <= 0:
            raise ValueError
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--preview-size must be WxH with positive integers, got {value!r}"
        ) from exc
    return (w, h)


def _parse_seeds(value: str) -> list[int]:
    """Parse a comma-separated list, inclusive ``A-B`` range, or mix of both.

    Examples
    --------
    ``"1,2,3"``     -> ``[1, 2, 3]``
    ``"0-3"``       -> ``[0, 1, 2, 3]``
    ``"1-3,5-7"``   -> ``[1, 2, 3, 5, 6, 7]``
    ``"1,3-4,9"``   -> ``[1, 3, 4, 9]``
    """
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("--seeds must not be empty")

    seeds: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        # Range token: A-B (seeds are non-negative; simple split on '-').
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise argparse.ArgumentTypeError(
                    f"--seeds range must be 'A-B' with integers, got {token!r}"
                )
            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError as exc:
                raise argparse.ArgumentTypeError(
                    f"--seeds range must be integers, got {token!r}"
                ) from exc
            if end < start:
                raise argparse.ArgumentTypeError(
                    f"--seeds range end must be >= start, got {token!r}"
                )
            seeds.extend(range(start, end + 1))
            continue

        # Single integer token.
        try:
            seeds.append(int(token))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"--seeds token must be an integer or 'A-B' range, got {token!r}"
            ) from exc

    if not seeds:
        raise argparse.ArgumentTypeError(f"--seeds produced no values from {value!r}")
    return seeds


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spaceship-generator",
        description="Procedurally generate a Minecraft spaceship and export it as a Litematica (.litematic) schematic.",
    )
    p.add_argument("--seed", type=int, default=None,
                   help="Integer seed (default: random).")
    p.add_argument("--seeds", type=_parse_seeds, default=None,
                   help="Bulk mode: comma-separated seeds ('1,2,3') or inclusive range ('0-9'). "
                        "Mutually exclusive with --seed.")
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
    p.add_argument(
        "--structure-style",
        choices=[s.value for s in StructureStyle],
        default=StructureStyle.FRIGATE.value,
        help="Ship archetype (frigate, fighter, dreadnought, shuttle, hammerhead, carrier).",
    )

    # Texture params
    p.add_argument("--window-period", type=int, default=4,
                   help="Window every N cells along Z.")
    p.add_argument("--stripe-period", type=int, default=8,
                   help="Accent stripe every N cells along Z.")
    p.add_argument("--engine-glow-depth", type=int, default=1,
                   help="Engine-glow core thickness in cells.")
    p.add_argument("--hull-noise-ratio", type=float, default=0.0,
                   help="Fraction of HULL surface cells to darken for a 60-30-10 palette effect "
                        "(0.0 off, 0.3 recommended).")
    p.add_argument("--panel-bands", type=int, default=1,
                   help="Number of HULL_DARK panel-line bands (1..3).")
    p.add_argument("--rivet-period", type=int, default=0,
                   help="HULL_DARK rivet dots every N cells on upper hull (0 disables).")
    p.add_argument("--engine-glow-ring", action="store_true",
                   help="Wrap ENGINE_GLOW cells with a HULL_DARK ring for a layered look.")

    # Output
    p.add_argument("--out", type=Path, default=Path("out"),
                   help="Output directory (default: ./out).")
    p.add_argument("--filename", type=str, default=None,
                   help="Output filename (default: ship_<seed>.litematic). "
                        "Ignored in --seeds bulk mode.")
    p.add_argument("--author", type=str, default="spaceship-generator",
                   help="Schematic author metadata.")
    p.add_argument("--name", type=str, default=None,
                   help="Schematic name metadata (default: 'Ship <seed>').")

    # Preview
    p.add_argument("--preview", action="store_true",
                   help="Also save a PNG preview alongside the .litematic (same stem).")
    p.add_argument("--preview-size", type=_parse_preview_size, default=(800, 800),
                   help="Preview size as WxH (default: 800x800).")

    # Verbosity
    p.add_argument("--verbose", action="store_true",
                   help="Print per-seed timings. Mutually exclusive with --quiet.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress success lines (errors still go to stderr). "
                        "Mutually exclusive with --verbose.")

    return p


def _run_one(
    seed: int,
    *,
    args: argparse.Namespace,
    filename: str | None,
) -> GenerationResult:
    """Run a single generate() call using ``args`` for the shared parameters."""
    shape_params = ShapeParams(
        length=args.length,
        width_max=args.width,
        height_max=args.height,
        engine_count=args.engines,
        wing_prob=args.wing_prob,
        greeble_density=args.greeble_density,
        cockpit_style=CockpitStyle(args.cockpit),
        structure_style=StructureStyle(args.structure_style),
    )
    texture_params = TextureParams(
        window_period_cells=args.window_period,
        accent_stripe_period=args.stripe_period,
        engine_glow_depth=args.engine_glow_depth,
        hull_noise_ratio=args.hull_noise_ratio,
        panel_line_bands=args.panel_bands,
        rivet_period=args.rivet_period,
        engine_glow_ring=args.engine_glow_ring,
    )

    result = generate(
        seed,
        palette=args.palette,
        shape_params=shape_params,
        texture_params=texture_params,
        out_dir=args.out,
        filename=filename,
        author=args.author,
        name=args.name,
        with_preview=bool(args.preview),
        preview_size=args.preview_size,
    )

    if args.preview:
        preview_path = result.litematic_path.with_suffix(".png")
        result.save_preview(preview_path)

    return result


def _print_success(result: GenerationResult, *, elapsed: float | None, args: argparse.Namespace) -> None:
    """Emit the success lines for a single generation, respecting --quiet/--verbose."""
    if args.quiet:
        return
    print(f"Seed: {result.seed}")
    print(f"Palette: {result.palette_name}")
    print(f"Grid shape (W x H x L): {result.shape[0]} x {result.shape[1]} x {result.shape[2]}")
    print(f"Blocks: {result.block_count}")
    print(f"Wrote: {result.litematic_path}")
    if args.preview:
        print(f"Preview: {result.litematic_path.with_suffix('.png')}")
    if args.verbose and elapsed is not None:
        print(f"Elapsed: {elapsed:.3f}s")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose and args.quiet:
        print("Error: --verbose and --quiet are mutually exclusive.", file=sys.stderr)
        return 2
    if args.seed is not None and args.seeds is not None:
        print("Error: --seed and --seeds are mutually exclusive.", file=sys.stderr)
        return 2

    if args.list_palettes:
        names = list_palettes()
        if not names:
            print("(no palettes found)")
            return 0
        for n in names:
            print(n)
        return 0

    # Determine the seed list.
    if args.seeds is not None:
        seeds = list(args.seeds)
        bulk_mode = True
    else:
        seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
        seeds = [seed]
        bulk_mode = False

    successes = 0
    failures = 0

    for i, seed in enumerate(seeds):
        # In bulk mode, force per-seed default filenames to avoid collisions.
        filename = None if bulk_mode else args.filename

        started = time.perf_counter() if args.verbose else None
        try:
            result = _run_one(seed, args=args, filename=filename)
        except FileNotFoundError as exc:
            print(f"Error (seed={seed}): {exc}", file=sys.stderr)
            if not bulk_mode:
                print("Available palettes:", ", ".join(list_palettes()), file=sys.stderr)
            failures += 1
            continue
        except ValueError as exc:
            print(f"Error (seed={seed}): {exc}", file=sys.stderr)
            failures += 1
            continue

        elapsed = (time.perf_counter() - started) if started is not None else None

        # Separate outputs with a blank line in bulk + non-quiet mode.
        if bulk_mode and i > 0 and not args.quiet:
            print()
        _print_success(result, elapsed=elapsed, args=args)
        successes += 1

    # Exit-code semantics:
    #   0 -> all seeds succeeded
    #   1 -> partial failure (some succeeded, some failed)
    #   2 -> no seed succeeded
    if successes == 0:
        return 2
    if failures > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
