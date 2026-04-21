"""Flask web UI for Spaceship Generator.

Run with::

    flask --app spaceship_generator.web.app run

This module is a slim composition root. Route-carrying code lives in
``spaceship_generator.web.blueprints.*``:

* ``ship``       — generate / result / preview / voxels / JSON API
* ``static_ext`` — block-texture passthrough + .litematic downloads
* ``ratelimit``  — per-IP fixed-window limiter (loopback exempt)
* ``errors``     — JSON-aware 404 handler

CSP + /static/ cache-control headers are wired as a single
``after_request`` hook here since they're global response policy, not
per-blueprint concerns.
"""

from __future__ import annotations

import os

from flask import Flask, request

from .blueprints.errors import init_error_handlers
from .blueprints.ratelimit import init_rate_limiter
from .blueprints.ship import ship_bp
from .blueprints.ship_support import init_ship_state
from .blueprints.static_ext import static_ext_bp

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


# Endpoint names used by the Jinja templates (``url_for('download', ...)``
# etc). Blueprint registration produces prefixed names like
# ``static_ext.download``; we add bare-name aliases at the app level so
# templates keep working without changes, and our own Python views can
# use the short names too.
_ENDPOINT_ALIASES: dict[str, str] = {
    "index": "ship.index",
    "do_generate": "ship.do_generate",
    "show_result": "ship.show_result",
    "preview": "ship.preview",
    "voxels": "ship.voxels",
    "api_palettes": "ship.api_palettes",
    "api_generate": "ship.api_generate",
    "api_meta": "ship.api_meta",
    "block_texture": "static_ext.block_texture",
    "download": "static_ext.download",
}


def _install_endpoint_aliases(app: Flask) -> None:
    """For each ``bare -> blueprint.endpoint`` mapping, publish a second
    url rule with the bare endpoint name so ``url_for('bare', ...)`` works
    from templates. The added rules share the same view function; Flask
    dispatches the first matching rule to it regardless."""
    # Snapshot the registered rules so we can look up path + methods by
    # endpoint without mutating the map we iterate.
    by_endpoint = {rule.endpoint: rule for rule in app.url_map.iter_rules()}
    for bare, full in _ENDPOINT_ALIASES.items():
        rule = by_endpoint.get(full)
        if rule is None:  # pragma: no cover - defensive
            continue
        view_func = app.view_functions.get(full)
        if view_func is None:  # pragma: no cover - defensive
            continue
        # ``Rule.methods`` includes implicit HEAD/OPTIONS added by werkzeug;
        # drop them so the alias mirrors the original verbs only.
        methods = {m for m in (rule.methods or set()) if m not in {"HEAD", "OPTIONS"}}
        app.add_url_rule(
            rule.rule,
            endpoint=bare,
            view_func=view_func,
            methods=sorted(methods) or None,
        )


def create_app() -> Flask:
    app = Flask(__name__)

    # Wire shared services.
    init_rate_limiter(app)
    init_ship_state(app)
    init_error_handlers(app)

    # Register blueprints.
    app.register_blueprint(ship_bp)
    app.register_blueprint(static_ext_bp)

    # Templates use bare endpoint names (``url_for('download')``, etc). Add
    # aliases so they keep resolving after the blueprint rename.
    _install_endpoint_aliases(app)

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

    return app


# Default ``app`` object for ``flask --app spaceship_generator.web.app``.
app = create_app()
