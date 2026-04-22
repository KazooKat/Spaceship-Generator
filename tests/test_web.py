"""Tests for the Flask web UI using the test client."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from spaceship_generator.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    # Route instance_path to tmp_path so generated files land outside the repo.
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


@pytest.fixture
def small_client(tmp_path, monkeypatch):
    """Client with a tiny MAX_RESULTS cap, used to exercise eviction."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["MAX_RESULTS"] = 2
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield app, c


def _minimal_form():
    return {
        "seed": "7",
        "palette": "sci_fi_industrial",
        "length": "24",
        "width": "12",
        "height": "8",
        "engines": "2",
        "wing_prob": "0.5",
        "greeble_density": "0.05",
        "window_period": "4",
        "cockpit": "bubble",
    }


def _minimal_json():
    return {
        "seed": 7,
        "palette": "sci_fi_industrial",
        "length": 24,
        "width": 12,
        "height": 8,
        "engines": 2,
        "wing_prob": 0.5,
        "greeble_density": 0.05,
        "window_period": 4,
        "cockpit": "bubble",
    }


def test_get_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Brand title may render as "SHIP FORGE" in the topbar after the UI revamp,
    # but base.html still carries a screen-reader-only <h1> with the canonical
    # product name "Spaceship Generator". Accept either anchor so the test
    # survives brand-surface rewording without losing meaning.
    assert ("Spaceship Generator" in body) or ("Ship" in body)
    assert "<form" in body
    assert "sci_fi_industrial" in body


def test_generate_flow(client):
    resp = client.post(
        "/generate",
        data=_minimal_form(),
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/result/")
    # Extract gen_id
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]

    # GET /result/<gen_id>
    result_resp = client.get(f"/result/{gen_id}")
    assert result_resp.status_code == 200
    body = result_resp.get_data(as_text=True)
    assert "Download .litematic" in body
    assert f'src="/preview/{gen_id}.png"' in body

    # GET preview PNG
    preview_resp = client.get(f"/preview/{gen_id}.png")
    assert preview_resp.status_code == 200
    assert preview_resp.mimetype == "image/png"
    assert preview_resp.data.startswith(b"\x89PNG")

    # GET download
    dl_resp = client.get(f"/download/{gen_id}")
    assert dl_resp.status_code == 200
    assert "attachment" in dl_resp.headers.get("Content-Disposition", "")
    assert len(dl_resp.data) > 0


def test_generate_invalid_param_shows_error(client):
    data = _minimal_form()
    data["length"] = "4"  # invalid
    resp = client.post("/generate", data=data)
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Error" in body
    assert "length" in body.lower()


def test_generate_missing_palette_shows_error(client):
    data = _minimal_form()
    data["palette"] = "does_not_exist"
    resp = client.post("/generate", data=data)
    assert resp.status_code == 400


def test_missing_gen_id_404(client):
    assert client.get("/result/nonexistent").status_code == 404
    assert client.get("/preview/nonexistent.png").status_code == 404
    assert client.get("/download/nonexistent").status_code == 404


# --- New tests -------------------------------------------------------------


def test_index_has_new_texture_fields(client):
    """Form must expose accent_stripe_period and engine_glow_depth inputs."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="accent_stripe_period"' in body
    assert 'name="engine_glow_depth"' in body


def test_index_has_random_seed_button(client):
    """A randomize-seed button must be present in the form."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Check for the id/data-role anchor the JS hook uses.
    assert 'id="randomize-seed"' in body


def test_api_palettes_returns_builtins(client):
    resp = client.get("/api/palettes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "palettes" in data
    palettes = data["palettes"]
    assert isinstance(palettes, list)
    # Original + new themes.
    for expected in (
        "sci_fi_industrial",
        "sleek_modern",
        "rustic_salvage",
        "alien_bio",
        "gold_imperial",
        "diamond_tech",
        "end_void",
        "coral_reef",
        "candy_pop",
        "neon_arcade",
        "wooden_frigate",
        "desert_sandstone",
        "deepslate_drone",
        "amethyst_crystal",
        "nordic_scout",
    ):
        assert expected in palettes, f"missing palette {expected!r}"


def test_random_palette_picks_deterministically(client):
    """'palette=random' resolves to a real palette based on seed."""
    body = _minimal_json()
    body["palette"] = "random"
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 200
    data = resp.get_json()
    # Resolved to a real palette (not the literal "random").
    assert data["palette"] != "random"
    assert data["palette"] in client.get("/api/palettes").get_json()["palettes"]

    # Same seed + random → same resolved palette (deterministic).
    resp2 = client.post("/api/generate", json=body)
    assert resp2.get_json()["palette"] == data["palette"]


def test_index_has_random_palette_option(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert 'value="random"' in body


def test_api_generate_valid_body(client):
    resp = client.post("/api/generate", json=_minimal_json())
    assert resp.status_code == 200
    data = resp.get_json()
    # Required keys
    for key in ("seed", "palette", "shape", "blocks", "download_url", "preview_url", "gen_id"):
        assert key in data, f"missing key {key!r} in JSON response"
    assert data["seed"] == 7
    assert data["palette"] == "sci_fi_industrial"
    assert isinstance(data["shape"], list) and len(data["shape"]) == 3
    assert isinstance(data["blocks"], int) and data["blocks"] > 0
    assert data["download_url"] == f"/download/{data['gen_id']}"
    assert data["preview_url"] == f"/preview/{data['gen_id']}.png"
    assert re.fullmatch(r"[0-9a-f]{12}", data["gen_id"])


def test_api_generate_invalid_palette(client):
    body = _minimal_json()
    body["palette"] = "does_not_exist"
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_index_has_tooltips(client):
    """Each input should have a ? tooltip with explanation."""
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    # Sample a few known help keys.
    assert 'class="tip"' in body
    assert "Same seed + same parameters" in body
    assert "Probability (0-1)" in body
    assert "greeble" in body.lower()


def test_index_has_htmx_form(client):
    """Form must use hx-post so generation happens inline on the page."""
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert 'hx-post="/generate"' in body
    assert 'id="result-panel"' in body
    assert 'hx-target="#result-panel"' in body


def test_htmx_generate_returns_partial_not_redirect(client):
    """When HX-Request is set, /generate returns HTML partial with 200."""
    resp = client.post(
        "/generate",
        data=_minimal_form(),
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Partial should contain the key and preview, but NOT a full <html> shell.
    assert "<html" not in body.lower()
    assert "Download .litematic" in body
    assert "Block key" in body
    # After the UI revamp the outer section may carry "result preview" rather
    # than a standalone `class="preview"`, and the canvas wrapper is now the
    # authoritative preview container. Accept any of these shapes so the
    # partial contract stays flexible.
    assert (
        'class="preview"' in body
        or 'class="result preview"' in body
        or "preview-canvas" in body
    )


def test_htmx_generate_error_returns_error_partial(client):
    """Bad input from HTMX should return the error partial, not full page."""
    data = _minimal_form()
    data["palette"] = "does_not_exist"
    resp = client.post(
        "/generate",
        data=data,
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "<html" not in body.lower()
    assert "Error" in body


def test_result_page_includes_block_key(client):
    """/result/<id> shows legend: role labels, block icons/swatches, block ids."""
    resp = client.post("/generate", data=_minimal_form())
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]

    result_resp = client.get(f"/result/{gen_id}")
    body = result_resp.get_data(as_text=True)
    assert "Block key" in body
    # Each row renders either a cached block-texture icon (preferred) or a
    # color swatch fallback — at least one must be present.
    assert 'class="block-icon"' in body or 'class="swatch"' in body
    # Must list at least one known role label + one minecraft: block id.
    assert "Windows" in body
    assert "minecraft:" in body


def test_block_texture_route_serves_png(client):
    """/block-texture/<block_id>.png returns cached PNG bytes for known blocks."""
    resp = client.get("/block-texture/minecraft:iron_block.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data.startswith(b"\x89PNG")


def test_block_texture_route_404_for_unknown(client):
    resp = client.get("/block-texture/minecraft:definitely_not_a_block.png")
    assert resp.status_code == 404


def test_block_texture_route_400_for_malformed(client):
    # Spaces and other unsafe chars must be rejected.
    resp = client.get("/block-texture/not a block.png")
    assert resp.status_code == 400


def test_result_page_renders_block_icon_when_cached(client):
    """Block key rows should use <img class=block-icon> when a texture is cached."""
    resp = client.post("/generate", data=_minimal_form())
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]
    body = client.get(f"/result/{gen_id}").get_data(as_text=True)
    assert 'class="block-icon"' in body
    assert "/block-texture/" in body


def test_preview_accepts_view_params(client):
    """Preview endpoint should re-render on elev/azim query params."""
    resp = client.post("/generate", data=_minimal_form())
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]

    rotated = client.get(f"/preview/{gen_id}.png?elev=10&azim=45")
    assert rotated.status_code == 200
    assert rotated.mimetype == "image/png"
    assert rotated.data.startswith(b"\x89PNG")

    # Bad floats → 400 (not a 500).
    bad = client.get(f"/preview/{gen_id}.png?elev=not_a_number")
    assert bad.status_code == 400


def test_voxels_endpoint_applies_alpha_to_translucent_roles(client):
    """/voxels/<id>.json should emit alpha < 1 for roles mapped to translucent blocks.

    Also assert the top-level payload shape (dims, count, voxels, colors) matches
    the documented contract in :func:`voxels` (base64-packed Int16 voxel buffer
    alongside a per-role RGBA color map).
    """
    # sci_fi_industrial maps WINDOW -> light_blue_stained_glass and
    # COCKPIT_GLASS -> tinted_glass, so both should come back translucent.
    resp = client.post(
        "/generate",
        data=_minimal_form(),
        follow_redirects=False,
    )
    assert resp.status_code == 302
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]

    from spaceship_generator.palette import Role

    vox_resp = client.get(f"/voxels/{gen_id}.json")
    assert vox_resp.status_code == 200
    data = vox_resp.get_json()

    # --- M15: top-level contract assertions -------------------------------
    # dims: [W, H, L] — three positive ints.
    assert "dims" in data, f"response missing 'dims': keys={list(data.keys())}"
    dims = data["dims"]
    assert isinstance(dims, list) and len(dims) == 3
    assert all(isinstance(d, int) and d > 0 for d in dims), dims

    # count: non-negative int, number of surface voxels.
    assert "count" in data, f"response missing 'count': keys={list(data.keys())}"
    assert isinstance(data["count"], int) and data["count"] >= 0

    # voxels: base64-encoded packed Int16 buffer (4 * count int16 = 8 * count bytes).
    assert "voxels" in data, f"response missing 'voxels': keys={list(data.keys())}"
    assert isinstance(data["voxels"], str)
    import base64 as _b64
    raw = _b64.b64decode(data["voxels"])
    assert len(raw) == data["count"] * 8, (
        f"voxels buffer length {len(raw)} != 8 * count ({data['count']})"
    )

    # colors: dict of role-int-string -> 4-float RGBA list.
    assert "colors" in data, f"response missing 'colors': keys={list(data.keys())}"
    colors = data["colors"]
    assert isinstance(colors, dict) and len(colors) > 0

    window_rgba = colors.get(str(int(Role.WINDOW)))
    cockpit_rgba = colors.get(str(int(Role.COCKPIT_GLASS)))
    hull_rgba = colors.get(str(int(Role.HULL)))

    assert window_rgba is not None and len(window_rgba) == 4
    assert cockpit_rgba is not None and len(cockpit_rgba) == 4
    assert hull_rgba is not None and len(hull_rgba) == 4

    # Translucent roles get alpha < 1.
    assert window_rgba[3] < 1.0, window_rgba
    assert cockpit_rgba[3] < 1.0, cockpit_rgba
    # Opaque roles keep full alpha.
    assert hull_rgba[3] == 1.0, hull_rgba


def test_index_has_structure_style_select(client):
    """Index page must expose a <select name='structure_style'> with every
    ``StructureStyle`` enum value rendered as an ``<option>``.

    The form drives hull archetype selection; any silently dropped enum value
    would regress the UI without breaking tests unless each value is checked
    explicitly. We walk the live enum so adding a new archetype keeps the
    assertion honest without hardcoding the list.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="structure_style"' in body

    from spaceship_generator.shape import StructureStyle

    # Every enum value must appear as an <option value="..."> in the rendered
    # HTML. Use a regex to tolerate attribute order and surrounding whitespace.
    for style in StructureStyle:
        pattern = re.compile(
            r'<option\s+[^>]*value="' + re.escape(style.value) + r'"',
            re.IGNORECASE,
        )
        assert pattern.search(body), (
            f"StructureStyle.{style.name} ({style.value!r}) missing as <option> in index"
        )


def test_generate_with_structure_style_fighter(client):
    """POST /generate with structure_style=fighter returns 200 and a new ship."""
    data = _minimal_form()
    data["structure_style"] = "fighter"
    resp = client.post("/generate", data=data, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/result/")
    gen_id = resp.headers["Location"].rsplit("/", 1)[-1]
    # Fetch the result page and verify it rendered.
    result_resp = client.get(f"/result/{gen_id}")
    assert result_resp.status_code == 200
    body = result_resp.get_data(as_text=True)
    assert "Download .litematic" in body


def test_generate_with_invalid_structure_style_returns_400(client):
    """Invalid structure_style values yield a 400 error."""
    data = _minimal_form()
    data["structure_style"] = "not-a-real-archetype"
    resp = client.post("/generate", data=data)
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "Error" in body
    assert "structure_style" in body.lower()


def test_api_generate_with_structure_style(client):
    """JSON API accepts structure_style and actually uses it.

    The current /api/generate response dict does not echo ``structure_style``
    back (keys are: seed, palette, shape, blocks, download_url, preview_url,
    gen_id). To prove the field took effect we generate the same seed + params
    under two different archetypes and assert the resulting ships differ —
    either in overall bounding-box shape or in block count. Identical outputs
    would mean the ``structure_style`` knob was silently ignored.
    """
    # Fighter: compact, typically lower block count than a dreadnought.
    body_fighter = _minimal_json()
    body_fighter["structure_style"] = "fighter"
    resp_fighter = client.post("/api/generate", json=body_fighter)
    assert resp_fighter.status_code == 200
    data_fighter = resp_fighter.get_json()
    assert "gen_id" in data_fighter
    assert data_fighter["blocks"] > 0
    # Contract check: no structure_style echo in the response (update this
    # assertion if the API ever grows to echo it back).
    assert "structure_style" not in data_fighter

    # Dreadnought: larger bulk profile with the same seed+params.
    body_dread = _minimal_json()
    body_dread["structure_style"] = "dreadnought"
    resp_dread = client.post("/api/generate", json=body_dread)
    assert resp_dread.status_code == 200
    data_dread = resp_dread.get_json()
    assert data_dread["blocks"] > 0

    # The archetype must produce a measurable difference: either the
    # bounding-box shape changes, or the block count differs. If both match
    # the two styles collapse to the same output — the style parameter has
    # effectively done nothing.
    assert (
        data_fighter["shape"] != data_dread["shape"]
        or data_fighter["blocks"] != data_dread["blocks"]
    ), (
        f"fighter and dreadnought produced identical ships "
        f"(shape={data_fighter['shape']}, blocks={data_fighter['blocks']}): "
        f"structure_style appears to be ignored"
    )


def test_api_generate_invalid_structure_style(client):
    """JSON API rejects unknown structure_style with 400."""
    body = _minimal_json()
    body["structure_style"] = "not-a-style"
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_memory_eviction_cleans_up_litematic(small_client):
    """Oldest .litematic on disk should be deleted when evicted from cache.

    Exercised through the public HTTP surface: POST enough /api/generate
    calls to exceed MAX_RESULTS (which the fixture clamps to 2), then hit
    /download/<first_gen_id> and expect 404 once the LRU has evicted it.
    The on-disk .litematic file for the evicted id must also be gone.
    """
    app, client = small_client
    assert app.config["MAX_RESULTS"] == 2

    gen_ids: list[str] = []
    disk_paths: list[Path] = []

    for seed in (11, 22, 33):
        body = _minimal_json()
        body["seed"] = seed
        resp = client.post("/api/generate", json=body)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        gen_id = data["gen_id"]
        gen_ids.append(gen_id)

        # Capture disk path at creation time via the public endpoint (before
        # possible eviction removes the entry from the store).
        result_resp = client.get(f"/api/result/{gen_id}")
        assert result_resp.status_code == 200, (
            f"freshly created result {gen_id} not found via /api/result/"
        )
        filename = result_resp.get_json()["filename"]
        disk_paths.append(Path(app.instance_path) / "generated" / filename)

    # Public-API verification: the first (evicted) id should 404 on all
    # result-serving endpoints.
    first_id = gen_ids[0]
    assert client.get(f"/download/{first_id}").status_code == 404, (
        f"download of evicted id {first_id} should 404"
    )
    assert client.get(f"/result/{first_id}").status_code == 404
    assert client.get(f"/preview/{first_id}.png").status_code == 404

    # The two most recent ids must still be downloadable.
    for kept_id in gen_ids[1:]:
        dl = client.get(f"/download/{kept_id}")
        assert dl.status_code == 200, (
            f"download of kept id {kept_id} should succeed, got {dl.status_code}"
        )
        assert "attachment" in dl.headers.get("Content-Disposition", "")

    # Disk cleanup: evicted file removed, kept files still present.
    assert len(disk_paths) == 3
    evicted_path, kept_a, kept_b = disk_paths
    assert not evicted_path.exists(), (
        f"evicted litematic should be removed from disk: {evicted_path}"
    )
    assert kept_a.exists()
    assert kept_b.exists()


def test_api_result_endpoint(client):
    """GET /api/result/<gen_id> returns metadata for a known id and 404 for unknown."""
    # 1. Generate a ship so we have a valid gen_id.
    resp = client.post("/api/generate", json=_minimal_json())
    assert resp.status_code == 200
    gen_id = resp.get_json()["gen_id"]

    # 2. Fetch result metadata via the new endpoint.
    result_resp = client.get(f"/api/result/{gen_id}")
    assert result_resp.status_code == 200
    data = result_resp.get_json()
    for key in ("gen_id", "seed", "palette", "shape", "blocks", "filename",
                "download_url", "preview_url"):
        assert key in data, f"missing key {key!r} in /api/result response"
    assert data["gen_id"] == gen_id
    assert data["download_url"] == f"/download/{gen_id}"
    assert data["preview_url"] == f"/preview/{gen_id}.png"
    assert isinstance(data["shape"], list) and len(data["shape"]) == 3
    assert isinstance(data["blocks"], int) and data["blocks"] > 0
    assert data["filename"].endswith(".litematic")

    # 3. Unknown id must return 404.
    not_found = client.get("/api/result/nonexistent")
    assert not_found.status_code == 404
    assert "error" in not_found.get_json()


# --- New tests covering F5's app.py changes --------------------------------


def test_download_404_when_file_deleted_from_disk(client):
    """/download/<gen_id> must return 404 (not 500) when the .litematic is gone.

    Covers M4 fixed in parallel by F5: the result can still be in the LRU
    cache while its on-disk file vanishes (manual cleanup, tmpfs churn,
    concurrent eviction of an earlier request writing to the same tree).
    ``send_file`` would otherwise crash with a 500; the fix returns 404.
    """
    resp = client.post("/api/generate", json=_minimal_json())
    assert resp.status_code == 200
    data = resp.get_json()
    gen_id = data["gen_id"]

    # Sanity: download works right now. Close the response explicitly so
    # the underlying file handle opened by ``send_file`` is released —
    # on Windows a still-open handle blocks the subsequent ``unlink`` with
    # a PermissionError (ERROR_SHARING_VIOLATION).
    first = client.get(f"/download/{gen_id}")
    assert first.status_code == 200
    first.close()

    # Reach into the store only to locate the disk file the route serves.
    # This mirrors the operational scenario where an external process (or
    # another worker) removes the file between list and serve.
    results_store = client.application.config["_RESULTS"]
    result = results_store.get(gen_id)
    assert result is not None
    disk_path = Path(result.litematic_path)
    assert disk_path.exists()
    disk_path.unlink()
    assert not disk_path.exists()

    # Now the route must 404 — not 500 — because the gen_id still maps
    # to a cached GenerationResult but the underlying file is gone.
    resp2 = client.get(f"/download/{gen_id}")
    assert resp2.status_code == 404, (
        f"expected 404 when .litematic missing on disk, got {resp2.status_code}"
    )


@pytest.mark.parametrize("bad_value", ["nan", "NaN", "inf", "Infinity", "-inf"])
def test_generate_rejects_non_finite_float_params(client, bad_value):
    """NaN/Inf floats must be rejected with 400 (not poison downstream numpy).

    Covers M7 fixed in parallel by F5: ``float("nan")`` and ``float("inf")``
    parse without error in Python, so without an explicit ``math.isfinite``
    guard they would flow into ShapeParams and then into numpy-heavy code,
    producing either NaN voxels or a 500 deep inside the generator. The fix
    rejects them at the boundary with a 400.
    """
    data = _minimal_form()
    data["wing_prob"] = bad_value
    resp = client.post("/generate", data=data)
    assert resp.status_code == 400, (
        f"wing_prob={bad_value!r} should be rejected with 400, "
        f"got {resp.status_code}"
    )


@pytest.mark.parametrize("bad_value", ["nan", "inf"])
def test_api_generate_rejects_non_finite_float_params(client, bad_value):
    """JSON API must also reject NaN/Inf floats with 400.

    JSON parsers can round-trip the strings ``"nan"``/``"inf"`` as Python
    floats via ``float(str)`` inside the param builder even if strict JSON
    would not. The boundary guard must catch both entry paths.
    """
    body = _minimal_json()
    body["wing_prob"] = bad_value
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 400, (
        f"api wing_prob={bad_value!r} should be rejected with 400, "
        f"got {resp.status_code}"
    )
    payload = resp.get_json()
    assert isinstance(payload, dict) and "error" in payload


def test_index_has_randomize_all_button(client):
    """Randomize-all button and its inline randomizer script must be present.

    Shipping the button without the script would give a silent no-op; shipping
    the script without the button would be dead code. Assert both anchors.

    Post-UI-revamp: the topbar random button may carry either the legacy
    ``randomize-all`` id (kept as an alias) or the new ``btn-random`` id —
    either is acceptable as long as the inline randomizer script resolves
    a matching node via ``getElementById``.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Button must be there under one of the accepted ids.
    assert ('id="randomize-all"' in body) or ('id="btn-random"' in body), (
        "no randomize-all / btn-random button found in index"
    )

    # And the inline randomizer must be wired to one of those ids. We check
    # for the core getElementById lookup; whitespace / quote style is
    # tolerated via a simple regex. Either id is acceptable.
    script_hook = re.compile(
        r"getElementById\(\s*['\"](?:randomize-all|btn-random)['\"]\s*\)"
    )
    assert script_hook.search(body), (
        "inline randomizer script not found — random button would be inert"
    )


# --- Rate limiting ---------------------------------------------------------
#
# Tests build a dedicated client whose app has a small rate-limit window so
# the 429 path is exercised quickly. The default-client cap is 10/min which
# is generous enough that all other tests stay under it.


#
# Loopback (127.0.0.1 / ::1 / "localhost") is exempt from the limiter so
# local dev doesn't lock the developer out. The Flask test client always
# reports ``127.0.0.1`` as ``remote_addr`` — if the rate-limit tests didn't
# send a non-loopback ``X-Forwarded-For`` they'd now ride the exemption
# and never hit the 429 path. TEST-NET-3 (203.0.113.0/24) is reserved
# for documentation per RFC 5737 so it's safe to use as a synthetic
# client address.
_SYNTHETIC_CLIENT_IP = "203.0.113.7"


def _rl_headers(extra: dict | None = None) -> dict:
    h = {"X-Forwarded-For": _SYNTHETIC_CLIENT_IP}
    if extra:
        h.update(extra)
    return h


@pytest.fixture
def rate_limited_client(tmp_path, monkeypatch):
    """Client with rate limit = 2 per 60s for deterministic 429 behavior.
    Tests must still send a non-loopback X-Forwarded-For to hit the
    limiter — loopback is intentionally exempt."""
    monkeypatch.setenv("SHIPFORGE_RATE_LIMIT", "2")
    monkeypatch.setenv("SHIPFORGE_RATE_WINDOW", "60")
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


def test_rate_limit_html_generate(rate_limited_client):
    """Third /generate POST inside the window returns 429 with Retry-After."""
    form = _minimal_form()
    r1 = rate_limited_client.post(
        "/generate", data=form, headers=_rl_headers(), follow_redirects=False,
    )
    r2 = rate_limited_client.post(
        "/generate", data=form, headers=_rl_headers(), follow_redirects=False,
    )
    assert r1.status_code in (200, 302)
    assert r2.status_code in (200, 302)
    r3 = rate_limited_client.post(
        "/generate", data=form, headers=_rl_headers(), follow_redirects=False,
    )
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    retry = int(r3.headers["Retry-After"])
    assert 1 <= retry <= 60


def test_rate_limit_json_api(rate_limited_client):
    """Third /api/generate hit returns JSON 429 with ``retry_after``."""
    body = _minimal_json()
    r1 = rate_limited_client.post("/api/generate", json=body, headers=_rl_headers())
    r2 = rate_limited_client.post("/api/generate", json=body, headers=_rl_headers())
    assert r1.status_code == 200
    assert r2.status_code == 200
    r3 = rate_limited_client.post("/api/generate", json=body, headers=_rl_headers())
    assert r3.status_code == 429
    payload = r3.get_json()
    assert payload["error"] == "rate_limited"
    assert isinstance(payload["retry_after"], int)
    assert payload["retry_after"] >= 1
    assert payload["limit"] == 2
    assert payload["window_seconds"] == 60
    assert "Retry-After" in r3.headers


def test_rate_limit_htmx_variant_returns_error_partial(rate_limited_client):
    """When the limited request is an HTMX form POST, the 429 body is the
    ``_error.html`` partial so HTMX can swap it into the error slot."""
    form = _minimal_form()
    rate_limited_client.post("/generate", data=form, headers=_rl_headers())
    rate_limited_client.post("/generate", data=form, headers=_rl_headers())
    r3 = rate_limited_client.post(
        "/generate", data=form, headers=_rl_headers({"HX-Request": "true"}),
    )
    assert r3.status_code == 429
    body = r3.get_data(as_text=True)
    assert "slow down" in body.lower() or "too many" in body.lower()


def test_rate_limit_exempts_loopback(rate_limited_client):
    """Requests coming from loopback (no XFF, remote_addr=127.0.0.1) must
    NOT be rate-limited even with a low limit set. This protects local
    dev + the Flask dev server from accidental lockout while iterating."""
    form = _minimal_form()
    # Fire WAY past the configured cap of 2/min. Loopback should ride
    # through every one.
    for i in range(6):
        resp = rate_limited_client.post(
            "/generate", data=form, follow_redirects=False,
        )
        assert resp.status_code in (200, 302), (
            f"loopback request #{i + 1} got {resp.status_code} "
            f"— loopback exemption is broken"
        )


def test_rate_limit_disabled_with_env_zero(tmp_path, monkeypatch):
    """Setting SHIPFORGE_RATE_LIMIT=0 turns the limiter off entirely."""
    monkeypatch.setenv("SHIPFORGE_RATE_LIMIT", "0")
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        body = _minimal_json()
        # 5 > default 10, but here we've disabled it entirely.
        for _ in range(5):
            resp = c.post("/api/generate", json=body)
            assert resp.status_code == 200


def test_rate_limit_isolates_by_ip(rate_limited_client):
    """Different X-Forwarded-For heads get their own counters."""
    form = _minimal_form()
    # 203.0.113.0/24 is TEST-NET-3 (RFC 5737) — safe synthetic addrs.
    rate_limited_client.post(
        "/generate", data=form, headers={"X-Forwarded-For": "203.0.113.1"}
    )
    rate_limited_client.post(
        "/generate", data=form, headers={"X-Forwarded-For": "203.0.113.1"}
    )
    # 203.0.113.1 now exhausted.
    exhausted = rate_limited_client.post(
        "/generate", data=form, headers={"X-Forwarded-For": "203.0.113.1"}
    )
    assert exhausted.status_code == 429
    # Different IP is still fresh.
    ok = rate_limited_client.post(
        "/generate", data=form, headers={"X-Forwarded-For": "203.0.113.2"}
    )
    assert ok.status_code in (200, 302)


def test_api_palettes_includes_colors(client):
    """/api/palettes must include a 'colors' key with hex swatches per palette."""
    resp = client.get("/api/palettes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "colors" in data, "'colors' key missing from /api/palettes response"
    colors = data["colors"]
    assert isinstance(colors, dict) and len(colors) > 0
    # At least one palette must expose a HULL swatch as a hex string.
    has_hull = any(
        isinstance(swatches.get("HULL"), str)
        for swatches in colors.values()
    )
    assert has_hull, "No palette in 'colors' has a 'HULL' hex string"


def test_csp_allows_unsafe_eval_for_alpine(client):
    """Alpine.js compiles reactive expressions via ``new Function()``. That
    requires ``'unsafe-eval'`` in ``script-src`` or every ``x-data`` /
    ``@click`` directive throws and the sidebar / modal UI is inert."""
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "script-src" in csp
    assert "'unsafe-eval'" in csp
