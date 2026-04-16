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

from ..generator import GenerationResult, generate
from ..palette import list_palettes
from ..shape import CockpitStyle, ShapeParams
from ..texture import TextureParams


_DEFAULT_MAX_RESULTS = 100


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

    @app.route("/generate", methods=["POST"])
    def do_generate():
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
            return (
                render_template(
                    "index.html",
                    palettes=list_palettes(),
                    cockpit_styles=[c.value for c in CockpitStyle],
                    defaults=request.form.to_dict(),
                    error=str(exc),
                ),
                400,
            )

        gen_id = _store(result)
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
        )

    @app.route("/preview/<gen_id>.png")
    def preview(gen_id: str):
        result = results.get(gen_id)
        if result is None or result.preview_png is None:
            abort(404)
        return send_file(io.BytesIO(result.preview_png), mimetype="image/png")

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
