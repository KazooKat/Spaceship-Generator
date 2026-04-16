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
    for expected in ("sci_fi_industrial", "sleek_modern", "rustic_salvage"):
        assert expected in palettes


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
