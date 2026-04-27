"""Command-line interface: ``python -m spaceship_generator`` / ``spaceship-generator``."""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from pathlib import Path

from .engine_styles import EngineStyle
from .generator import GenerationResult, generate
from .greeble_styles import GreebleType
from .palette import list_palettes
from .shape import CockpitStyle, ShapeParams, StructureStyle
from .structure_styles import HullStyle
from .texture import TextureParams
from .wing_styles import WingStyle

# Optional modules — the CLI keeps working when they're missing so a partial
# rollout (weapons landed but fleet didn't yet, or vice versa) still ships a
# usable generator. Every call-site guards on the corresponding flag.
try:
    from . import weapon_styles as _weapon_styles  # type: ignore
except ImportError as _exc:  # pragma: no cover - exercised via monkeypatch
    _weapon_styles = None
    _weapon_styles_error: str | None = str(_exc)
else:
    _weapon_styles_error = None

try:
    from . import fleet as _fleet  # type: ignore
except ImportError as _exc:  # pragma: no cover - exercised via monkeypatch
    _fleet = None
    _fleet_error: str | None = str(_exc)
else:
    _fleet_error = None

try:
    from . import presets as _presets  # type: ignore
except ImportError as _exc:  # pragma: no cover - exercised via monkeypatch
    _presets = None
    _presets_error: str | None = str(_exc)
else:
    _presets_error = None


def _parse_ship_size(value: str) -> tuple[int, int, int]:
    """Parse a ``WxHxL`` string into ``(W, H, L)``.

    Raises :class:`argparse.ArgumentTypeError` on malformed input or
    dimensions that violate the :class:`ShapeParams` minimums
    (W>=4, H>=4, L>=8).
    """
    parts = value.lower().split("x")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"--ship-size must be WxHxL with positive integers, got {value!r}"
        )
    try:
        w, h, length = (int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--ship-size must be WxHxL with positive integers, got {value!r}"
        ) from exc
    if w < 4 or h < 4 or length < 8:
        raise argparse.ArgumentTypeError(
            f"--ship-size: W>=4, H>=4, L>=8 required; got W={w} H={h} L={length}"
        )
    return (w, h, length)


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


def _parse_nonneg_int(value: str) -> int:
    """Parse a non-negative integer (``>= 0``)."""
    try:
        i = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"must be a non-negative integer, got {value!r}"
        ) from exc
    if i < 0:
        raise argparse.ArgumentTypeError(
            f"must be >= 0, got {i}"
        )
    return i


def _parse_pos_int(value: str) -> int:
    """Parse a positive integer (``>= 1``)."""
    try:
        i = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"must be a positive integer, got {value!r}"
        ) from exc
    if i < 1:
        raise argparse.ArgumentTypeError(
            f"must be >= 1, got {i}"
        )
    return i


def _parse_weapon_types(value: str) -> list[str]:
    """Parse a comma-separated list of weapon-type tokens.

    Validation against :class:`WeaponType` happens later (only if the
    ``weapon_styles`` module is importable), so this helper just normalizes
    whitespace and drops empty tokens.
    """
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("--weapon-types must not be empty")
    tokens = [t.strip() for t in value.split(",")]
    tokens = [t for t in tokens if t]
    if not tokens:
        raise argparse.ArgumentTypeError(
            f"--weapon-types produced no values from {value!r}"
        )
    return tokens


def _parse_unit_float(value: str) -> float:
    """Parse a float in the closed interval ``[0.0, 1.0]``.

    Used by ``--greeble-density`` so that out-of-range values are rejected
    at argparse time (exit code 2) rather than surfacing later as a
    :class:`ValueError` inside the generator.
    """
    try:
        f = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"must be a float in [0.0, 1.0], got {value!r}"
        ) from exc
    if not 0.0 <= f <= 1.0:
        raise argparse.ArgumentTypeError(
            f"must be in [0.0, 1.0], got {f}"
        )
    return f


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
    p.add_argument(
        "--seed-phrase",
        type=str,
        default=None,
        metavar="TEXT",
        help=(
            "Hash TEXT into a deterministic integer seed (SHA-256 mod 2^31-1). "
            "Mutually exclusive with --seed and --seeds."
        ),
    )
    p.add_argument("--palette", type=str, default="sci_fi_industrial",
                   help="Palette name to use (default: sci_fi_industrial). "
                        "Use 'random' to pick a random palette.")
    p.add_argument("--list-palettes", action="store_true",
                   help="List available palettes and exit.")
    p.add_argument("--palette-info", metavar="NAME",
                   help="Print role -> block ID and hex preview color for NAME and exit. "
                        "Use --list-palettes to see available palette names.")
    p.add_argument("--list-styles", action="store_true",
                   help="List available hull/engine/wing styles and exit.")
    p.add_argument("--list-shape-styles", action="store_true",
                   help="List HullStyle / EngineStyle / WingStyle members "
                        "(grouped, one per line) and exit. Narrower than "
                        "--list-styles, which also includes cockpit and "
                        "weapon types.")
    # ``--preset``/``--list-presets`` are only active when the optional
    # ``presets`` module is importable. When it's absent we still register
    # the flags (so ``--help`` documents them) but restrict the choices to
    # an empty list — argparse then rejects any value at parse time and
    # callers get a clear error instead of a mysterious AttributeError.
    _preset_choices = _presets.list_presets() if _presets is not None else []
    p.add_argument(
        "--preset",
        choices=_preset_choices or None,
        default=None,
        help="Named ship archetype preset "
             "(corvette, dropship, science_vessel, gunship, "
             "freighter_heavy, interceptor). Individual flags "
             "(--hull-style, --engine-style, --wing-style, "
             "--cockpit-style, --greeble-density, --weapon-count, "
             "--weapon-types) override preset values when provided.",
    )
    p.add_argument("--list-presets", action="store_true",
                   help="List available preset names and exit.")
    p.add_argument("--list-weapon-types", action="store_true",
                   help="Print all available weapon types and exit.")

    # Shape params
    p.add_argument("--length", type=int, default=40, help="Ship length in blocks (Z axis).")
    p.add_argument("--width", type=int, default=20, help="Ship max width in blocks (X axis).")
    p.add_argument("--height", type=int, default=12, help="Ship max height in blocks (Y axis).")
    p.add_argument("--engines", type=int, default=2, help="Number of engines (0..6).")
    p.add_argument("--wing-prob", type=float, default=0.75,
                   help="Probability of wings (0..1).")
    # ``--greeble-density`` accepts values in [0.0, 1.0]. When omitted the
    # default is ``None`` so we can tell "user didn't touch this" apart from
    # "user typed 0.0". ``None`` preserves legacy behavior: the in-shape
    # scatter keeps its historical ``ShapeParams`` default (0.05) and the
    # post-build generator-level scatter stays off.
    p.add_argument("--greeble-density", type=_parse_unit_float, default=None,
                   help="Density of surface greebles in [0.0, 1.0]. "
                        "When omitted, legacy defaults apply. "
                        "Shortcut: --no-greebles is equivalent to "
                        "--greeble-density 0 (mutually exclusive).")
    p.add_argument("--no-greebles", action="store_true",
                   help="Shortcut for --greeble-density 0 (disables greeble "
                        "scatter entirely). Mutually exclusive with "
                        "--greeble-density.")
    p.add_argument(
        "--greeble-style",
        metavar="TYPE",
        choices=[t.value for t in GreebleType],
        help=(
            "Restrict greeble scatter to one type: "
            + ", ".join(t.value for t in GreebleType)
            + ". Default: all types."
        ),
    )
    p.add_argument("--cockpit", choices=[c.value for c in CockpitStyle],
                   default=CockpitStyle.BUBBLE.value, help="Cockpit style.")
    p.add_argument(
        "--cockpit-style",
        choices=[c.value for c in CockpitStyle],
        default=None,
        help="Cockpit archetype "
             "(bubble, pointed, integrated, canopy_dome, wrap_bridge, "
             "offset_turret). When omitted, the legacy auto-selection "
             "(driven by --cockpit) is used.",
    )
    p.add_argument(
        "--structure-style",
        choices=[s.value for s in StructureStyle],
        default=StructureStyle.FRIGATE.value,
        help="Ship archetype (frigate, fighter, dreadnought, shuttle, hammerhead, carrier).",
    )
    p.add_argument(
        "--wing-style",
        choices=[w.value for w in WingStyle],
        default=WingStyle.STRAIGHT.value,
        help="Wing silhouette (straight, swept, delta, tapered, gull, split).",
    )
    p.add_argument(
        "--hull-style",
        choices=[h.value for h in HullStyle],
        default=None,
        help="Hull silhouette archetype "
             "(arrow, saucer, whale, dagger, blocky_freighter). "
             "When omitted, the legacy generator hull is used.",
    )
    p.add_argument(
        "--hull-style-front",
        choices=[h.value for h in HullStyle],
        default=None,
        help="Hull silhouette archetype to blend toward the nose "
             "(z = L - 1). Pair with --hull-style-rear to enable a "
             "Z-axis blend between two profiles (cosine-weighted "
             "crossover centred at z = L/2). Both flags must be "
             "supplied for the blend to engage; if either is omitted "
             "the legacy single-style hull selection is used. When "
             "both are set, the blend overrides --hull-style.",
    )
    p.add_argument(
        "--hull-style-rear",
        choices=[h.value for h in HullStyle],
        default=None,
        help="Hull silhouette archetype to blend toward the engine "
             "end (z = 0). Pair with --hull-style-front to enable a "
             "Z-axis blend between two profiles. See --hull-style-front "
             "for crossover details.",
    )
    p.add_argument(
        "--engine-style",
        choices=[e.value for e in EngineStyle],
        default=None,
        help="Engine archetype "
             "(single_core, twin_nacelle, quad_cluster, ring, ion_array). "
             "When omitted, the legacy engine placer is used.",
    )
    p.add_argument(
        "--hull-noise",
        type=_parse_unit_float,
        default=0.0,
        metavar="AMPLITUDE",
        help="Procedural-noise hull distortion amplitude in [0.0, 1.0] "
             "(default 0.0 = off). Higher values displace hull-membrane "
             "cells via a deterministic 3D hash-noise field for an "
             "asteroid-pitted / battle-damaged look. Clamped to ±2 cells "
             "so the silhouette stays legible. Deterministic per seed.",
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

    # Weapons (optional — requires weapon_styles module).
    p.add_argument("--weapon-count", type=_parse_nonneg_int, default=0,
                   help="Number of weapons to scatter onto the ship "
                        "(0 disables, default 0). Requires the weapon_styles "
                        "module.")
    p.add_argument("--weapon-types", type=_parse_weapon_types, default=None,
                   help="Comma-separated list of weapon types to restrict "
                        "placement to (e.g. 'turret_large,missile_pod'). "
                        "Defaults to all types.")

    # Repeat mode — generate N ships with consecutive seeds.
    p.add_argument("--repeat", type=_parse_pos_int, default=1,
                   help="Generate N ships with consecutive seeds (default 1). "
                        "Without --seed, seeds are random starting points; "
                        "with --seed S, generates seeds S, S+1, …, S+N-1. "
                        "Mutually exclusive with --seeds.")

    # Fleet (optional — requires fleet module; enabled when --fleet-count > 1).
    p.add_argument("--fleet-count", type=_parse_pos_int, default=1,
                   help="Generate a fleet of N ships (default 1, single-ship "
                        "legacy behavior). Each ship is written as "
                        "ship_<seed>_<i>.litematic. Requires the fleet module.")
    p.add_argument("--fleet-size-tier",
                   choices=["small", "mid", "large", "capital", "mixed"],
                   default="mixed",
                   help="Fleet size tier (only used when --fleet-count > 1).")
    p.add_argument("--fleet-style-coherence", type=_parse_unit_float,
                   default=0.7,
                   help="Fleet style coherence in [0.0, 1.0] "
                        "(only used when --fleet-count > 1).")

    # Dry-run mode
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve generation params and print as JSON without writing files. Exit 0.",
    )

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
    p.add_argument(
        "--ship-size",
        type=_parse_ship_size,
        default=None,
        metavar="WxHxL",
        help="Override ship dimensions: width x height x length in blocks (e.g. 30x10x50). W>=4, H>=4, L>=8.",
    )
    p.add_argument("--preview-azimuth", type=float, default=None,
                   help="Camera azimuth angle in degrees for preview (default: 45).")
    p.add_argument("--preview-elevation", type=float, default=None,
                   help="Camera elevation angle in degrees for preview (default: 30).")

    # Verbosity
    p.add_argument("--verbose", action="store_true",
                   help="Print per-seed timings. Mutually exclusive with --quiet.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress success lines (errors still go to stderr). "
                        "Mutually exclusive with --verbose.")

    # Diagnostics
    p.add_argument("--stats", action="store_true",
                   help="After each ship, print a role -> cell-count table "
                        "(sorted by count desc, EMPTY skipped) plus total "
                        "block count and grid density. Useful for verifying "
                        "palette + style choices produced the desired "
                        "material distribution.")
    p.add_argument("--output-json", action="store_true",
                   help="Print a JSON summary of each generated ship to stdout.")
    p.add_argument("--export-manifest", action="store_true",
                   help="Write <name>.json sidecar alongside each .litematic with "
                        "seed, palette, shape, block count, and UTC timestamp.")
    p.add_argument(
        "--from-manifest",
        type=Path,
        default=None,
        metavar="FILE",
        help="Reproduce a ship from a prior --export-manifest JSON sidecar. "
             "Reads seed, palette, and dims (shape) from FILE and overrides "
             "those args. Mutually exclusive with --seed, --seeds, "
             "--seed-phrase, --repeat, and --fleet-count.",
    )
    p.add_argument(
        "--block-summary",
        action="store_true",
        default=False,
        help="Print block_id,count CSV (sorted by count desc) after generation. "
             "Useful for survival mode resource planning.",
    )

    return p


def _resolve_weapon_types(tokens: list[str] | None) -> tuple[list, list[str]]:
    """Turn CLI tokens into ``WeaponType`` members, collecting any bad names.

    Returns ``(allowed, unknown)``. ``allowed`` is the parsed list (may be
    empty when every token is unknown); ``unknown`` lists the rejected
    tokens so the caller can surface a single clear warning. When
    ``tokens`` is ``None`` (flag not set) we return ``([], [])`` and the
    caller defaults to "all types".
    """
    if _weapon_styles is None or not tokens:
        return ([], [])
    allowed = []
    unknown: list[str] = []
    valid = {wt.value: wt for wt in _weapon_styles.WeaponType}
    for tok in tokens:
        if tok in valid:
            allowed.append(valid[tok])
        else:
            unknown.append(tok)
    return (allowed, unknown)


def _apply_weapons(
    result: GenerationResult,
    *,
    seed: int,
    count: int,
    types: list | None,
    palette_obj,
    author: str,
    schem_name: str,
) -> None:
    """Scatter weapons into ``result.role_grid`` (in place) and re-export.

    No-op when ``weapon_styles`` is missing, ``count == 0``, or the scatter
    produces zero placements. Callers are expected to have already warned
    on stderr if the module is missing.
    """
    import numpy as np

    from .export import export_litematic

    if _weapon_styles is None or count <= 0:
        return

    rng = np.random.default_rng(seed ^ 0x7EA9)
    placements = _weapon_styles.scatter_weapons(
        result.role_grid, rng, count, types=types
    )
    if not placements:
        return

    grid = result.role_grid
    W, H, L = grid.shape
    for x, y, z, role in placements:
        if 0 <= x < W and 0 <= y < H and 0 <= z < L:
            grid[x, y, z] = role

    # Re-export so the weapons persist into the on-disk .litematic.
    export_litematic(
        grid,
        palette_obj,
        result.litematic_path,
        name=schem_name,
        author=author,
        description=f"Procedurally generated spaceship with weapons (seed={seed})",
    )

    # Refresh the preview PNG if one was rendered originally so the saved
    # image reflects the weaponised grid.
    if result.preview_png is not None:
        try:
            from .preview import render_preview

            result.preview_png = render_preview(
                grid, palette_obj, size=(800, 800)
            )
        except Exception:  # pragma: no cover - preview is best-effort
            pass


def _run_one(
    seed: int,
    *,
    args: argparse.Namespace,
    filename: str | None,
) -> GenerationResult:
    """Run a single generate() call using ``args`` for the shared parameters."""
    # ``args.greeble_density`` is ``None`` when the user didn't pass the
    # flag. In that case we keep the legacy ShapeParams default (0.05) and
    # leave the generator-level scatter at 0.0 so behavior is unchanged.
    shape_greeble = (
        args.greeble_density
        if args.greeble_density is not None
        else ShapeParams.__dataclass_fields__["greeble_density"].default
    )
    shape_params = ShapeParams(
        length=args.length,
        width_max=args.width,
        height_max=args.height,
        engine_count=args.engines,
        wing_prob=args.wing_prob,
        greeble_density=min(shape_greeble, 0.5),  # ShapeParams caps at 0.5
        cockpit_style=CockpitStyle(args.cockpit),
        structure_style=StructureStyle(args.structure_style),
        wing_style=WingStyle(args.wing_style),
        hull_noise=float(getattr(args, "hull_noise", 0.0) or 0.0),
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

    # New-style params — may not yet be wired on the generator side in which
    # case we gracefully fall back to the legacy signature.
    hull_style = HullStyle(args.hull_style) if args.hull_style else None
    # Z-axis blend: only engage when *both* front and rear are provided.
    # When either is missing we silently fall back to the legacy single-
    # style hull selection (this matches the documented "if either omitted,
    # behaviour matches current single-style ship" contract).
    hull_style_front = (
        HullStyle(args.hull_style_front)
        if getattr(args, "hull_style_front", None)
        else None
    )
    hull_style_rear = (
        HullStyle(args.hull_style_rear)
        if getattr(args, "hull_style_rear", None)
        else None
    )
    if hull_style_front is None or hull_style_rear is None:
        # Partial pair → don't engage the blend so we keep current behaviour.
        hull_style_front = None
        hull_style_rear = None
    engine_style = EngineStyle(args.engine_style) if args.engine_style else None
    # ``--cockpit-style`` is opt-in: when omitted we leave cockpit selection
    # to the legacy ``ShapeParams.cockpit_style`` (driven by ``--cockpit``).
    cockpit_style = (
        CockpitStyle(args.cockpit_style) if args.cockpit_style else None
    )
    gen_greeble = args.greeble_density if args.greeble_density is not None else 0.0
    greeble_types_arg = (
        [GreebleType(args.greeble_style)]
        if getattr(args, "greeble_style", None)
        else None
    )

    # When ``--ship-size`` is provided, override the three dimension fields on
    # the already-built ShapeParams so all downstream code (generator, fleet,
    # etc.) sees the user-supplied dimensions.
    if getattr(args, "ship_size", None) is not None:
        w, h, length = args.ship_size
        shape_params.width_max = w
        shape_params.height_max = h
        shape_params.length = length

    # When ``--cockpit-style`` is explicitly set, push it onto ShapeParams
    # too so consumers that read ``shape_params.cockpit_style`` (rather
    # than the new generator-level kwarg) also see the override.
    if cockpit_style is not None:
        shape_params.cockpit_style = cockpit_style

    base_kwargs = {
        "palette": args.palette,
        "shape_params": shape_params,
        "texture_params": texture_params,
        "out_dir": args.out,
        "filename": filename,
        "author": args.author,
        "name": args.name,
        "with_preview": bool(args.preview),
        "preview_size": args.preview_size,
    }
    try:
        # Forward ``cockpit_style`` alongside the other new-style kwargs.
        # The generator may not accept it yet — handled below via TypeError.
        extra_kwargs = {
            "hull_style": hull_style,
            "engine_style": engine_style,
            "greeble_density": gen_greeble,
            "greeble_types": greeble_types_arg,
        }
        if hull_style_front is not None and hull_style_rear is not None:
            extra_kwargs["hull_style_front"] = hull_style_front
            extra_kwargs["hull_style_rear"] = hull_style_rear
        if cockpit_style is not None:
            extra_kwargs["cockpit_style"] = cockpit_style
        result = generate(seed, **extra_kwargs, **base_kwargs)
    except TypeError:
        # Generator's new-style params aren't wired yet — warn and retry
        # with the legacy-only signature so the CLI stays usable in
        # lockstep-less rollouts.
        if (
            hull_style is not None
            or engine_style is not None
            or gen_greeble
            or cockpit_style is not None
            or greeble_types_arg is not None
        ):
            print(
                "Warning: --hull-style/--engine-style/--greeble-density/"
                "--cockpit-style/--greeble-style not supported by this generator; ignoring.",
                file=sys.stderr,
            )
        result = generate(seed, **base_kwargs)

    # Optional weapon pass. The scatter writes into ``result.role_grid`` in
    # place and re-exports the .litematic so the weapons persist on disk.
    weapon_count = int(getattr(args, "weapon_count", 0) or 0)
    if weapon_count > 0:
        if _weapon_styles is None:
            print(
                f"weapons unavailable: {_weapon_styles_error}",
                file=sys.stderr,
            )
        else:
            allowed, unknown = _resolve_weapon_types(
                getattr(args, "weapon_types", None)
            )
            if unknown:
                print(
                    "Warning: unknown --weapon-types ignored: "
                    + ", ".join(unknown),
                    file=sys.stderr,
                )
            types_arg = allowed or None
            try:
                from .palette import load_palette

                pal_obj = load_palette(args.palette)
                _apply_weapons(
                    result,
                    seed=seed,
                    count=weapon_count,
                    types=types_arg,
                    palette_obj=pal_obj,
                    author=args.author,
                    schem_name=args.name or f"Ship {seed}",
                )
            except TypeError as exc:
                print(f"weapons unavailable: {exc}", file=sys.stderr)

    if args.preview:
        # Re-render with custom camera angles when either angle flag is set.
        if args.preview_azimuth is not None or args.preview_elevation is not None:
            try:
                from .palette import load_palette
                from .preview import render_preview

                pal_obj = load_palette(args.palette)
                result.preview_png = render_preview(
                    result.role_grid,
                    pal_obj,
                    size=args.preview_size,
                    azimuth_deg=args.preview_azimuth,
                    elevation_deg=args.preview_elevation,
                )
            except Exception:  # pragma: no cover - preview is best-effort
                pass
        preview_path = result.litematic_path.with_suffix(".png")
        result.save_preview(preview_path)

    return result


def _run_fleet_ship(
    planned,
    *,
    idx: int,
    args: argparse.Namespace,
) -> GenerationResult:
    """Run one ship from a fleet plan.

    ``planned`` is a :class:`fleet.GeneratedShip`. We copy its parameters
    onto a shallow clone of ``args`` (so ``_run_one`` keeps a single
    plumbing path) and force the filename to ``ship_<seed>_<idx>.litematic``
    so fleet outputs never collide with each other or with solo-ship runs.
    """
    import copy

    ship_args = copy.copy(args)
    w, h, length = planned.dims
    ship_args.width = int(w)
    ship_args.height = int(h)
    ship_args.length = int(length)
    ship_args.palette = planned.palette
    if planned.hull_style is not None:
        ship_args.hull_style = planned.hull_style.value
    if planned.engine_style is not None:
        ship_args.engine_style = planned.engine_style.value
    if planned.wing_style is not None:
        ship_args.wing_style = planned.wing_style.value
    # Fleet ships always carry their own greeble density so the fleet as a
    # whole reads as a curated set rather than a uniform sweep.
    ship_args.greeble_density = float(planned.greeble_density)
    # Each ship gets a per-ship schematic name so Litematica's in-game
    # browser doesn't show ``count`` identical entries.
    if args.name is None:
        ship_args.name = f"Ship {planned.seed}"

    filename = f"ship_{planned.seed}_{idx}.litematic"
    return _run_one(planned.seed, args=ship_args, filename=filename)


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


def _print_stats(result: GenerationResult) -> None:
    """Print a role → cell-count table for ``result.role_grid``.

    Format::

        Role distribution:
          HULL: 1234 (45.2%)
          WINDOW: 321 (11.8%)
          ...
        Total blocks: 2728
        Density: 0.284

    - EMPTY is skipped (it's the dominant role and makes the table noisy).
    - Percentages are against non-EMPTY blocks (so they sum to ~100% modulo
      rounding).
    - Density is ``filled / total_cells`` in the **full** grid (EMPTY
      included in the denominator) so it measures how "packed" the ship is
      in its bounding box.

    Always writes to stdout; callers gate on ``--stats`` before invoking.
    """
    import numpy as np

    from .palette import Role

    grid = result.role_grid
    values, counts = np.unique(grid, return_counts=True)
    # ``np.unique`` returns ndarray scalars — cast to plain ints so we can
    # feed them to ``Role(...)`` without surprises.
    counts_by_role: dict[int, int] = {int(v): int(c) for v, c in zip(values, counts, strict=True)}

    total_cells = int(grid.size)
    empty_count = counts_by_role.get(int(Role.EMPTY), 0)
    filled = total_cells - empty_count
    density = (filled / total_cells) if total_cells > 0 else 0.0

    # Sort by count descending; skip EMPTY.
    non_empty = [
        (role_int, c)
        for role_int, c in counts_by_role.items()
        if role_int != int(Role.EMPTY)
    ]
    non_empty.sort(key=lambda rc: (-rc[1], rc[0]))

    print("Role distribution:")
    for role_int, c in non_empty:
        try:
            name = Role(role_int).name
        except ValueError:
            # Unknown role id (e.g. a custom weapon role beyond the enum):
            # surface its numeric value rather than crashing.
            name = f"ROLE_{role_int}"
        pct = (c / filled * 100.0) if filled > 0 else 0.0
        print(f"  {name}: {c} ({pct:.1f}%)")
    print(f"Total blocks: {filled}")
    print(f"Density: {density:.3f}")


def _print_json_summary(result: GenerationResult) -> None:
    """Print a one-line JSON summary of ``result`` to stdout.

    Emits newline-delimited JSON (NDJSON) — one object per call — so that
    bulk ``--seeds`` runs produce one machine-readable line per ship.
    Always writes to stdout; callers gate on ``--output-json`` before invoking.
    """
    import json

    summary = {
        "seed": result.seed,
        "palette": result.palette_name,
        "shape": list(result.shape),
        "blocks": result.block_count,
        "path": str(result.litematic_path),
    }
    print(json.dumps(summary), file=sys.stdout)


def _print_block_summary(result: GenerationResult) -> None:
    """Print CSV of block_id,count sorted by count descending."""
    import numpy as np

    from .palette import Role, load_palette

    pal = load_palette(result.palette_name)
    roles, counts = np.unique(result.role_grid, return_counts=True)
    pairs = []
    for role_int, count in zip(roles, counts, strict=True):
        if int(role_int) == int(Role.EMPTY):
            continue
        try:
            block_id = pal.block_state(int(role_int)).id
        except (ValueError, KeyError):
            continue
        pairs.append((block_id, int(count)))
    pairs.sort(key=lambda x: -x[1])
    print("block_id,count")
    for block_id, count in pairs:
        print(f"{block_id},{count}")


def _explicit_flags(argv: list[str] | None) -> set[str]:
    """Return the set of CLI long-option names that appear in ``argv``.

    Used to tell "user passed ``--hull-style saucer``" apart from "argparse
    filled in the default". We only need long-option names (``--hull-style``,
    etc.), and tokens like ``--foo=bar`` are normalized to ``--foo``. When
    ``argv`` is ``None`` we fall back to :data:`sys.argv` minus the program
    name so the behavior matches argparse's own default-source decision.
    """
    tokens = list(argv) if argv is not None else sys.argv[1:]
    seen: set[str] = set()
    for tok in tokens:
        if not isinstance(tok, str) or not tok.startswith("--"):
            continue
        # ``--foo=bar`` → ``--foo``.
        name = tok.split("=", 1)[0]
        seen.add(name)
    return seen


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    explicit = _explicit_flags(argv)

    # ``--no-greebles`` is a shortcut for ``--greeble-density 0``. Reject the
    # ambiguous case where both flags are passed; otherwise materialize the
    # shortcut by setting greeble_density to 0.0 so downstream plumbing
    # (which only reads ``args.greeble_density``) needs no special-case.
    if args.no_greebles and args.greeble_density is not None:
        parser.error("--no-greebles and --greeble-density are mutually exclusive")
    if args.no_greebles:
        args.greeble_density = 0.0

    if args.verbose and args.quiet:
        print("Error: --verbose and --quiet are mutually exclusive.", file=sys.stderr)
        return 2
    if args.seed is not None and args.seeds is not None:
        print("Error: --seed and --seeds are mutually exclusive.", file=sys.stderr)
        return 2
    if args.seeds is not None and args.repeat > 1:
        print("Error: --seeds and --repeat are mutually exclusive.", file=sys.stderr)
        return 2
    if args.seed_phrase is not None and (args.seed is not None or args.seeds is not None):
        print(
            "Error: --seed-phrase is mutually exclusive with --seed and --seeds.",
            file=sys.stderr,
        )
        return 1
    if args.seed_phrase is not None:
        phrase_seed = (
            int(hashlib.sha256(args.seed_phrase.encode()).hexdigest(), 16) % (2**31 - 1)
        )
        print(
            f'Seed phrase "{args.seed_phrase}" -> seed {phrase_seed}',
            file=sys.stderr,
        )
        args.seed = phrase_seed

    # ``--from-manifest FILE`` reproduces a previously-exported ship by
    # overriding seed/palette/dims from the JSON sidecar produced by
    # ``--export-manifest``. It conflicts with anything that also chooses
    # seeds (so the user's intent is unambiguous) and with fleet mode.
    if getattr(args, "from_manifest", None) is not None:
        conflicts = []
        if args.seed is not None and "--seed" in explicit:
            conflicts.append("--seed")
        if args.seeds is not None:
            conflicts.append("--seeds")
        if args.seed_phrase is not None:
            conflicts.append("--seed-phrase")
        if args.repeat > 1:
            conflicts.append("--repeat")
        if int(getattr(args, "fleet_count", 1) or 1) > 1:
            conflicts.append("--fleet-count")
        if conflicts:
            parser.error(
                "--from-manifest is mutually exclusive with "
                + ", ".join(conflicts)
            )

        manifest_path = Path(args.from_manifest)
        if not manifest_path.is_file():
            parser.error(f"--from-manifest: file not found: {manifest_path}")

        import json as _json
        try:
            manifest_data = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            parser.error(f"--from-manifest: invalid JSON in {manifest_path}: {exc}")

        if not isinstance(manifest_data, dict):
            parser.error(
                f"--from-manifest: top-level JSON in {manifest_path} must be an object"
            )

        # Required keys: ``seed``, ``palette``, and either ``shape`` (a 3-tuple)
        # or width+height+length. Anything else is optional.
        if "seed" not in manifest_data:
            parser.error(
                f"--from-manifest: missing required key 'seed' in {manifest_path}"
            )
        if "palette" not in manifest_data:
            parser.error(
                f"--from-manifest: missing required key 'palette' in {manifest_path}"
            )

        m_shape = manifest_data.get("shape")
        if m_shape is not None:
            if not isinstance(m_shape, list | tuple) or len(m_shape) != 3:
                parser.error(
                    f"--from-manifest: 'shape' must be a 3-element list "
                    f"[W, H, L] in {manifest_path}"
                )
            try:
                m_w, m_h, m_l = (int(x) for x in m_shape)
            except (TypeError, ValueError) as exc:
                parser.error(
                    f"--from-manifest: 'shape' must contain integers in "
                    f"{manifest_path}: {exc}"
                )
        elif all(k in manifest_data for k in ("width", "height", "length")):
            try:
                m_w = int(manifest_data["width"])
                m_h = int(manifest_data["height"])
                m_l = int(manifest_data["length"])
            except (TypeError, ValueError) as exc:
                parser.error(
                    f"--from-manifest: width/height/length must be integers in "
                    f"{manifest_path}: {exc}"
                )
        else:
            parser.error(
                f"--from-manifest: must contain 'shape' or "
                f"width+height+length in {manifest_path}"
            )

        # Override args from the manifest BEFORE the generation pipeline runs.
        try:
            args.seed = int(manifest_data["seed"])
        except (TypeError, ValueError) as exc:
            parser.error(
                f"--from-manifest: 'seed' must be an integer in "
                f"{manifest_path}: {exc}"
            )
        args.palette = str(manifest_data["palette"])
        args.width = m_w
        args.height = m_h
        args.length = m_l
        # ``--ship-size`` would otherwise win in ``_run_one``; clear it so the
        # manifest dims take effect.
        args.ship_size = None
        if manifest_data.get("preset") is not None:
            args.preset = manifest_data["preset"]

        print(
            f"Reproducing from manifest: seed={args.seed} "
            f"palette={args.palette} dims={m_w}x{m_h}x{m_l}",
            file=sys.stderr,
        )

    if args.list_palettes:
        names = list_palettes()
        if not names:
            print("(no palettes found)")
            return 0
        for n in names:
            print(n)
        return 0

    if args.list_shape_styles:
        # Narrower sibling of --list-styles: only the three "shape" enums
        # (hull / engine / wing). Same grouped, one-per-line, indent-by-two
        # format so a user can grep across both flags. Members emit in
        # enum-declaration order, which is deterministic and stable across
        # runs for callers piping into other tools.
        print("Hull styles:")
        for h in HullStyle:
            print(f"  {h.value}")
        print("Engine styles:")
        for e in EngineStyle:
            print(f"  {e.value}")
        print("Wing styles:")
        for w in WingStyle:
            print(f"  {w.value}")
        return 0

    if args.list_styles:
        print("Hull styles:")
        for h in HullStyle:
            print(f"  {h.value}")
        print("Engine styles:")
        for e in EngineStyle:
            print(f"  {e.value}")
        print("Wing styles:")
        for w in WingStyle:
            print(f"  {w.value}")
        print("Cockpit styles:")
        for c in CockpitStyle:
            print(f"  {c.value}")
        # Weapon types only appear when the optional module is available.
        # The fallback message goes to stderr so piping ``--list-styles``
        # into another program still gets clean hull/engine/wing output.
        if _weapon_styles is not None:
            print("Weapon types:")
            for wt in _weapon_styles.WeaponType:
                print(f"  {wt.value}")
        else:
            print(
                f"weapon_styles unavailable: {_weapon_styles_error}",
                file=sys.stderr,
            )
        return 0

    if args.list_presets:
        if _presets is None:
            # Defensive fallback: presets module missing in a partial rollout.
            # We still exit 0 so ``--list-presets`` remains a discovery tool
            # and print a stderr breadcrumb.
            print(
                f"presets unavailable: {_presets_error}",
                file=sys.stderr,
            )
            return 0
        names = _presets.list_presets()
        if not names:
            print("(no presets found)")
            return 0
        for n in names:
            spec = _presets.SHIP_PRESETS[n]
            desc = spec.get("description", "")
            if desc:
                print(f"  {n} — {desc}")
            else:
                print(f"  {n}")
        return 0

    if args.list_weapon_types:
        if _weapon_styles is None:
            print(f"weapon_styles unavailable: {_weapon_styles_error}", file=sys.stderr)
            raise SystemExit(1)
        for wt in _weapon_styles.WeaponType:
            print(f"  {wt.value}")
        raise SystemExit(0)

    if getattr(args, "palette_info", None):
        from .palette import Role, load_palette
        try:
            pal = load_palette(args.palette_info)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Palette: {pal.name}")
        for role in Role:
            if role == Role.EMPTY:
                continue
            bs = pal.blocks[role]
            r_f, g_f, b_f, _ = pal.preview_colors[role]
            hex_col = f"#{int(r_f * 255):02x}{int(g_f * 255):02x}{int(b_f * 255):02x}"
            print(f"  {role.name:<16} {bs.id:<40} {hex_col}")
        return 0

    # Resolve ``--preset`` → kwargs bundle. Individual flags override.
    # We mutate ``args`` in place so the downstream plumbing
    # (_run_one / _run_fleet_ship) sees the merged values without needing
    # to know about presets. The override rule: "user typed the flag on
    # the command line" wins over the preset's value.
    if args.preset is not None:
        if _presets is None:
            print(
                f"presets unavailable: {_presets_error}",
                file=sys.stderr,
            )
        else:
            try:
                preset_kwargs = _presets.apply_preset(args.preset)
            except KeyError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 2
            # Apply each preset field only when the user didn't set the
            # corresponding individual flag on the command line.
            preset_shape = preset_kwargs.get("shape_params")
            if preset_shape is not None:
                if "--length" not in explicit:
                    args.length = preset_shape.length
                if "--width" not in explicit:
                    args.width = preset_shape.width_max
                if "--height" not in explicit:
                    args.height = preset_shape.height_max
                if "--wing-style" not in explicit:
                    args.wing_style = preset_shape.wing_style.value
                if "--cockpit-style" not in explicit:
                    args.cockpit_style = preset_shape.cockpit_style.value
            if "--hull-style" not in explicit and preset_kwargs.get("hull_style") is not None:
                args.hull_style = preset_kwargs["hull_style"].value
            if "--engine-style" not in explicit and preset_kwargs.get("engine_style") is not None:
                args.engine_style = preset_kwargs["engine_style"].value
            if "--greeble-density" not in explicit and "greeble_density" in preset_kwargs:
                args.greeble_density = float(preset_kwargs["greeble_density"])
            if "--weapon-count" not in explicit and "weapon_count" in preset_kwargs:
                args.weapon_count = int(preset_kwargs["weapon_count"])
            if "--weapon-types" not in explicit and preset_kwargs.get("weapon_types"):
                # ``weapon_types`` from the preset is a list of WeaponType
                # enum members; the CLI's downstream plumbing expects raw
                # string tokens (to mirror ``--weapon-types`` input), so
                # map back to ``.value``.
                args.weapon_types = [wt.value for wt in preset_kwargs["weapon_types"]]

    # Resolve ``--palette random`` → a concrete palette name chosen at
    # runtime. This is intercepted here so all downstream code (fleet,
    # seeds loop, weapon pass) receives the same resolved name.
    if args.palette == "random":
        args.palette = random.choice(list_palettes())

    # --dry-run: resolve params, print JSON summary, write nothing, exit 0.
    if getattr(args, "dry_run", False):
        import json as _json

        dry_seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
        # Resolve dimensions (--ship-size overrides individual flags).
        if getattr(args, "ship_size", None) is not None:
            dry_w, dry_h, dry_l = args.ship_size
        else:
            dry_w, dry_h, dry_l = args.width, args.height, args.length
        dry_info = {
            "seed": dry_seed,
            "palette": args.palette,
            "width": dry_w,
            "height": dry_h,
            "length": dry_l,
            "preset": getattr(args, "preset", None),
            "dry_run": True,
        }
        print(_json.dumps(dry_info))
        return 0

    # Fleet mode short-circuits the seeds loop: one fleet seed plans N ships
    # and each planned ship is generated individually.
    fleet_count = int(getattr(args, "fleet_count", 1) or 1)
    if fleet_count > 1:
        if _fleet is None:
            print(f"fleet unavailable: {_fleet_error}", file=sys.stderr)
            # Fall back to single-ship behavior so partial rollouts still
            # produce *something* rather than silently doing nothing.
            fleet_count = 1
        elif args.seeds is not None:
            print(
                "Error: --seeds and --fleet-count > 1 are mutually exclusive.",
                file=sys.stderr,
            )
            return 2

    if fleet_count > 1:
        fleet_seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
        try:
            fleet_params = _fleet.FleetParams(
                count=fleet_count,
                palette=args.palette,
                size_tier=args.fleet_size_tier,
                style_coherence=float(args.fleet_style_coherence),
                seed=fleet_seed,
            )
            planned_ships = _fleet.generate_fleet(fleet_params)
        except (TypeError, ValueError) as exc:
            print(f"fleet unavailable: {exc}", file=sys.stderr)
            planned_ships = []

        successes = 0
        failures = 0
        for i, planned in enumerate(planned_ships):
            started = time.perf_counter() if args.verbose else None
            try:
                result = _run_fleet_ship(planned, idx=i, args=args)
            except FileNotFoundError as exc:
                print(f"Error (fleet ship {i}, seed={planned.seed}): {exc}",
                      file=sys.stderr)
                failures += 1
                continue
            except ValueError as exc:
                print(f"Error (fleet ship {i}, seed={planned.seed}): {exc}",
                      file=sys.stderr)
                failures += 1
                continue

            elapsed = (time.perf_counter() - started) if started is not None else None
            if i > 0 and not args.quiet:
                print()
            _print_success(result, elapsed=elapsed, args=args)
            if args.stats:
                _print_stats(result)
            if args.output_json:
                _print_json_summary(result)
            if args.export_manifest:
                import datetime as _dt
                import json as _json
                _manifest = {
                    "seed": result.seed,
                    "palette": result.palette_name,
                    "shape": list(result.shape),
                    "blocks": result.block_count,
                    "litematic": str(result.litematic_path),
                    "timestamp": _dt.datetime.now(_dt.UTC).isoformat() + "Z",
                }
                Path(result.litematic_path).with_suffix(".json").write_text(
                    _json.dumps(_manifest, indent=2), encoding="utf-8"
                )
            if args.block_summary:
                _print_block_summary(result)
            successes += 1

        if successes == 0:
            return 2
        if failures > 0:
            return 1
        return 0

    # Determine the seed list (legacy single + --seeds bulk + --repeat modes).
    if args.seeds is not None:
        seeds = list(args.seeds)
        bulk_mode = True
    elif args.repeat > 1:
        base = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
        seeds = list(range(base, base + args.repeat))
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
        if args.stats:
            _print_stats(result)
        if args.output_json:
            _print_json_summary(result)
        if args.export_manifest:
            import datetime as _dt
            import json as _json
            _manifest = {
                "seed": result.seed,
                "palette": result.palette_name,
                "shape": list(result.shape),
                "blocks": result.block_count,
                "litematic": str(result.litematic_path),
                "timestamp": _dt.datetime.now(_dt.UTC).isoformat() + "Z",
            }
            Path(result.litematic_path).with_suffix(".json").write_text(
                _json.dumps(_manifest, indent=2), encoding="utf-8"
            )
        if args.block_summary:
            _print_block_summary(result)
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
