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


_MAX_RESULTS = 100


def create_app() -> Flask:
    app = Flask(__name__)
    results: "OrderedDict[str, GenerationResult]" = OrderedDict()

    def _store(result: GenerationResult) -> str:
        gen_id = uuid.uuid4().hex[:12]
        results[gen_id] = result
        while len(results) > _MAX_RESULTS:
            results.popitem(last=False)
        return gen_id

    def _out_dir() -> Path:
        d = Path(app.instance_path) / "generated"
        d.mkdir(parents=True, exist_ok=True)
        return d

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
                "cockpit": CockpitStyle.BUBBLE.value,
            },
        )

    @app.route("/generate", methods=["POST"])
    def do_generate():
        try:
            seed = int(request.form.get("seed") or 0)
            palette_name = request.form.get("palette", "sci_fi_industrial")

            shape_params = ShapeParams(
                length=int(request.form.get("length", 40)),
                width_max=int(request.form.get("width", 20)),
                height_max=int(request.form.get("height", 12)),
                engine_count=int(request.form.get("engines", 2)),
                wing_prob=float(request.form.get("wing_prob", 0.75)),
                greeble_density=float(request.form.get("greeble_density", 0.05)),
                cockpit_style=CockpitStyle(
                    request.form.get("cockpit", CockpitStyle.BUBBLE.value)
                ),
            )
            texture_params = TextureParams(
                window_period_cells=int(request.form.get("window_period", 4)),
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

    # Expose the in-memory store for tests.
    app.config["_RESULTS"] = results
    return app


# Default ``app`` object for ``flask --app spaceship_generator.web.app``.
app = create_app()
