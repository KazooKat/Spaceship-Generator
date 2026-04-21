"""App-level error handlers.

When the caller prefers JSON (e.g. ``fetch('/api/meta')`` with default
Accept or explicit ``application/json``), return a structured error body
instead of the Jinja-rendered HTML 404 page. HTML clients still get
Flask's default 404 page — this only specializes the JSON case.
"""

from __future__ import annotations

from flask import Flask, jsonify, request


def init_error_handlers(app: Flask) -> None:
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


__all__ = ["init_error_handlers"]
