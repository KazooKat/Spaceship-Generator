"""Flask web UI for Spaceship Generator.

Run with::

    flask --app spaceship_generator.web.app run
"""

from __future__ import annotations

import base64
import io
import math
import os
import random
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import numpy as np

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

from ..block_colors import (
    approximate_block_color,
    block_alpha,
    block_texture_png,
    hex_to_rgba,
    is_translucent,
)
from ..generator import GenerationResult, generate
from ..palette import Palette, Role, list_palettes, load_palette
from ..shape import CockpitStyle, ShapeParams, StructureStyle
from ..texture import TextureParams
from ..wing_styles import WingStyle


_DEFAULT_MAX_RESULTS = 100


# --- Rate limiting -----------------------------------------------------------
#
# Generation is CPU + memory heavy (numpy voxel grid + palette mapping +
# litematic serialization + optional preview PNG). Without a cap, a single
# impatient client holding Enter on Generate can pin the server. The limiter
# is a per-client fixed-window token counter keyed by the best-effort client
# IP, thread-safe under the default Flask dev + gunicorn-sync workers.
#
# Tunables (env vars, both honored on app creation):
#   SHIPFORGE_RATE_LIMIT   — max requests per window per IP (default 10)
#                            set to 0 to disable the limiter entirely
#   SHIPFORGE_RATE_WINDOW  — window length in seconds (default 60)
#
# The limiter does NOT persist across restarts — that's fine for the
# protection we want here (absorb local bursts). A reverse proxy with
# proper throttling (nginx, Cloudflare) should be used in production.


class _RateLimiter:
    """Per-key fixed-window counter. Not a token bucket — simpler and
    adequate for the small-abuse case we care about. Zero deps."""

    def __init__(self, max_requests: int, window_s: float) -> None:
        self.max_requests = int(max_requests)
        self.window_s = float(window_s)
        self._lock = threading.Lock()
        # key -> (window_start_ts, count)
        self._windows: dict[str, tuple[float, int]] = {}
        # Opportunistic GC threshold to bound memory if we see many unique
        # IPs over time.
        self._max_keys = 4096

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is 0 when allowed, otherwise the number of
        seconds until the current window rolls over.
        """
        if self.max_requests <= 0:
            # Disabled: always allow.
            return True, 0.0
        ts = now if now is not None else time.monotonic()
        with self._lock:
            start, count = self._windows.get(key, (ts, 0))
            elapsed = ts - start
            if elapsed >= self.window_s:
                # Fresh window.
                self._windows[key] = (ts, 1)
                self._maybe_gc(ts)
                return True, 0.0
            if count < self.max_requests:
                self._windows[key] = (start, count + 1)
                return True, 0.0
            retry = max(0.0, self.window_s - elapsed)
            return False, retry

    def _maybe_gc(self, ts: float) -> None:
        # Called under the lock. Drops stale windows if the dict is big.
        if len(self._windows) < self._max_keys:
            return
        cutoff = ts - self.window_s
        stale = [k for k, (start, _) in self._windows.items() if start < cutoff]
        for k in stale:
            self._windows.pop(k, None)


# IPs that should never be rate-limited. Loopback covers local dev
# against the Flask dev server or a local gunicorn — hammering
# Generate while iterating shouldn't lock the developer out for a
# whole window. Production deployments behind a proxy see the real
# client IP via X-Forwarded-For, so loopback here really does mean
# "same machine as the server" and is safe to exempt.
_RATE_LIMIT_EXEMPT_IPS = frozenset({
    "127.0.0.1", "::1", "localhost",
})


def _client_ip_key() -> str:
    """Best-effort client key for rate limiting. Honors X-Forwarded-For's
    first hop (common behind a reverse proxy); falls back to
    ``request.remote_addr``; finally uses the literal "anon" bucket so we
    still have *some* cap even when the request has no address."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        head = xff.split(",", 1)[0].strip()
        if head:
            return head
    return request.remote_addr or "anon"


def _is_rate_limit_exempt(key: str) -> bool:
    """True when the resolved client key is a loopback address and
    should bypass the limiter. Kept as a separate hook so tests can
    still exercise the 429 path by passing non-loopback
    X-Forwarded-For headers."""
    return key in _RATE_LIMIT_EXEMPT_IPS

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
        # FileNotFoundError: palette YAML missing on disk.
        # ValueError: malformed YAML, missing required keys, or unparseable
        # block/color specs — all surfaced by ``Palette.load``.
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

    # Rate limiter — per-app instance so tests get fresh state.
    # Default raised from 10 → 30/min after dev-loop hit the cap during
    # normal iteration. 30 covers burst-use of the Random button and
    # leaves enough headroom that a developer holding the UI rarely
    # notices the limiter while still stopping true abuse.
    try:
        _rate_max = int(os.environ.get("SHIPFORGE_RATE_LIMIT", "30"))
    except ValueError:
        _rate_max = 30
    try:
        _rate_window = float(os.environ.get("SHIPFORGE_RATE_WINDOW", "60"))
    except ValueError:
        _rate_window = 60.0
    app.config.setdefault("RATE_LIMIT_MAX", _rate_max)
    app.config.setdefault("RATE_LIMIT_WINDOW", _rate_window)
    rate_limiter = _RateLimiter(_rate_max, _rate_window)
    # Exposed for tests that want to reset state between cases.
    app.extensions["shipforge_rate_limiter"] = rate_limiter

    def _rate_limited_response(retry_after: float, *, as_json: bool):
        """Build a 429 response with a ``Retry-After`` header. ``retry_after``
        is rounded UP to the next whole second per RFC 9110."""
        retry_s = max(1, int(math.ceil(retry_after)))
        if as_json:
            resp = jsonify({
                "error": "rate_limited",
                "retry_after": retry_s,
                "limit": rate_limiter.max_requests,
                "window_seconds": int(rate_limiter.window_s),
            })
        else:
            is_htmx = request.headers.get("HX-Request", "").lower() == "true"
            msg = (
                f"Too many generations — slow down. Try again in {retry_s}s."
            )
            if is_htmx:
                resp = app.response_class(
                    render_template("_error.html", error=msg),
                    mimetype="text/html",
                )
            else:
                resp = app.response_class(msg, mimetype="text/plain")
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_s)
        return resp

    def _check_rate_limit(*, as_json: bool):
        """Return a 429 response if the request is over the limit, else
        None to let the view proceed."""
        key = _client_ip_key()
        if _is_rate_limit_exempt(key):
            return None
        allowed, retry = rate_limiter.check(key)
        if allowed:
            return None
        return _rate_limited_response(retry, as_json=as_json)

    results: "OrderedDict[str, GenerationResult]" = OrderedDict()
    # Guards the insert + eviction loop in ``_store``. ``OrderedDict`` is not
    # safe for concurrent mutation under a threaded WSGI server — without this
    # lock, two simultaneous ``_store`` calls can double-evict (each thread
    # sees ``len(results) > max`` after both inserts) or corrupt the LRU order.
    _store_lock = threading.Lock()

    def _cleanup_result(result: GenerationResult) -> None:
        """Delete the on-disk .litematic file for an evicted result."""
        try:
            Path(result.litematic_path).unlink(missing_ok=True)
        except OSError:
            # Best-effort cleanup; do not raise during eviction.
            pass

    def _store(result: GenerationResult) -> str:
        gen_id = uuid.uuid4().hex[:12]
        max_results = int(app.config.get("MAX_RESULTS", _DEFAULT_MAX_RESULTS))
        evicted: list[GenerationResult] = []
        with _store_lock:
            results[gen_id] = result
            while len(results) > max_results:
                _evicted_id, evicted_result = results.popitem(last=False)
                evicted.append(evicted_result)
        # Disk I/O outside the lock — the OrderedDict is already consistent.
        for evicted_result in evicted:
            _cleanup_result(evicted_result)
        return gen_id

    def _out_dir() -> Path:
        d = Path(app.instance_path) / "generated"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _finite_float(source, key: str, default: float) -> float:
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

    @app.route("/")
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

    def _render_default_preview(result: GenerationResult) -> bytes | None:
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
        from ..preview import render_preview

        return render_preview(
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
        limited = _check_rate_limit(as_json=False)
        if limited is not None:
            return limited
        is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        try:
            seed, palette_name, shape_params, texture_params = (
                _build_params_from_source(request.form)
            )

            # Skip eager matplotlib render: the client uses the WebGL canvas
            # which pulls voxel data from ``/voxels/<gen_id>.json``. The
            # ``/preview/<gen_id>.png`` route still works, but renders lazily.
            result = generate(
                seed,
                palette=palette_name,
                shape_params=shape_params,
                texture_params=texture_params,
                out_dir=_out_dir(),
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

        # No view override: lazily render and cache the approximated-color
        # default-view PNG. The WebGL canvas makes this route unnecessary for
        # the normal UI flow — it remains for no-WebGL fallback and scripting.
        if raw_elev is None and raw_azim is None:
            if result.preview_png is None:
                png = _render_default_preview(result)
                if png is None:
                    abort(404)
                result.preview_png = png
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

    @app.route("/voxels/<gen_id>.json")
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
        result = results.get(gen_id)
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
        approx = _approximate_role_colors(pal)
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
        # The .litematic file can disappear from disk between generation and
        # download (LRU eviction of an earlier id that shared the same temp
        # tree, manual cleanup, etc.). Treat it as 404 rather than letting
        # ``send_file`` crash with a 500.
        if not Path(result.litematic_path).exists():
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
        limited = _check_rate_limit(as_json=True)
        if limited is not None:
            return limited
        payload = request.get_json(silent=True) or {}
        try:
            seed, palette_name, shape_params, texture_params = (
                _build_params_from_source(payload)
            )

            # Preview PNG is rendered lazily by the /preview/<id>.png route
            # when a consumer actually fetches it. The default web flow now
            # uses the WebGL canvas and /voxels/<id>.json instead.
            result = generate(
                seed,
                palette=palette_name,
                shape_params=shape_params,
                texture_params=texture_params,
                out_dir=_out_dir(),
                with_preview=False,
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

    # --- /api/meta ----------------------------------------------------------
    # Lightweight UI metadata endpoint. Used by the sci-fi console frontend
    # (Alpine.js-driven presets / control panel) to render palette/cockpit/
    # structure choices and defaults without re-scraping the index HTML.
    # Reuses the same data sources as ``index()`` so drift between the Jinja
    # template and this API is impossible.
    @app.route("/api/meta", methods=["GET"])
    def api_meta():
        # ``param_help`` may in theory be None at import time (e.g. if a
        # consumer monkey-patches it to clear tooltips); fall back to empty.
        help_map = PARAM_HELP if isinstance(PARAM_HELP, dict) else {}

        # Import version lazily with a defensive fallback. A broken or missing
        # package metadata must not break this endpoint.
        try:
            from .. import __version__ as _pkg_version  # type: ignore
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

    # --- 404 handler (JSON for API clients) --------------------------------
    # When the caller prefers JSON (e.g. ``fetch('/api/meta')`` with default
    # Accept or explicit ``application/json``), return a structured error
    # body instead of the Jinja-rendered HTML 404 page. HTML clients still
    # get Flask's default 404 page — this only specializes the JSON case.
    @app.errorhandler(404)
    def _not_found(_exc):
        accept = request.accept_mimetypes
        best = accept.best_match(["application/json", "text/html"])
        if best == "application/json" and accept[best] >= accept["text/html"]:
            return (
                jsonify({"error": "not_found", "path": request.path}),
                404,
            )
        # Fall through to Flask's default 404 rendering.
        return ("Not Found", 404)

    # --- CSP / security headers + cache-control ----------------------------
    # Single after_request hook handles both concerns:
    # 1. Adds a CSP that allows the CDN scripts the sci-fi console frontend
    #    loads (htmx, Alpine.js, Lucide) and Google Fonts. Gated by the
    #    ``SHIPFORGE_CSP`` env var (defaults to enabled; set to ``0`` to
    #    disable during dev experimentation with inline/unsafe code).
    # 2. Adds a short 5-minute Cache-Control to ``/static/`` responses when
    #    none is already set (the /block-texture/ route sets its own long
    #    immutable header and is left alone).
    #
    # KNOWN RELAXATIONS:
    # * ``'unsafe-inline'`` (script-src + style-src): htmx hx-* inline attrs,
    #   Alpine ``x-data`` / ``@click`` directives, and inline ``<style>`` blocks
    #   are used throughout the templates.
    # * ``'unsafe-eval'`` (script-src): Alpine.js evaluates reactive
    #   expressions via ``new Function(...)``, which is classified as an eval.
    #   Without it every ``x-data`` / ``@click`` / ``:class`` directive throws
    #   "unsafe-eval is not an allowed source of script" and the entire
    #   sidebar / modal / drawer UI is dead. The CSP-safe Alpine build avoids
    #   this but requires a build step we don't run.
    # Tightening with per-request nonces + the CSP-safe Alpine bundle is a
    # future improvement; for now this is the working tradeoff.
    _CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )

    def _csp_enabled() -> bool:
        # Default to on. Only the explicit disable strings flip it off —
        # this mirrors how other ship-forge env flags behave.
        val = os.environ.get("SHIPFORGE_CSP", "1").strip().lower()
        return val not in ("0", "false", "off", "no")

    @app.after_request
    def _apply_security_and_cache_headers(response):
        # CSP: do not clobber an already-set policy (e.g. reverse-proxy may
        # inject its own). Only add when absent and the env flag is on.
        if _csp_enabled() and "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = _CSP_POLICY

        # Cache-Control for /static/ — short TTL so edits surface quickly
        # during iteration. Skip if a handler (e.g. /block-texture) already
        # set its own Cache-Control; skip non-/static/ paths entirely.
        try:
            path = request.path or ""
        except RuntimeError:
            # No request context (shouldn't happen in after_request, but be
            # defensive so header logic can't break a response).
            path = ""
        if path.startswith("/static/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "public, max-age=300"

        return response

    # Expose the in-memory store for tests.
    app.config["_RESULTS"] = results
    return app


# Default ``app`` object for ``flask --app spaceship_generator.web.app``.
app = create_app()
