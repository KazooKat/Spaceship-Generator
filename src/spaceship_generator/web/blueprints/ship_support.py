"""Shared helpers for the ``ship`` blueprint.

Extracted from ``ship.py`` so the route module stays under the project's
500-line cap. Covers:

* Constants consumed by the HTML form + /api/meta (``PARAM_HELP``,
  ``ROLE_LABELS``).
* Color approximation + palette-key legend construction.
* Form/JSON parameter parsing and input validation.
* The in-memory results store (``_ShipState``) with LRU eviction.
* Small template-rendering shortcuts used by multiple views.
"""

from __future__ import annotations

import math
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from flask import Flask, current_app, render_template, url_for

from ...block_colors import (
    approximate_block_color,
    block_texture_png,
    hex_to_rgba,
)
from ...generator import GenerationResult
from ...palette import Palette, Role, list_palettes, load_palette
from ...shape import CockpitStyle, ShapeParams, StructureStyle
from ...texture import TextureParams
from ...wing_styles import WingStyle


# Human-readable descriptions used for UI tooltips.
PARAM_HELP: dict[str, str] = {
    "seed": "Any integer. Same seed + same parameters always produce the same ship.",
    "palette": "Block & color theme. Defines what Minecraft block each role maps to. 'random' picks one from the current seed.",
    "length": "Z dimension (nose-to-tail) in blocks. Bigger = longer ship.",
    "width": "Max X dimension (wingspan) in blocks. Ship is mirrored across X.",
    "height": "Max Y dimension (top-to-bottom) in blocks.",
    "engines": "Number of engine nozzles at the rear (0-6). Mirrored across center.",
    "wing_prob": "Probability (0-1) that the ship grows wings off the hull.",
    "greeble_density": "Fraction (0-0.5) of hull surface covered in small detail blocks.",
    "cockpit": "Shape of the cockpit at the nose: bubble, pointed, or integrated.",
    "structure_style": "Overall ship archetype (frigate, fighter, dreadnought, shuttle, hammerhead, carrier). Changes hull profile, engine layout, and wings.",
    "wing_style": "Wing silhouette: straight (legacy slab), swept (tip angled rearward), delta (triangular), tapered (shrinking chord), gull (raised outer section), split (two stacked wings).",
    "window_period": "Block spacing between window lights along the hull. Lower = more windows.",
    "accent_stripe_period": "Block spacing between accent-colored stripes down the hull.",
    "engine_glow_depth": "How many blocks deep the engine glow core extends into the nozzle.",
    "hull_noise_ratio": "Amount of random HULL_DARK speckle on hull (0-1), per the 60-30-10 rule.",
    "panel_line_bands": "How many horizontal HULL_DARK panel-line bands run along the hull (1-3).",
    "rivet_period": "Block spacing of small rivet dots along edges. 0 disables them.",
    "engine_glow_ring": "Add a glowing ring around each engine nozzle.",
}


# Short human labels for legend entries — shown in the block-key panel.
ROLE_LABELS: dict[str, str] = {
    "HULL": "Hull (primary)",
    "HULL_DARK": "Hull accent / panel lines",
    "WINDOW": "Windows",
    "ENGINE": "Engine housing",
    "ENGINE_GLOW": "Engine glow core",
    "COCKPIT_GLASS": "Cockpit glass",
    "WING": "Wings",
    "GREEBLE": "Greebles (details)",
    "LIGHT": "Running lights",
    "INTERIOR": "Interior filler",
}


_DEFAULT_MAX_RESULTS = 100


# --- color / legend helpers -------------------------------------------------


def rgba_to_hex(rgba: tuple[float, float, float, float]) -> str:
    r, g, b, _a = rgba
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(r * 255)))),
        max(0, min(255, int(round(g * 255)))),
        max(0, min(255, int(round(b * 255)))),
    )


def approximate_role_colors(
    pal: Palette, *, allow_network: bool = False
) -> dict[Role, tuple[float, float, float, float]]:
    """Return per-role RGBA colors approximated from Minecraft block textures.

    Uses the bundled disk cache populated from the misode/mcmeta vanilla asset
    mirror. Falls back to the palette's stylized ``preview_colors`` when a
    block has no cached approximation. ``allow_network`` is off by default in
    request paths to keep latency bounded.
    """
    out: dict[Role, tuple[float, float, float, float]] = {}
    for role, block in pal.blocks.items():
        hex_col = approximate_block_color(str(block), allow_network=allow_network)
        if hex_col:
            out[role] = hex_to_rgba(hex_col)
        else:
            out[role] = pal.preview_colors.get(role, (0.5, 0.5, 0.5, 1.0))
    return out


def palette_key(palette_name: str) -> list[dict]:
    """Return a list of legend entries for ``palette_name``.

    Each entry is ``{role, label, color, block, hex}``. ``color`` is the
    approximated Minecraft block color (or stylized fallback); ``hex`` is its
    string form shown alongside the block id. If the palette can't be loaded,
    returns an empty list.
    """
    try:
        pal = load_palette(palette_name)
    except (FileNotFoundError, ValueError):
        # FileNotFoundError: palette YAML missing on disk.
        # ValueError: malformed YAML, missing required keys, or unparseable
        # block/color specs — all surfaced by ``Palette.load``.
        return []
    approx = approximate_role_colors(pal)
    entries: list[dict] = []
    for role in Role:
        if role == Role.EMPTY:
            continue
        block = pal.blocks.get(role)
        color_rgba = approx.get(role, (0.5, 0.5, 0.5, 1.0))
        color_hex = rgba_to_hex(color_rgba)
        block_str = str(block) if block is not None else ""
        # Only emit a texture URL when we already have the texture cached on
        # disk. This keeps request paths network-free — the Flask route will
        # 404 the missing ones and the template falls back to the color
        # swatch we already show.
        texture_url = ""
        if block_str and block_texture_png(block_str, allow_network=False):
            texture_url = url_for("block_texture", block_id=block_str)
        entries.append(
            {
                "role": role.name,
                "label": ROLE_LABELS.get(role.name, role.name.title()),
                "color": color_hex,
                "hex": color_hex,
                "block": block_str,
                "texture_url": texture_url,
            }
        )
    return entries


# --- shared state plumbing --------------------------------------------------


class _ShipState:
    """Mutable per-app state: the results store, its lock, and the instance
    output directory helper. Stashed on ``app.extensions['shipforge']`` so
    blueprint views can reach it via ``current_app`` instead of closures.
    """

    def __init__(self, app: Flask) -> None:
        self.app = app
        self.results: "OrderedDict[str, GenerationResult]" = OrderedDict()
        # Guards the insert + eviction loop in ``store``. ``OrderedDict`` is
        # not safe for concurrent mutation under a threaded WSGI server —
        # without this lock, two simultaneous ``store`` calls can
        # double-evict (each thread sees ``len(results) > max`` after both
        # inserts) or corrupt the LRU order.
        self.store_lock = threading.Lock()
        # Also expose on config so tests (and other blueprints) can reach it.
        app.config["_RESULTS"] = self.results

    def out_dir(self) -> Path:
        d = Path(self.app.instance_path) / "generated"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _cleanup_result(result: GenerationResult) -> None:
        """Delete the on-disk .litematic file for an evicted result."""
        try:
            Path(result.litematic_path).unlink(missing_ok=True)
        except OSError:
            # Best-effort cleanup; do not raise during eviction.
            pass

    def store(self, result: GenerationResult) -> str:
        gen_id = uuid.uuid4().hex[:12]
        max_results = int(self.app.config.get("MAX_RESULTS", _DEFAULT_MAX_RESULTS))
        evicted: list[GenerationResult] = []
        with self.store_lock:
            self.results[gen_id] = result
            while len(self.results) > max_results:
                _evicted_id, evicted_result = self.results.popitem(last=False)
                evicted.append(evicted_result)
        # Disk I/O outside the lock — the OrderedDict is already consistent.
        for evicted_result in evicted:
            self._cleanup_result(evicted_result)
        return gen_id


def state() -> _ShipState:
    return current_app.extensions["shipforge"]


def init_ship_state(app: Flask) -> _ShipState:
    """Create and attach a fresh ``_ShipState`` to ``app``."""
    app.config.setdefault("MAX_RESULTS", _DEFAULT_MAX_RESULTS)
    st = _ShipState(app)
    app.extensions["shipforge"] = st
    return st


# --- input parsing ----------------------------------------------------------


def _finite_float(source: Any, key: str, default: float) -> float:
    """Parse a float field that must be finite.

    ``float("inf")`` / ``float("nan")`` parse without error but poison
    downstream math (e.g. NaN propagates through numpy and then into the
    voxel payload). Reject non-finite values up front; the caller's
    ``except (ValueError, FileNotFoundError)`` returns 400.
    """
    v = float(source.get(key, default))
    if not math.isfinite(v):
        raise ValueError(f"{key} must be finite")
    return v


def build_params_from_source(
    source: Any,
) -> tuple[int, str, ShapeParams, TextureParams]:
    """Parse params from a dict-like source (form or JSON).

    Raises ValueError on bad input (caught by callers).
    """
    seed = int(source.get("seed") or 0)
    palette_name = source.get("palette", "sci_fi_industrial")

    # "random" (or "__random__") picks a palette deterministically from the
    # seed so the same seed still reproduces the same ship. This keeps the
    # generator's determinism contract while expanding the combination
    # space via the UI.
    if palette_name in ("random", "__random__"):
        available = [p for p in list_palettes() if p != "random"]
        if not available:
            raise ValueError("no palettes available")
        palette_name = available[abs(int(seed)) % len(available)]

    # Resolve structure_style. Default to FRIGATE for back-compat. Unknown
    # values raise ValueError here (converted to 400 by the caller).
    raw_structure = source.get("structure_style", StructureStyle.FRIGATE.value)
    try:
        structure_style = StructureStyle(raw_structure)
    except ValueError as exc:
        raise ValueError(
            f"structure_style must be one of "
            f"{[s.value for s in StructureStyle]}; got {raw_structure!r}"
        ) from exc

    # Resolve wing_style. Default STRAIGHT keeps legacy silhouette.
    raw_wing = source.get("wing_style", WingStyle.STRAIGHT.value)
    try:
        wing_style = WingStyle(raw_wing)
    except ValueError as exc:
        raise ValueError(
            f"wing_style must be one of "
            f"{[s.value for s in WingStyle]}; got {raw_wing!r}"
        ) from exc

    shape_params = ShapeParams(
        length=int(source.get("length", 40)),
        width_max=int(source.get("width", 20)),
        height_max=int(source.get("height", 12)),
        engine_count=int(source.get("engines", 2)),
        wing_prob=_finite_float(source, "wing_prob", 0.75),
        greeble_density=_finite_float(source, "greeble_density", 0.05),
        cockpit_style=CockpitStyle(
            source.get("cockpit", CockpitStyle.BUBBLE.value)
        ),
        structure_style=structure_style,
        wing_style=wing_style,
    )
    # "engine_glow_ring" accepts bool, "on"/"true"/"1" from forms, or a truthy
    # JSON bool. Treat any non-empty value other than "false"/"0" as True.
    raw_ring = source.get("engine_glow_ring", False)
    if isinstance(raw_ring, str):
        engine_glow_ring = raw_ring.strip().lower() not in ("", "false", "0", "off", "no")
    else:
        engine_glow_ring = bool(raw_ring)

    texture_params = TextureParams(
        window_period_cells=int(source.get("window_period", 4)),
        accent_stripe_period=int(source.get("accent_stripe_period", 8)),
        engine_glow_depth=int(source.get("engine_glow_depth", 1)),
        hull_noise_ratio=_finite_float(source, "hull_noise_ratio", 0.0),
        panel_line_bands=int(source.get("panel_line_bands", 1)),
        rivet_period=int(source.get("rivet_period", 0)),
        engine_glow_ring=engine_glow_ring,
    )
    return seed, palette_name, shape_params, texture_params


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# --- template shortcuts -----------------------------------------------------


def render_default_preview(result: GenerationResult) -> bytes | None:
    """Render (and return) the default-view approximated-color preview.

    Used by ``/preview/<gen_id>.png`` on demand. The WebGL renderer on
    the page no longer needs this PNG — it is kept only as a fallback
    for browsers without WebGL and for scripting consumers that still
    fetch ``preview_url`` from ``/api/generate``.
    """
    try:
        pal = load_palette(result.palette_name)
    except (FileNotFoundError, ValueError):
        return None
    from ...preview import render_preview

    return render_preview(
        result.role_grid,
        pal,
        size=(700, 700),
        color_override=approximate_role_colors(pal),
    )


def render_result_partial(gen_id: str, result: GenerationResult) -> str:
    return render_template(
        "_result.html",
        gen_id=gen_id,
        seed=result.seed,
        palette=result.palette_name,
        shape=result.shape,
        blocks=result.block_count,
        filename=result.litematic_path.name,
        key_entries=palette_key(result.palette_name),
    )


__all__ = [
    "PARAM_HELP",
    "ROLE_LABELS",
    "approximate_role_colors",
    "build_params_from_source",
    "clamp",
    "init_ship_state",
    "palette_key",
    "render_default_preview",
    "render_result_partial",
    "rgba_to_hex",
    "state",
]
