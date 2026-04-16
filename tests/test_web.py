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
    assert "Spaceship Generator" in body
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
    assert 'class="preview"' in body


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


def test_memory_eviction_cleans_up_litematic(small_client):
    """Oldest .litematic on disk should be deleted when evicted from cache."""
    app, client = small_client
    assert app.config["MAX_RESULTS"] == 2

    results_store = app.config["_RESULTS"]

    gen_ids: list[str] = []
    disk_paths: list[Path] = []

    for seed in (11, 22, 33):
        body = _minimal_json()
        body["seed"] = seed
        resp = client.post("/api/generate", json=body)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        gen_ids.append(data["gen_id"])

        # Capture the disk path from the stored GenerationResult right now,
        # since after eviction the entry will be removed from the store.
        result = results_store.get(data["gen_id"])
        if result is not None:
            disk_paths.append(Path(result.litematic_path))

    # Only the last 2 should still be in the cache; the first was evicted.
    assert gen_ids[0] not in results_store
    assert gen_ids[1] in results_store
    assert gen_ids[2] in results_store

    # We captured 3 disk paths (even for the first one, at time of creation).
    assert len(disk_paths) == 3
    evicted_path, kept_a, kept_b = disk_paths

    # Evicted file was unlinked; kept ones still exist.
    assert not evicted_path.exists(), (
        f"evicted litematic should be removed from disk: {evicted_path}"
    )
    assert kept_a.exists()
    assert kept_b.exists()
