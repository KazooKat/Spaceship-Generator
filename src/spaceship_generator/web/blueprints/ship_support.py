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
import sys
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from flask import Flask, current_app, render_template, url_for

from ... import presets as _presets
from ...block_colors import (
    approximate_block_color,
    block_texture_png,
    hex_to_rgba,
)
from ...engine_styles import EngineStyle
from ...generator import GenerationResult
from ...palette import Palette, Role, list_palettes, load_palette
from ...shape import CockpitStyle, ShapeParams, StructureStyle
from ...structure_styles import HullStyle
from ...texture import TextureParams
from ...weapon_styles import WeaponType
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
    return f"#{max(0, min(255, int(round(r * 255)))):02x}{max(0, min(255, int(round(g * 255)))):02x}{max(0, min(255, int(round(b * 255)))):02x}"


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
        self.results: OrderedDict[str, GenerationResult] = OrderedDict()
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


def _parse_optional_enum(
    source: Any, key: str, enum_cls: type
) -> Any:
    """Parse a form/JSON field that accepts ``"auto"`` / empty as ``None``.

    Otherwise construct the enum from the raw value. Raises
    :class:`ValueError` on unknown enum values so the caller surfaces 400.
    """
    raw = source.get(key)
    if raw is None:
        return None
    if isinstance(raw, str):
        raw_str = raw.strip().lower()
        if raw_str in ("", "auto", "__auto__"):
            return None
        try:
            return enum_cls(raw_str)
        except ValueError as exc:
            valid = [m.value for m in enum_cls]
            raise ValueError(
                f"{key} must be 'auto' or one of {valid}; got {raw!r}"
            ) from exc
    # Non-string (already an enum instance, or something wrapping it).
    if isinstance(raw, enum_cls):
        return raw
    try:
        return enum_cls(raw)
    except ValueError as exc:
        valid = [m.value for m in enum_cls]
        raise ValueError(
            f"{key} must be 'auto' or one of {valid}; got {raw!r}"
        ) from exc


def _parse_preset(source: Any) -> str | None:
    """Return a valid preset name from ``source``, or ``None``.

    Accepts a ``preset`` field on the form/JSON source and validates it
    against :func:`spaceship_generator.presets.list_presets`. Empty strings,
    missing values, and unknown preset names all collapse to ``None`` so a
    typo or stale client can't 400 the request — the preset is simply
    ignored and the raw form values drive generation.
    """
    if not hasattr(source, "get"):
        return None
    raw = source.get("preset")
    if raw is None or not isinstance(raw, str):
        return None
    name = raw.strip()
    if not name:
        return None
    if name not in _presets.list_presets():
        return None
    return name



# HTML-default values that the browser form always submits when the user has
# not explicitly changed a field. When a preset is active we treat an incoming
# value that matches the HTML default as "not set" so the preset can supply a
# richer value — exactly the same logic the CLI uses when ``--preset`` is
# combined with per-flag overrides (explicit flag wins; implicit HTML default
# does NOT count as an explicit override).
#
# These must stay in sync with the ``defaults`` dict passed to ``index.html``
# by the ``index()`` route in ``ship.py``.
_HTML_FORM_DEFAULTS: dict[str, Any] = {
    "length": 40,
    "width": 20,
    "height": 12,
    "engines": 2,
    "wing_prob": 0.75,
    "greeble_density": 0.0,
    "wing_style": "straight",
    "cockpit": "bubble",
    "structure_style": "frigate",
}


def _merge_preset_into_source(source: Any, preset_name: str) -> dict[str, Any]:
    """Return a new dict layering preset defaults under ``source``.

    Mirrors the CLI's override rule: individual form fields win, preset
    values fill in gaps. Concretely:

    * Style enum fields (``hull_style``, ``engine_style``, ``wing_style``,
      ``cockpit_style``, ``cockpit``) accept the preset value when the form
      sends ``auto``/empty/missing — ``auto`` is the UI sentinel for
      "don't override the pipeline default", and with a preset in play the
      preset IS the pipeline default.
    * For ``wing_style`` and ``cockpit``, the HTML-default values
      (``straight`` / ``bubble``) are treated as "not set" when a preset
      is active — the browser always submits the current option value, so
      the user's "I haven't touched this" intent must be inferred by
      comparing against the known HTML default.
    * Numeric shape fields (``length``, ``width``, ``height``) accept the
      preset value when the form submits the HTML-default value (40/20/12).
      Because the browser always sends every named input's current value,
      "user submitted 40 and has never touched the slider" is
      indistinguishable from "user explicitly typed 40", so we use the
      HTML-default as a sentinel for the unset state.  A user who genuinely
      wants length=40 when using the corvette preset (which defaults to 50)
      can achieve it by clicking away from the preset and back — the intent
      is preserved for the overwhelming majority case.
    * ``greeble_density``, ``weapon_count``, ``weapon_types`` follow the
      same "absent key → preset wins" rule as before.

    Returns a fresh ``dict`` so callers can mutate safely. ``weapon_types``
    from the preset is flattened to the raw string tokens the downstream
    parser already understands, matching the CLI's own mapping.
    """
    preset_kwargs = _presets.apply_preset(preset_name)
    preset_shape: ShapeParams = preset_kwargs["shape_params"]

    # Preserve MultiDict semantics when the caller passed one (form path)
    # so ``weapon_types=turret_large&weapon_types=missile_pod`` doesn't
    # collapse to a single value during the merge. JSON callers already
    # pass plain dicts so we fall back to ``dict`` for them.
    if hasattr(source, "getlist") and hasattr(source, "setlist"):
        # werkzeug MultiDict (or mutable subclass) — reuse the mutable form.
        try:
            from werkzeug.datastructures import MultiDict  # local import
            merged = MultiDict(source)
        except ImportError:  # pragma: no cover - werkzeug is a flask dep
            merged = dict(source)
    elif hasattr(source, "getlist"):
        # Immutable MultiDict (``request.form``) — promote to mutable MultiDict
        # by copying items including all values.
        try:
            from werkzeug.datastructures import MultiDict  # local import
            merged = MultiDict(source)
        except ImportError:  # pragma: no cover - werkzeug is a flask dep
            merged = dict(source)
    else:
        merged = dict(source)

    def _style_missing(key: str, html_defaults: tuple[str, ...] = ()) -> bool:
        """True when ``key`` is absent, the ``auto`` sentinel, or matches one
        of the given ``html_defaults`` (which means the user never touched the
        control and the preset should win)."""
        if key not in merged:
            return True
        v = merged[key]
        if v is None:
            return True
        if isinstance(v, str):
            vs = v.strip().lower()
            if vs in ("", "auto", "__auto__"):
                return True
            if vs in html_defaults:
                return True
        return False

    def _numeric_is_default(key: str) -> bool:
        """True when ``key`` is absent OR equals the HTML-form default value.

        The browser always submits every named input. We treat a submitted
        value that matches the HTML default as "the user hasn't explicitly
        set this", allowing the preset to supply a richer value.
        """
        if key not in merged:
            return True
        html_default = _HTML_FORM_DEFAULTS.get(key)
        if html_default is None:
            return False  # no known default — treat as explicitly set
        try:
            submitted = float(merged[key])
            return submitted == float(html_default)
        except (TypeError, ValueError):
            return False

    # Size dimensions — preset wins when the form omits the field OR submits
    # the HTML-default value (user never touched the slider).
    if _numeric_is_default("length"):
        merged["length"] = preset_shape.length
    if _numeric_is_default("width"):
        merged["width"] = preset_shape.width_max
    if _numeric_is_default("height"):
        merged["height"] = preset_shape.height_max

    # Style enums — preset wins when the form sends auto/empty or the
    # HTML-default option value.
    hull_style = preset_kwargs.get("hull_style")
    if hull_style is not None and _style_missing("hull_style"):
        merged["hull_style"] = hull_style.value
    engine_style = preset_kwargs.get("engine_style")
    if engine_style is not None and _style_missing("engine_style"):
        merged["engine_style"] = engine_style.value
    # wing_style: "straight" is the HTML form default; treat it the same as
    # "auto" so the preset's wing_style wins when the user hasn't changed it.
    if (
        preset_shape.wing_style is not None
        and _style_missing("wing_style", html_defaults=("straight",))
    ):
        merged["wing_style"] = preset_shape.wing_style.value
    if _style_missing("cockpit_style") and preset_shape.cockpit_style is not None:
        merged["cockpit_style"] = preset_shape.cockpit_style.value
    # ``cockpit`` is the shape-level picker; "bubble" is the HTML default —
    # treat it the same as "auto" so the preset's cockpit archetype wins.
    if (
        preset_shape.cockpit_style is not None
        and _style_missing("cockpit", html_defaults=("bubble",))
    ):
        merged["cockpit"] = preset_shape.cockpit_style.value

    # Generator-level scalars — preset wins when the key is absent.
    if "greeble_density" not in merged and "greeble_density" in preset_kwargs:
        merged["greeble_density"] = float(preset_kwargs["greeble_density"])
    if "weapon_count" not in merged and "weapon_count" in preset_kwargs:
        merged["weapon_count"] = int(preset_kwargs["weapon_count"])
    if "weapon_types" not in merged and preset_kwargs.get("weapon_types"):
        wt_values = [wt.value for wt in preset_kwargs["weapon_types"]]
        # MultiDict-aware assign so the downstream ``getlist`` path sees the
        # full preset list rather than just the first element.
        if hasattr(merged, "setlist"):
            merged.setlist("weapon_types", wt_values)
        else:
            merged["weapon_types"] = wt_values

    return merged


def build_params_from_source(
    source: Any,
) -> tuple[int, str, ShapeParams, TextureParams, dict[str, Any]]:
    """Parse params from a dict-like source (form or JSON).

    Returns a 5-tuple ``(seed, palette_name, shape_params, texture_params,
    extra_gen_kwargs)`` where ``extra_gen_kwargs`` carries top-level
    :func:`spaceship_generator.generator.generate` kwargs that don't fit
    inside :class:`ShapeParams` / :class:`TextureParams` (currently
    ``hull_style``, ``engine_style``, ``greeble_density``). Callers should
    pass ``extra_gen_kwargs`` through a ``try/except TypeError`` fallback so
    older ``generate`` implementations that don't accept those kwargs still
    work.

    If the source carries a ``preset`` field matching one of
    :func:`spaceship_generator.presets.list_presets`, the preset's values
    seed the parsing as defaults; individual form fields still override the
    preset the same way ``--hull-style`` etc. override ``--preset`` on the
    CLI. Unknown/empty preset names are silently ignored so a stale client
    can never 400 the request.

    Raises ValueError on bad input (caught by callers).
    """
    # Preset merge happens first so every downstream lookup (shape,
    # texture, extras) sees the seeded defaults. The merge is a pure
    # dict-level operation — individual parsers stay preset-agnostic.
    preset_name = _parse_preset(source)
    if preset_name is not None:
        source = _merge_preset_into_source(source, preset_name)
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

    # Parse the top-level generator greeble-density slider (0-1). Clamp to
    # [0, 1] so accidentally-out-of-range form input doesn't 400 — the UI's
    # slider is [0, 1] step 0.05, and callers that hand-roll JSON can still
    # feed wild numbers. The shape-level ``ShapeParams.greeble_density`` is
    # a distinct dial (legacy hull-top greeble placement, capped at 0.5);
    # we reuse the same field value but clamp separately for each.
    gen_greeble_density_raw = _finite_float(source, "greeble_density", 0.0)
    gen_greeble_density = clamp(gen_greeble_density_raw, 0.0, 1.0)
    # ShapeParams validates greeble_density ≤ 0.5. Pass the clamped value so
    # we never violate its invariant even if the slider is >0.5.
    shape_greeble_density = clamp(gen_greeble_density_raw, 0.0, 0.5)

    shape_params = ShapeParams(
        length=int(source.get("length", 40)),
        width_max=int(source.get("width", 20)),
        height_max=int(source.get("height", 12)),
        engine_count=int(source.get("engines", 2)),
        wing_prob=_finite_float(source, "wing_prob", 0.75),
        greeble_density=shape_greeble_density,
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

    # Optional top-level generator kwargs. ``None`` means "auto" / pipeline
    # default — only members actually chosen by the user are forwarded so
    # older ``generate`` signatures can still swallow the rest.
    extra_gen_kwargs: dict[str, Any] = {
        "hull_style": _parse_optional_enum(source, "hull_style", HullStyle),
        "engine_style": _parse_optional_enum(
            source, "engine_style", EngineStyle
        ),
        "greeble_density": gen_greeble_density,
        "cockpit_style": _parse_optional_enum(
            source, "cockpit_style", CockpitStyle
        ),
        "weapon_count": _parse_weapon_count(source),
        "weapon_types": _parse_weapon_types(source),
    }
    return seed, palette_name, shape_params, texture_params, extra_gen_kwargs


def _parse_weapon_count(source: Any) -> int:
    """Parse the weapon_count form/JSON field.

    Coerces to int and clamps to ``[0, 8]`` so the generator's scatter loop
    can't be driven into pathological territory by a tampered URL or hand-
    rolled JSON body. Non-numeric or missing values collapse to ``0``.
    """
    raw = source.get("weapon_count", 0)
    try:
        n = int(float(raw)) if raw not in (None, "") else 0
    except (TypeError, ValueError):
        n = 0
    return int(clamp(n, 0, 8))


def _parse_weapon_types(source: Any) -> list[WeaponType] | None:
    """Parse weapon_types from a form (``getlist``) or JSON (``list``).

    * Unknown tokens are dropped with a stderr warning so the request still
      succeeds — the generator just ends up with a narrower allow-list than
      the user asked for.
    * An empty result returns ``None`` (meaning "use all types" downstream).
    """
    # ``werkzeug.ImmutableMultiDict`` (form) exposes ``getlist``; plain
    # dicts (JSON) don't. Branch on availability.
    raw: list[Any]
    if hasattr(source, "getlist"):
        raw = list(source.getlist("weapon_types"))
    else:
        maybe = source.get("weapon_types")
        if maybe is None:
            raw = []
        elif isinstance(maybe, (list, tuple)):
            raw = list(maybe)
        elif isinstance(maybe, str):
            # Tolerate a comma-separated string so JSON callers can hand
            # us a single field — mirrors the CLI's parse path.
            raw = [tok for tok in maybe.split(",") if tok.strip()]
        else:
            raw = [maybe]

    resolved: list[WeaponType] = []
    for tok in raw:
        if tok is None:
            continue
        if isinstance(tok, WeaponType):
            resolved.append(tok)
            continue
        tok_str = str(tok).strip().lower()
        if not tok_str:
            continue
        try:
            resolved.append(WeaponType(tok_str))
        except ValueError:
            print(
                f"warning: dropping unknown weapon_type token {tok!r}",
                file=sys.stderr,
            )
    return resolved or None


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
    "_parse_preset",
    "_merge_preset_into_source",
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
