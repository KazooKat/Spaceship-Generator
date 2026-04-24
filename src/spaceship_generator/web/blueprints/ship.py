"""Core generation routes: HTML form flow + JSON API + metadata + voxels/preview.

All routes live on a single ``ship`` blueprint. Helpers, constants, and
shared state plumbing live in ``ship_support`` so this module stays
focused on HTTP handling.
"""

from __future__ import annotations

import base64
import io
import random
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from ... import presets
from ...block_colors import block_alpha, is_translucent
from ...engine_styles import EngineStyle, build_engines
from ...fleet import SIZE_TIERS, FleetParams, generate_fleet
from ...generator import generate
from ...greeble_styles import scatter_greebles
from ...palette import Role, list_palettes, load_palette
from ...shape import CockpitStyle, ShapeParams, StructureStyle, generate_shape
from ...structure_styles import HullStyle
from ...texture import assign_roles
from ...weapon_styles import WeaponType
from ...wing_styles import WingStyle
from .ratelimit import check_rate_limit
from .ship_support import (
    PARAM_HELP,
    approximate_role_colors,
    build_params_from_source,
    clamp,
    palette_key,
    render_default_preview,
    render_result_partial,
    state,
)

ship_bp = Blueprint("ship", __name__)


def _ship_metadata(seed: int, shape_params, palette_name: str) -> dict:
    """Return metadata for one ship without writing any files."""
    shape_grid = generate_shape(seed, shape_params)
    W, H, L = shape_grid.shape
    role_grid = assign_roles(shape_grid)
    filled_mask = shape_grid > 0
    roles, counts = np.unique(role_grid[filled_mask], return_counts=True)
    role_map = {str(r): int(c) for r, c in zip(roles, counts, strict=True)}
    return {
        "seed": seed,
        "dimensions": {"width": W, "height": H, "length": L},
        "voxel_count": int(np.sum(filled_mask)),
        "role_counts": role_map,
    }


def _generate_with_extras(seed, *, extra_gen_kwargs: dict, **base_kwargs):
    """Call :func:`generate` with the base kwargs plus the style-picker
    extras, falling back if ``generate()`` doesn't accept them yet.

    The ``extra_gen_kwargs`` dict may contain ``hull_style``,
    ``engine_style``, and ``greeble_density``. If the local ``generate``
    implementation raises :class:`TypeError` (e.g. it predates the style-
    picker wiring), we drop the extras and retry with just the base kwargs
    so the POST still succeeds. Also filters out ``None`` values before the
    first call so "auto" selections don't override ``generate`` defaults.
    """
    # Drop ``None`` (= "auto") before forwarding so we never stomp on the
    # generator's own defaults for unselected style pickers.
    forwarded = {k: v for k, v in (extra_gen_kwargs or {}).items() if v is not None}
    try:
        return generate(seed, **base_kwargs, **forwarded)
    except TypeError:
        # ``generate`` may not yet accept one of hull_style / engine_style /
        # greeble_density as a kwarg (parallel wiring in progress). Retry
        # with only the legacy base kwargs rather than failing the request.
        return generate(seed, **base_kwargs)


@ship_bp.route("/", endpoint="index")
def index():
    return render_template(
        "index.html",
        palettes=list_palettes(),
        presets=presets.list_presets(),
        cockpit_styles=[c.value for c in CockpitStyle],
        structure_styles=[s.value for s in StructureStyle],
        wing_styles=[w.value for w in WingStyle],
        hull_styles=[h.value for h in HullStyle],
        engine_styles=[e.value for e in EngineStyle],
        weapon_types=[w.value for w in WeaponType],
        param_help=PARAM_HELP,
        defaults={
            "seed": random.randint(0, 2**31 - 1),
            "palette": "sci_fi_industrial",
            "length": 40,
            "width": 20,
            "height": 12,
            "engines": 2,
            "wing_prob": 0.75,
            "greeble_density": 0.0,
            "window_period": 4,
            "accent_stripe_period": 8,
            "engine_glow_depth": 1,
            "hull_noise_ratio": 0.0,
            "panel_line_bands": 1,
            "rivet_period": 0,
            "engine_glow_ring": False,
            "cockpit": CockpitStyle.BUBBLE.value,
            "structure_style": StructureStyle.FRIGATE.value,
            "wing_style": WingStyle.STRAIGHT.value,
            "hull_style": "auto",
            "engine_style": "auto",
        },
    )


@ship_bp.route("/generate", methods=["POST"], endpoint="do_generate")
def do_generate():
    limited = check_rate_limit(as_json=False)
    if limited is not None:
        return limited
    st = state()
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    try:
        seed, palette_name, shape_params, texture_params, extra_gen_kwargs = (
            build_params_from_source(request.form)
        )

        # Skip eager matplotlib render: the client uses the WebGL canvas
        # which pulls voxel data from ``/voxels/<gen_id>.json``. The
        # ``/preview/<gen_id>.png`` route still works, but renders lazily.
        result = _generate_with_extras(
            seed,
            palette=palette_name,
            shape_params=shape_params,
            texture_params=texture_params,
            out_dir=st.out_dir(),
            with_preview=False,
            extra_gen_kwargs=extra_gen_kwargs,
        )
    except (ValueError, FileNotFoundError) as exc:
        if is_htmx:
            return (
                render_template("_error.html", error=str(exc)),
                400,
            )
        return (
            render_template(
                "index.html",
                palettes=list_palettes(),
                presets=presets.list_presets(),
                cockpit_styles=[c.value for c in CockpitStyle],
                structure_styles=[s.value for s in StructureStyle],
                wing_styles=[w.value for w in WingStyle],
                hull_styles=[h.value for h in HullStyle],
                engine_styles=[e.value for e in EngineStyle],
                weapon_types=[w.value for w in WeaponType],
                param_help=PARAM_HELP,
                defaults=request.form.to_dict(),
                error=str(exc),
            ),
            400,
        )

    gen_id = st.store(result)
    if is_htmx:
        return render_result_partial(gen_id, result)
    return redirect(url_for("show_result", gen_id=gen_id))


@ship_bp.route("/result/<gen_id>", endpoint="show_result")
def show_result(gen_id: str):
    result = state().results.get(gen_id)
    if result is None:
        abort(404)
    return render_template(
        "result.html",
        gen_id=gen_id,
        seed=result.seed,
        palette=result.palette_name,
        shape=result.shape,
        blocks=result.block_count,
        filename=result.litematic_path.name,
        key_entries=palette_key(result.palette_name),
    )


@ship_bp.route("/preview/<gen_id>.png", endpoint="preview")
def preview(gen_id: str):
    result = state().results.get(gen_id)
    if result is None:
        abort(404)

    raw_elev = request.args.get("elev")
    raw_azim = request.args.get("azim")

    # No view override: lazily render and cache the approximated-color
    # default-view PNG. The WebGL canvas makes this route unnecessary for
    # the normal UI flow — it remains for no-WebGL fallback and scripting.
    if raw_elev is None and raw_azim is None:
        if result.preview_png is None:
            png = render_default_preview(result)
            if png is None:
                abort(404)
            result.preview_png = png
        return send_file(io.BytesIO(result.preview_png), mimetype="image/png")

    try:
        elev = clamp(float(raw_elev) if raw_elev is not None else 22.0, -89.0, 89.0)
        azim = float(raw_azim) if raw_azim is not None else -62.0
    except ValueError:
        abort(400)

    try:
        pal = load_palette(result.palette_name)
    except (FileNotFoundError, ValueError):
        abort(404)

    # Import lazily — matplotlib is a big import.
    from ...preview import render_preview

    png = render_preview(
        result.role_grid,
        pal,
        size=(700, 700),
        view=(elev, azim),
        color_override=approximate_role_colors(pal),
    )
    return send_file(io.BytesIO(png), mimetype="image/png")


@ship_bp.route("/preview-lite", endpoint="preview_lite")
def preview_lite():
    """Return a small, quick-render PNG preview for the given params.

    Used by the debounced live-preview toggle in the sidebar — as the user
    drags sliders / switches enums, the client refetches this endpoint with
    the current form query string and updates an <img> src. Compared with
    ``POST /generate``, this route:

    * Reads params from ``request.args`` (so it's a cheap GET — cacheable).
    * Skips the .litematic export entirely (big I/O + serialization win).
    * Runs only the shape → role grid → matplotlib preview pipeline, at a
      reduced size (≤300px) so renders stay snappy even on a hot slider.
    * Attaches ``Cache-Control: public, max-age=30`` so identical queries
      (same seed + same params) don't re-render for half a minute.

    Rate-limited via the shared per-IP limiter so spamming the endpoint
    can't pin the server — see ``check_rate_limit``.
    """
    limited = check_rate_limit(as_json=False)
    if limited is not None:
        return limited
    try:
        seed, palette_name, shape_params, texture_params, extras = (
            build_params_from_source(request.args)
        )
    except (ValueError, KeyError) as exc:
        # Bad param value (ValueError from parsers) or a required key that
        # downstream code can't cope with. Either way it's a 400.
        return (str(exc), 400)

    try:
        pal = load_palette(palette_name)
    except (FileNotFoundError, ValueError) as exc:
        return (str(exc), 400)

    # Mirror the relevant pieces of ``generate`` without the export step.
    # This stays structurally parallel to ``scripts/gen_gallery.py`` so
    # behavior matches the gallery tool.
    hull_style = extras.get("hull_style")
    engine_style = extras.get("engine_style")
    gen_greeble_density = float(extras.get("greeble_density") or 0.0)

    shape_grid = generate_shape(seed, shape_params, hull_style=hull_style)

    if engine_style is not None:
        W, H, L = shape_grid.shape
        engine_mask = (shape_grid == Role.ENGINE) | (shape_grid == Role.ENGINE_GLOW)
        shape_grid[engine_mask] = Role.EMPTY
        engine_rng = np.random.default_rng(seed ^ 0xE5)
        base_radius = max(1, min(W, H) // 10)
        engine_length = max(2, L // 8)
        spread = max(2, W // 4)
        cy_engine = max(base_radius + 1, H // 2 - 1)
        for x, y, z, role in build_engines(
            shape_grid,
            engine_style,
            position=(W // 2, cy_engine, 0),
            size=(base_radius, engine_length, spread),
            rng=engine_rng,
        ):
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                shape_grid[x, y, z] = role

    if gen_greeble_density > 0.0:
        W, H, L = shape_grid.shape
        greeble_rng = np.random.default_rng(seed ^ 0x6E)
        for x, y, z, role in scatter_greebles(
            shape_grid, greeble_rng, gen_greeble_density
        ):
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                if shape_grid[x, y, z] == Role.EMPTY:
                    shape_grid[x, y, z] = role

    role_grid = assign_roles(shape_grid, texture_params)

    # Matplotlib preview at reduced resolution. 256 sits under the ≤300px cap
    # and renders in a fraction of the full-size preview time, which is what
    # makes the debounced live-refresh tolerable.
    from ...preview import render_preview
    png = render_preview(
        role_grid,
        pal,
        size=(256, 256),
        color_override=approximate_role_colors(pal),
    )

    resp = send_file(io.BytesIO(png), mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp


@ship_bp.route("/voxels/<gen_id>.json", endpoint="voxels")
def voxels(gen_id: str):
    """Return surface voxels + per-role colors as JSON for client WebGL.

    Response shape::

        {
          "dims": [W, H, L],           # role_grid is indexed [x, y, z]
          "count": N,                  # number of surface voxels
          "voxels": "<base64 Int16Array>",
                                       # length = 4 * N; (x, y, z, role)
                                       # tuples, Int16 little-endian
          "colors": {"1": [r,g,b,a], ...}   # role enum int -> 0-1 RGBA
        }

    Only surface voxels (filled cells with at least one empty 6-neighbor)
    are emitted — the interior cubes are invisible, and including them
    would bloat the payload by 5-10x for typical ships.
    """
    result = state().results.get(gen_id)
    if result is None:
        abort(404)

    grid = result.role_grid
    if grid.ndim != 3:
        abort(500)

    # Surface mask: filled cell with at least one empty 6-neighbor.
    filled = grid != int(Role.EMPTY)
    # Shift by one on each axis to compute neighbor-emptiness per voxel.
    # Cells on the grid boundary are surface by definition (neighbor outside
    # the grid is implicitly empty).
    pad = np.pad(filled, 1, mode="constant", constant_values=False)
    neighbors_filled = (
        pad[:-2, 1:-1, 1:-1]
        & pad[2:, 1:-1, 1:-1]
        & pad[1:-1, :-2, 1:-1]
        & pad[1:-1, 2:, 1:-1]
        & pad[1:-1, 1:-1, :-2]
        & pad[1:-1, 1:-1, 2:]
    )
    surface = filled & ~neighbors_filled

    xs, ys, zs = np.nonzero(surface)
    roles = grid[xs, ys, zs].astype(np.int16)
    # Pack as interleaved Int16 (x, y, z, role). Using Int16 bounds
    # each coordinate to [-32768, 32767] which is fine for ship grids.
    packed = np.empty((xs.size, 4), dtype=np.int16)
    packed[:, 0] = xs.astype(np.int16)
    packed[:, 1] = ys.astype(np.int16)
    packed[:, 2] = zs.astype(np.int16)
    packed[:, 3] = roles
    # Ensure little-endian encoding for predictable client decoding.
    raw = packed.astype("<i2", copy=False).tobytes()
    b64 = base64.b64encode(raw).decode("ascii")

    try:
        pal = load_palette(result.palette_name)
    except (FileNotFoundError, ValueError):
        abort(404)
    approx = approximate_role_colors(pal)
    # JSON keys must be strings. Translucent Minecraft blocks (glass,
    # ice, honey, slime) get their alpha channel replaced with a
    # suggested translucency so the WebGL renderer can draw them with
    # blending. RGB is preserved from the approximated block color.
    colors_json: dict[str, list[float]] = {}
    for role, rgba in approx.items():
        block = pal.blocks.get(role)
        block_str = str(block) if block is not None else ""
        if block_str and is_translucent(block_str):
            alpha = block_alpha(block_str)
            rgba = (rgba[0], rgba[1], rgba[2], alpha)
        colors_json[str(int(role))] = [float(v) for v in rgba]

    W, H, L = grid.shape
    return jsonify(
        {
            "dims": [int(W), int(H), int(L)],
            "count": int(xs.size),
            "voxels": b64,
            "colors": colors_json,
        }
    )


# --- JSON API ---------------------------------------------------------------

# Representative roles to include in the palette color preview.
_PREVIEW_ROLES = ("HULL", "WINDOW", "ENGINE_GLOW", "WING")

# Module-level cache: palette name -> {role_name: "#rrggbb"}.
_PALETTE_COLORS_CACHE: dict[str, dict[str, str]] | None = None


def _rgba_to_hex(r: float, g: float, b: float, a: float) -> str:  # noqa: ANN001
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _build_palette_colors_cache() -> dict[str, dict[str, str]]:
    """Load all palettes once and return a nested dict of preview hex colors."""
    result: dict[str, dict[str, str]] = {}
    for name in list_palettes():
        try:
            palette = load_palette(name)
        except Exception:  # noqa: BLE001
            continue
        role_map: dict[str, str] = {}
        for role_name in _PREVIEW_ROLES:
            try:
                role = Role[role_name]
            except KeyError:
                continue
            rgba = palette.preview_colors.get(role)
            if rgba is None:
                continue
            role_map[role_name] = _rgba_to_hex(*rgba)
        result[name] = role_map
    return result


@ship_bp.route("/api/palettes", methods=["GET"], endpoint="api_palettes")
def api_palettes():
    global _PALETTE_COLORS_CACHE
    if _PALETTE_COLORS_CACHE is None:
        _PALETTE_COLORS_CACHE = _build_palette_colors_cache()
    return jsonify({"palettes": list_palettes(), "colors": _PALETTE_COLORS_CACHE})


@ship_bp.route("/api/palettes/<string:name>", methods=["GET"], endpoint="api_palette_detail")
def api_palette_detail(name: str):
    try:
        pal = load_palette(name)
    except Exception:  # noqa: BLE001
        return jsonify({"error": f"palette {name!r} not found"}), 404
    return jsonify({
        "name": pal.name,
        "roles": {role.name: str(block) for role, block in pal.blocks.items()},
        "preview_colors": {
            role.name: _rgba_to_hex(*rgba)
            for role, rgba in pal.preview_colors.items()
        },
    })


@ship_bp.route("/api/generate", methods=["POST"], endpoint="api_generate")
def api_generate():
    limited = check_rate_limit(as_json=True)
    if limited is not None:
        return limited
    st = state()
    payload = request.get_json(silent=True) or {}
    try:
        seed, palette_name, shape_params, texture_params, extra_gen_kwargs = (
            build_params_from_source(payload)
        )

        # Preview PNG is rendered lazily by the /preview/<id>.png route
        # when a consumer actually fetches it. The default web flow now
        # uses the WebGL canvas and /voxels/<id>.json instead.
        result = _generate_with_extras(
            seed,
            palette=palette_name,
            shape_params=shape_params,
            texture_params=texture_params,
            out_dir=st.out_dir(),
            with_preview=False,
            extra_gen_kwargs=extra_gen_kwargs,
        )
    except (ValueError, FileNotFoundError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    gen_id = st.store(result)
    return jsonify(
        {
            "seed": result.seed,
            "palette": result.palette_name,
            "shape": list(result.shape),
            "blocks": result.block_count,
            "download_url": url_for("download", gen_id=gen_id),
            "preview_url": url_for("preview", gen_id=gen_id),
            "gen_id": gen_id,
        }
    )


@ship_bp.route("/api/batch", methods=["POST"], endpoint="api_batch")
def api_batch():
    limited = check_rate_limit(as_json=True)
    if limited is not None:
        return limited
    st = state()
    payload = request.get_json(silent=True) or {}
    count = payload.get("count", 1)
    if not isinstance(count, int) or count < 1 or count > 10:
        return jsonify({"error": "count must be an integer 1\u201310"}), 400

    ships = []
    base_seed = payload.get("seed")
    for i in range(count):
        item = dict(payload)
        item.pop("count", None)
        if base_seed is None:
            item.pop("seed", None)  # let build_params_from_source pick random
        else:
            item["seed"] = base_seed + i  # deterministic range from base_seed
        try:
            seed, palette_name, shape_params, texture_params, extra_gen_kwargs = (
                build_params_from_source(item)
            )
            result = _generate_with_extras(
                seed,
                palette=palette_name,
                shape_params=shape_params,
                texture_params=texture_params,
                out_dir=st.out_dir(),
                with_preview=False,
                extra_gen_kwargs=extra_gen_kwargs,
            )
        except (ValueError, FileNotFoundError, TypeError) as exc:
            return jsonify({"error": str(exc), "ship_index": i}), 400
        gen_id = st.store(result)
        ships.append({
            "seed": result.seed,
            "palette": result.palette_name,
            "shape": list(result.shape),
            "blocks": result.block_count,
            "download_url": url_for("download", gen_id=gen_id),
            "preview_url": url_for("preview", gen_id=gen_id),
            "gen_id": gen_id,
        })
    return jsonify({"ships": ships, "count": len(ships)})


@ship_bp.route("/api/result/<gen_id>", methods=["GET"], endpoint="api_result")
def api_result(gen_id: str):
    result = state().get(gen_id)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "gen_id": gen_id,
        "seed": result.seed,
        "palette": result.palette_name,
        "shape": list(result.shape),
        "blocks": result.block_count,
        "filename": Path(result.litematic_path).name,
        "download_url": url_for("download", gen_id=gen_id),
        "preview_url": url_for("preview", gen_id=gen_id),
    })


# --- /api/meta --------------------------------------------------------------
# Lightweight UI metadata endpoint. Used by the sci-fi console frontend
# (Alpine.js-driven presets / control panel) to render palette/cockpit/
# structure choices and defaults without re-scraping the index HTML.
# Reuses the same data sources as ``index()`` so drift between the Jinja
# template and this API is impossible.
@ship_bp.route("/api/meta", methods=["GET"], endpoint="api_meta")
def api_meta():
    # ``param_help`` may in theory be None at import time (e.g. if a
    # consumer monkey-patches it to clear tooltips); fall back to empty.
    help_map = PARAM_HELP if isinstance(PARAM_HELP, dict) else {}

    # Import version lazily with a defensive fallback. A broken or missing
    # package metadata must not break this endpoint.
    try:
        from ... import __version__ as _pkg_version  # type: ignore
        version = str(_pkg_version) or "dev"
    except Exception:  # pragma: no cover - defensive
        version = "dev"

    return jsonify(
        {
            "palettes": list_palettes(),
            "presets": presets.list_presets(),
            "cockpit_styles": [c.value for c in CockpitStyle],
            "structure_styles": [s.value for s in StructureStyle],
            "wing_styles": [w.value for w in WingStyle],
            "hull_styles": [h.value for h in HullStyle],
            "engine_styles": [e.value for e in EngineStyle],
            "weapon_types": [w.value for w in WeaponType],
            "param_help": dict(help_map),
            "defaults": {
                "seed": 42,
                "palette": "sci_fi_industrial",
                "length": 40,
                "width": 20,
                "height": 12,
                "engines": 2,
                "wing_prob": 0.75,
                "greeble_density": 0.0,
                "window_period": 4,
                "accent_stripe_period": 8,
                "engine_glow_depth": 1,
                "hull_noise_ratio": 0.0,
                "panel_line_bands": 1,
                "rivet_period": 0,
                "engine_glow_ring": False,
                "cockpit": CockpitStyle.BUBBLE.value,
                "structure_style": StructureStyle.FRIGATE.value,
                "wing_style": WingStyle.STRAIGHT.value,
                "hull_style": "auto",
                "engine_style": "auto",
            },
            "version": version,
            "batch_max": 10,
        }
    )


@ship_bp.route("/api/health", methods=["GET"], endpoint="api_health")
def api_health():
    try:
        from ... import __version__ as _pkg_version  # type: ignore
        version = str(_pkg_version) or "dev"
    except Exception:  # pragma: no cover - defensive
        version = "dev"

    return jsonify(
        {
            "status": "ok",
            "version": version,
            "palette_count": len(list_palettes()),
            "preset_count": len(presets.list_presets()),
        }
    )


@ship_bp.route("/api/presets", methods=["GET"], endpoint="api_presets")
def api_presets():
    """Return full metadata for every named preset as JSON.

    Response shape::

        {
          "presets": [
            {
              "name": "corvette",
              "hull_style": "dagger",
              "engine_style": "twin_nacelle",
              "wing_style": "swept",
              "cockpit_style": "bubble",
              "greeble_density": 0.1,
              "weapon_count": 2,
              "weapon_types": ["turret_large", "point_defense"],
              "size": {"width": 20, "height": 12, "length": 50}
            },
            ...
          ]
        }

    Enum values are serialised as their ``.value`` strings (lowercase
    snake_case) matching the convention used by ``/api/meta``.
    """
    result = []
    for name in presets.list_presets():
        spec = presets.SHIP_PRESETS[name]
        width, height, length = spec["size"]
        result.append({
            "name": name,
            "description": spec["description"],
            "hull_style": spec["hull_style"].value,
            "engine_style": spec["engine_style"].value,
            "wing_style": spec["wing_style"].value,
            "cockpit_style": spec["cockpit_style"].value,
            "greeble_density": float(spec["greeble_density"]),
            "weapon_count": int(spec["weapon_count"]),
            "weapon_types": [wt.value for wt in spec["weapon_types"]],
            "size": {"width": width, "height": height, "length": length},
        })
    return jsonify({"presets": result})


@ship_bp.route("/api/presets/<string:name>", methods=["GET"], endpoint="api_preset_detail")
def api_preset_detail(name: str):
    """Return full metadata for a single named preset.

    Response shape mirrors one entry from ``/api/presets``::

        {
          "name": "corvette",
          "description": "Fast light warship ...",
          "hull_style": "dagger",
          "engine_style": "twin_nacelle",
          "wing_style": "swept",
          "cockpit_style": "bubble",
          "greeble_density": 0.1,
          "weapon_count": 2,
          "weapon_types": ["turret_large", "point_defense"],
          "size": {"width": 20, "height": 12, "length": 50}
        }

    Returns 404 if the preset name is not recognised, 503 if the presets
    module failed to import.
    """
    if not hasattr(presets, "SHIP_PRESETS"):
        return jsonify({"error": "presets unavailable"}), 503
    spec = presets.SHIP_PRESETS.get(name)
    if spec is None:
        return jsonify({"error": "preset not found", "name": name}), 404
    width, height, length = spec["size"]
    return jsonify({
        "name": name,
        "description": spec["description"],
        "hull_style": spec["hull_style"].value,
        "engine_style": spec["engine_style"].value,
        "wing_style": spec["wing_style"].value,
        "cockpit_style": spec["cockpit_style"].value,
        "greeble_density": float(spec["greeble_density"]),
        "weapon_count": int(spec["weapon_count"]),
        "weapon_types": [wt.value for wt in spec["weapon_types"]],
        "size": {"width": width, "height": height, "length": length},
    })


# --- /download-fleet --------------------------------------------------------
# Bulk "plan-and-pack-a-fleet" endpoint. Given a seed + palette + count + size
# tier + coherence, plan N ships via ``fleet.generate_fleet``, run each through
# ``generate()`` into a scratch dir, then stream the .litematic files back as
# a single zip. Kept as a GET so the frontend can just drop a link; the
# download is still subject to the per-IP rate limiter.


# ZipFile mtimes influence the raw bytes of the archive. Fix the per-entry
# timestamp to a constant so the zip envelope is byte-deterministic for the
# same seed + params. The underlying .litematic payloads come from litemapy,
# which writes its own gzip stream with its own mtime inside each file — so
# we still only assert filename + size equality across two calls, not full
# byte equality.
_ZIP_FIXED_MTIME = (2020, 1, 1, 0, 0, 0)

_ALLOWED_SIZE_TIERS = frozenset(set(SIZE_TIERS) | {"mixed"})


def _parse_download_fleet_args(args) -> tuple[int, str, int, str, float]:
    """Parse + validate ``/download-fleet`` query params.

    Returns ``(seed, palette, count, size_tier, coherence)``. Raises
    :class:`ValueError` on any bad input so the caller can map to a 400.

    Parameter contract:
    * ``count``    — int in ``[1, 20]`` (1 minimum so we never pack an empty
                     zip; 20 upper bound bounds generation cost per request).
    * ``size_tier``— one of ``SIZE_TIERS.keys()`` ∪ ``{"mixed"}``.
    * ``style_coherence`` — float in ``[0.0, 1.0]``.
    * ``palette``  — must resolve via ``load_palette``; unknown name → 400.
    * ``seed``     — int, defaults to 0 (matching the rest of the web surface).
    """
    try:
        seed = int(args.get("seed") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"seed must be an integer; got {args.get('seed')!r}"
        ) from exc

    palette_name = (args.get("palette") or "sci_fi_industrial").strip()
    if not palette_name:
        raise ValueError("palette must be a non-empty string")
    # Confirm the palette actually resolves before we spend any generate()
    # cycles. load_palette raises FileNotFoundError / ValueError for missing
    # or malformed YAML; either maps to a 400.
    try:
        load_palette(palette_name)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    raw_count = args.get("count", "1")
    try:
        count = int(float(raw_count))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"count must be an integer; got {raw_count!r}") from exc
    if not 1 <= count <= 20:
        raise ValueError(f"count must be in [1, 20]; got {count}")

    size_tier = (args.get("size_tier") or "mixed").strip().lower()
    if size_tier not in _ALLOWED_SIZE_TIERS:
        allowed = sorted(_ALLOWED_SIZE_TIERS)
        raise ValueError(
            f"size_tier must be one of {allowed}; got {size_tier!r}"
        )

    raw_coherence = args.get("style_coherence", "0.7")
    try:
        coherence = float(raw_coherence)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"style_coherence must be a float; got {raw_coherence!r}"
        ) from exc
    if not 0.0 <= coherence <= 1.0:
        raise ValueError(
            f"style_coherence must be in [0.0, 1.0]; got {coherence}"
        )

    return seed, palette_name, count, size_tier, coherence


@ship_bp.route("/api/fleet/plan", methods=["GET"], endpoint="fleet_plan")
def fleet_plan():
    """Return JSON metadata for a planned fleet without generating any files.

    Query params (all optional):

    * ``seed``       — int, default 0.
    * ``palette``    — palette name, default ``sci_fi_industrial``. Must exist.
    * ``count``      — int 1–10, default 3.
    * ``size_tier``  — ``small``/``mid``/``large``/``capital``/``mixed``, default ``mid``.
    * ``coherence``  — float 0.0–1.0, default 0.8.

    Returns 200 JSON with fleet metadata on success, 400 JSON ``{"error": "..."}``
    for invalid params.
    """
    # --- seed ---
    try:
        seed = int(request.args.get("seed") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": f"seed must be an integer; got {request.args.get('seed')!r}"}), 400

    # --- palette ---
    palette_name = (request.args.get("palette") or "sci_fi_industrial").strip()
    if not palette_name:
        return jsonify({"error": "palette must be a non-empty string"}), 400
    if palette_name not in list_palettes():
        return jsonify({"error": f"unknown palette {palette_name!r}"}), 400

    # --- count ---
    raw_count = request.args.get("count", "3")
    try:
        count = int(float(raw_count))
    except (TypeError, ValueError):
        return jsonify({"error": f"count must be an integer; got {raw_count!r}"}), 400
    if not 1 <= count <= 10:
        return jsonify({"error": f"count must be in [1, 10]; got {count}"}), 400

    # --- size_tier ---
    size_tier = (request.args.get("size_tier") or "mid").strip().lower()
    if size_tier not in _ALLOWED_SIZE_TIERS:
        allowed = sorted(_ALLOWED_SIZE_TIERS)
        return jsonify({"error": f"size_tier must be one of {allowed}; got {size_tier!r}"}), 400

    # --- coherence ---
    raw_coherence = request.args.get("coherence", "0.8")
    try:
        coherence = float(raw_coherence)
    except (TypeError, ValueError):
        return jsonify({"error": f"coherence must be a float; got {raw_coherence!r}"}), 400
    if not 0.0 <= coherence <= 1.0:
        return jsonify({"error": f"coherence must be in [0.0, 1.0]; got {coherence}"}), 400

    fleet_params = FleetParams(
        count=count,
        palette=palette_name,
        size_tier=size_tier,
        style_coherence=coherence,
        seed=seed,
    )
    try:
        ships = generate_fleet(fleet_params)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    ships_json = []
    for idx, ship in enumerate(ships):
        ships_json.append({
            "index": idx,
            "seed": ship.seed,
            "hull_style": ship.hull_style.value if ship.hull_style else None,
            "engine_style": ship.engine_style.value if ship.engine_style else None,
            "wing_style": ship.wing_style.value if ship.wing_style else None,
            "cockpit_style": ship.cockpit_style.value if ship.cockpit_style else None,
            "greeble_density": float(ship.greeble_density),
            "weapon_count": int(ship.weapon_count),
            "dims": {
                "width": ship.dims[0],
                "height": ship.dims[1],
                "length": ship.dims[2],
            },
        })

    return jsonify({
        "seed": seed,
        "palette": palette_name,
        "count": count,
        "size_tier": size_tier,
        "coherence": coherence,
        "ships": ships_json,
    })


@ship_bp.route("/api/compare", methods=["GET"], endpoint="compare")
def api_compare():
    """Compare two ships by seed — returns metadata side-by-side without generating files."""
    # seed_a
    raw_a = request.args.get("seed_a")
    if raw_a is None:
        return jsonify({"error": "seed_a is required"}), 400
    try:
        seed_a = int(raw_a)
    except (TypeError, ValueError):
        return jsonify({"error": f"seed_a must be an integer; got {raw_a!r}"}), 400
    # seed_b
    raw_b = request.args.get("seed_b")
    if raw_b is None:
        return jsonify({"error": "seed_b is required"}), 400
    try:
        seed_b = int(raw_b)
    except (TypeError, ValueError):
        return jsonify({"error": f"seed_b must be an integer; got {raw_b!r}"}), 400
    # palette
    palette_name = (request.args.get("palette") or "sci_fi_industrial").strip()
    if palette_name not in list_palettes():
        return jsonify({"error": f"unknown palette {palette_name!r}"}), 400
    # shape params (default or from preset)
    preset_name = request.args.get("preset")
    shape_params = ShapeParams()
    if preset_name:
        if preset_name not in presets.SHIP_PRESETS:
            return jsonify({"error": f"unknown preset {preset_name!r}"}), 400
        spec = presets.SHIP_PRESETS[preset_name]
        width, height, length = spec["size"]
        shape_params = ShapeParams(
            length=length,
            width_max=width,
            height_max=height,
        )
    try:
        meta_a = _ship_metadata(seed_a, shape_params, palette_name)
        meta_b = _ship_metadata(seed_b, shape_params, palette_name)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"palette": palette_name, "ship_a": meta_a, "ship_b": meta_b})


@ship_bp.route("/download-fleet", methods=["GET"], endpoint="download_fleet")
def download_fleet():
    """Plan ``count`` ships and stream them back as one zip of ``.litematic``.

    Query params (all optional except where noted):

    * ``seed`` — int seed for fleet planning (default 0).
    * ``palette`` — palette name (default ``sci_fi_industrial``). Must exist.
    * ``count`` — 1-20 ships (enforced).
    * ``size_tier`` — ``small``/``mid``/``large``/``capital``/``mixed``.
    * ``style_coherence`` — 0-1, passed straight through to ``FleetParams``.

    Returns ``application/zip`` with
    ``Content-Disposition: attachment; filename=fleet_<seed>_<palette>.zip``.

    Error surface:
    * Bad params → 400 JSON ``{"error": "..."}``.
    * Generation failure (e.g. palette blew up mid-pipeline) → 500 JSON.
    * Rate-limited → 429 from :func:`check_rate_limit`.
    """
    limited = check_rate_limit(as_json=True)
    if limited is not None:
        return limited

    try:
        seed, palette_name, count, size_tier, coherence = (
            _parse_download_fleet_args(request.args)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    fleet_params = FleetParams(
        count=count,
        palette=palette_name,
        size_tier=size_tier,
        style_coherence=coherence,
        seed=seed,
    )
    try:
        ships = generate_fleet(fleet_params)
    except ValueError as exc:
        # Should not hit given the validation above, but FleetParams itself
        # re-validates and could drift. Treat as 400 so the client can fix
        # the request.
        return jsonify({"error": str(exc)}), 400

    # Generate every ship into a fresh scratch dir so concurrent fleet
    # downloads can't overwrite each other's ship_<seed>.litematic files.
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="fleet_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            results = []
            for idx, ship in enumerate(ships):
                w, h, length = ship.dims
                shape_params = ShapeParams(
                    length=length,
                    width_max=w,
                    height_max=h,
                    wing_style=ship.wing_style,
                )
                # Per-ship filename. Prefix with the fleet index so two ships
                # that happen to draw the same seed from the fleet RNG still
                # get distinct zip entries.
                filename = f"ship_{idx:02d}_{ship.seed}.litematic"
                result = generate(
                    seed=ship.seed,
                    palette=palette_name,
                    shape_params=shape_params,
                    out_dir=tmp_path,
                    filename=filename,
                    with_preview=False,
                    hull_style=ship.hull_style,
                    engine_style=ship.engine_style,
                    greeble_density=ship.greeble_density,
                )
                results.append(result)
        except (ValueError, FileNotFoundError, OSError) as exc:
            # Anything that trips mid-pipeline (bad palette at load time,
            # corrupt YAML, disk full) is a 500 — the request was shaped
            # correctly but the server failed to satisfy it.
            return jsonify({"error": f"fleet generation failed: {exc}"}), 500

        # Pack results into an in-memory zip. Use ZIP_DEFLATED so the zip is
        # noticeably smaller than a stored-only pack — .litematic payloads
        # are already gzipped inside, so compression gains are modest but
        # non-zero on entry metadata + filenames.
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for result in results:
                path = Path(result.litematic_path)
                info = zipfile.ZipInfo(
                    filename=path.name,
                    date_time=_ZIP_FIXED_MTIME,
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, path.read_bytes())

    buf.seek(0)
    safe_palette = "".join(
        ch for ch in palette_name if ch.isalnum() or ch in "_-"
    )
    download_name = f"fleet_{seed}_{safe_palette or 'palette'}.zip"
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )


__all__ = ["ship_bp"]
