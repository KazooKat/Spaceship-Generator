"""Core generation routes: HTML form flow + JSON API + metadata + voxels/preview.

All routes live on a single ``ship`` blueprint. Helpers, constants, and
shared state plumbing live in ``ship_support`` so this module stays
focused on HTTP handling.
"""

from __future__ import annotations

import base64
import io
import random

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

from ...block_colors import block_alpha, is_translucent
from ...generator import generate
from ...palette import Role, list_palettes, load_palette
from ...shape import CockpitStyle, StructureStyle
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


@ship_bp.route("/", endpoint="index")
def index():
    return render_template(
        "index.html",
        palettes=list_palettes(),
        cockpit_styles=[c.value for c in CockpitStyle],
        structure_styles=[s.value for s in StructureStyle],
        wing_styles=[w.value for w in WingStyle],
        param_help=PARAM_HELP,
        defaults={
            "seed": random.randint(0, 2**31 - 1),
            "palette": "sci_fi_industrial",
            "length": 40,
            "width": 20,
            "height": 12,
            "engines": 2,
            "wing_prob": 0.75,
            "greeble_density": 0.05,
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
        seed, palette_name, shape_params, texture_params = (
            build_params_from_source(request.form)
        )

        # Skip eager matplotlib render: the client uses the WebGL canvas
        # which pulls voxel data from ``/voxels/<gen_id>.json``. The
        # ``/preview/<gen_id>.png`` route still works, but renders lazily.
        result = generate(
            seed,
            palette=palette_name,
            shape_params=shape_params,
            texture_params=texture_params,
            out_dir=st.out_dir(),
            with_preview=False,
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
                cockpit_styles=[c.value for c in CockpitStyle],
                structure_styles=[s.value for s in StructureStyle],
                wing_styles=[w.value for w in WingStyle],
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


@ship_bp.route("/api/palettes", methods=["GET"], endpoint="api_palettes")
def api_palettes():
    return jsonify({"palettes": list_palettes()})


@ship_bp.route("/api/generate", methods=["POST"], endpoint="api_generate")
def api_generate():
    limited = check_rate_limit(as_json=True)
    if limited is not None:
        return limited
    st = state()
    payload = request.get_json(silent=True) or {}
    try:
        seed, palette_name, shape_params, texture_params = (
            build_params_from_source(payload)
        )

        # Preview PNG is rendered lazily by the /preview/<id>.png route
        # when a consumer actually fetches it. The default web flow now
        # uses the WebGL canvas and /voxels/<id>.json instead.
        result = generate(
            seed,
            palette=palette_name,
            shape_params=shape_params,
            texture_params=texture_params,
            out_dir=st.out_dir(),
            with_preview=False,
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
            "cockpit_styles": [c.value for c in CockpitStyle],
            "structure_styles": [s.value for s in StructureStyle],
            "wing_styles": [w.value for w in WingStyle],
            "param_help": dict(help_map),
            "defaults": {
                "seed": 42,
                "palette": "sci_fi_industrial",
                "length": 40,
                "width": 20,
                "height": 12,
                "engines": 2,
                "wing_prob": 0.75,
                "greeble_density": 0.05,
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
            },
            "version": version,
        }
    )


__all__ = ["ship_bp"]
