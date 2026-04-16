"""Flask web UI for Spaceship Generator.

Run with::

    flask --app spaceship_generator.web.app run
"""

from __future__ import annotations

import io
import random
import uuid
from collections import OrderedDict
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    redirect,
    send_file,
    url_for,
)

import re

from ..block_colors import approximate_block_color, block_texture_png, hex_to_rgba
from ..generator import GenerationResult, generate
from ..palette import Palette, Role, list_palettes, load_palette
from ..shape import CockpitStyle, ShapeParams
from ..texture import TextureParams


_DEFAULT_MAX_RESULTS = 100

# Accept namespaced block ids, with optional state spec (e.g. ``[lit=true]``).
# Matches what ``block_colors._BLOCKID_RE`` accepts so the route can safely
# round-trip the block ids produced by the palette key.
_BLOCKID_URL_RE = re.compile(r"^[A-Za-z0-9_:\-\[\]=,]+$")


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


def _rgba_to_hex(rgba: tuple[float, float, float, float]) -> str:
    r, g, b, _a = rgba
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(r * 255)))),
        max(0, min(255, int(round(g * 255)))),
        max(0, min(255, int(round(b * 255)))),
    )


def _approximate_role_colors(
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


def _palette_key(palette_name: str) -> list[dict]:
    """Return a list of legend entries for ``palette_name``.

    Each entry is ``{role, label, color, block, hex}``. ``color`` is the
    approximated Minecraft block color (or stylized fallback); ``hex`` is its
    string form shown alongside the block id. If the palette can't be loaded,
    returns an empty list.
    """
    try:
        pal = load_palette(palette_name)
    except (FileNotFoundError, ValueError):
        return []
    approx = _approximate_role_colors(pal)
    entries: list[dict] = []
    for role in Role:
        if role == Role.EMPTY:
            continue
        block = pal.blocks.get(role)
        color_rgba = approx.get(role, (0.5, 0.5, 0.5, 1.0))
        color_hex = _rgba_to_hex(color_rgba)
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


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.setdefault("MAX_RESULTS", _DEFAULT_MAX_RESULTS)
    results: "OrderedDict[str, GenerationResult]" = OrderedDict()

    def _cleanup_result(result: GenerationResult) -> None:
        """Delete the on-disk .litematic file for an evicted result."""
        try:
            Path(result.litematic_path).unlink(missing_ok=True)
        except OSError:
            # Best-effort cleanup; do not raise during eviction.
            pass

    def _store(result: GenerationResult) -> str:
        gen_id = uuid.uuid4().hex[:12]
        results[gen_id] = result
        max_results = int(app.config.get("MAX_RESULTS", _DEFAULT_MAX_RESULTS))
        while len(results) > max_results:
            _evicted_id, evicted_result = results.popitem(last=False)
            _cleanup_result(evicted_result)
        return gen_id

    def _out_dir() -> Path:
        d = Path(app.instance_path) / "generated"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _build_params_from_source(source) -> tuple[int, str, ShapeParams, TextureParams]:
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

        shape_params = ShapeParams(
            length=int(source.get("length", 40)),
            width_max=int(source.get("width", 20)),
            height_max=int(source.get("height", 12)),
            engine_count=int(source.get("engines", 2)),
            wing_prob=float(source.get("wing_prob", 0.75)),
            greeble_density=float(source.get("greeble_density", 0.05)),
            cockpit_style=CockpitStyle(
                source.get("cockpit", CockpitStyle.BUBBLE.value)
            ),
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
            hull_noise_ratio=float(source.get("hull_noise_ratio", 0.0)),
            panel_line_bands=int(source.get("panel_line_bands", 1)),
            rivet_period=int(source.get("rivet_period", 0)),
            engine_glow_ring=engine_glow_ring,
        )
        return seed, palette_name, shape_params, texture_params

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            palettes=list_palettes(),
            cockpit_styles=[c.value for c in CockpitStyle],
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
            },
        )

    def _apply_approx_preview(result: GenerationResult) -> None:
        """Replace ``result.preview_png`` with an approximated-color render.

        The bundled palette YAML colors are stylized; this swap makes the
        preview match the actual Minecraft block textures (via cached mcmeta
        samples) so the on-page preview and block key agree.
        """
        try:
            pal = load_palette(result.palette_name)
        except (FileNotFoundError, ValueError):
            return
        from ..preview import render_preview

        result.preview_png = render_preview(
            result.role_grid,
            pal,
            size=(700, 700),
            color_override=_approximate_role_colors(pal),
        )

    def _render_result_partial(gen_id: str, result: GenerationResult) -> str:
        return render_template(
            "_result.html",
            gen_id=gen_id,
            seed=result.seed,
            palette=result.palette_name,
            shape=result.shape,
            blocks=result.block_count,
            filename=result.litematic_path.name,
            key_entries=_palette_key(result.palette_name),
        )

    @app.route("/generate", methods=["POST"])
    def do_generate():
        is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        try:
            seed, palette_name, shape_params, texture_params = (
                _build_params_from_source(request.form)
            )

            result = generate(
                seed,
                palette=palette_name,
                shape_params=shape_params,
                texture_params=texture_params,
                out_dir=_out_dir(),
                with_preview=True,
                preview_size=(700, 700),
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
                    param_help=PARAM_HELP,
                    defaults=request.form.to_dict(),
                    error=str(exc),
                ),
                400,
            )

        _apply_approx_preview(result)
        gen_id = _store(result)
        if is_htmx:
            return _render_result_partial(gen_id, result)
        return redirect(url_for("show_result", gen_id=gen_id))

    @app.route("/result/<gen_id>")
    def show_result(gen_id: str):
        result = results.get(gen_id)
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
            key_entries=_palette_key(result.palette_name),
        )

    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    @app.route("/preview/<gen_id>.png")
    def preview(gen_id: str):
        result = results.get(gen_id)
        if result is None:
            abort(404)

        raw_elev = request.args.get("elev")
        raw_azim = request.args.get("azim")

        # No view override: serve the cached approximated-color PNG.
        if raw_elev is None and raw_azim is None:
            if result.preview_png is None:
                abort(404)
            return send_file(io.BytesIO(result.preview_png), mimetype="image/png")

        try:
            elev = _clamp(float(raw_elev) if raw_elev is not None else 22.0, -89.0, 89.0)
            azim = float(raw_azim) if raw_azim is not None else -62.0
        except ValueError:
            abort(400)

        try:
            pal = load_palette(result.palette_name)
        except (FileNotFoundError, ValueError):
            abort(404)

        # Import lazily — matplotlib is a big import.
        from ..preview import render_preview

        png = render_preview(
            result.role_grid,
            pal,
            size=(700, 700),
            view=(elev, azim),
            color_override=_approximate_role_colors(pal),
        )
        return send_file(io.BytesIO(png), mimetype="image/png")

    @app.route("/block-texture/<path:block_id>.png")
    def block_texture(block_id: str):
        """Serve the cached Minecraft block texture PNG for ``block_id``.

        Only serves textures already on disk — network fetches happen at cache
        bootstrap time, not during request handling. Returns 404 for unknown
        or un-cacheable ids, 400 for malformed ids.
        """
        if not _BLOCKID_URL_RE.fullmatch(block_id):
            abort(400)
        png = block_texture_png(block_id, allow_network=False)
        if png is None:
            abort(404)
        resp = send_file(io.BytesIO(png), mimetype="image/png")
        # Textures are immutable per block_id; cache hard in the browser.
        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
        return resp

    @app.route("/download/<gen_id>")
    def download(gen_id: str):
        result = results.get(gen_id)
        if result is None:
            abort(404)
        return send_file(
            result.litematic_path,
            as_attachment=True,
            download_name=result.litematic_path.name,
            mimetype="application/octet-stream",
        )

    # --- JSON API -----------------------------------------------------------

    @app.route("/api/palettes", methods=["GET"])
    def api_palettes():
        return jsonify({"palettes": list_palettes()})

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        payload = request.get_json(silent=True) or {}
        try:
            seed, palette_name, shape_params, texture_params = (
                _build_params_from_source(payload)
            )

            result = generate(
                seed,
                palette=palette_name,
                shape_params=shape_params,
                texture_params=texture_params,
                out_dir=_out_dir(),
                with_preview=True,
                preview_size=(700, 700),
            )
        except (ValueError, FileNotFoundError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

        _apply_approx_preview(result)
        gen_id = _store(result)
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

    # Expose the in-memory store for tests.
    app.config["_RESULTS"] = results
    return app


# Default ``app`` object for ``flask --app spaceship_generator.web.app``.
app = create_app()
