"""Extra static-ish routes: cached block textures + generated-file downloads.

These are separate from Flask's built-in ``/static/`` because the payloads
are produced by the generator at runtime (``.litematic`` files) or pulled
from the on-disk texture cache by id (``/block-texture/<id>.png``). Both
live here so the main ``ship`` blueprint stays focused on the
generate/preview/voxels surface.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from flask import Blueprint, abort, current_app, send_file

from ...block_colors import block_texture_png


# Accept namespaced block ids, with optional state spec (e.g. ``[lit=true]``).
# Matches what ``block_colors._BLOCKID_RE`` accepts so the route can safely
# round-trip the block ids produced by the palette key.
_BLOCKID_URL_RE = re.compile(r"^[A-Za-z0-9_:\-\[\]=,]+$")


static_ext_bp = Blueprint("static_ext", __name__)


@static_ext_bp.route("/block-texture/<path:block_id>.png", endpoint="block_texture")
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


@static_ext_bp.route("/download/<gen_id>", endpoint="download")
def download(gen_id: str):
    results = current_app.config["_RESULTS"]
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


__all__ = ["static_ext_bp", "_BLOCKID_URL_RE"]
