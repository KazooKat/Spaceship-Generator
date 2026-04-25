"""Tests for GET /api/palettes/<name> single-palette detail endpoint."""

from __future__ import annotations

import pytest

from spaceship_generator.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


def test_api_palette_detail_ok(client):
    rv = client.get("/api/palettes/sci_fi_industrial")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["name"] == "sci_fi_industrial"
    assert "roles" in data
    assert "preview_colors" in data
    assert isinstance(data["roles"], dict)
    # HULL role must be present
    assert "HULL" in data["roles"]


def test_api_palette_detail_not_found(client):
    rv = client.get("/api/palettes/nonexistent_xyz_palette")
    assert rv.status_code == 404
    data = rv.get_json()
    assert "error" in data


def test_api_preset_detail_known(client):
    rv = client.get("/api/presets/corvette")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["name"] == "corvette"
    assert "description" in data
    assert isinstance(data["description"], str) and len(data["description"]) > 0


def test_api_preset_detail_unknown(client):
    rv = client.get("/api/presets/nonexistent_xyz")
    assert rv.status_code == 404
    data = rv.get_json()
    assert "error" in data


def test_fleet_plan_default_params(client):
    rv = client.get("/api/fleet/plan")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "ships" in data
    assert isinstance(data["ships"], list)
    assert len(data["ships"]) == data["count"]
    ship = data["ships"][0]
    assert "seed" in ship
    assert "dims" in ship
    assert "hull_style" in ship
    assert "width" in ship["dims"]


def test_fleet_plan_custom_count(client):
    rv = client.get("/api/fleet/plan?count=5&seed=42&palette=sci_fi_industrial")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 5
    assert len(data["ships"]) == 5


def test_fleet_plan_invalid_count_zero(client):
    rv = client.get("/api/fleet/plan?count=0")
    assert rv.status_code == 400
    assert "error" in rv.get_json()


def test_fleet_plan_invalid_palette(client):
    rv = client.get("/api/fleet/plan?palette=nonexistent_xyz_palette")
    assert rv.status_code == 400
    assert "error" in rv.get_json()


def test_fleet_plan_invalid_size_tier(client):
    rv = client.get("/api/fleet/plan?size_tier=bogus")
    assert rv.status_code == 400
    assert "error" in rv.get_json()


def test_api_compare_basic(client):
    rv = client.get("/api/compare?seed_a=1&seed_b=2")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "ship_a" in data and "ship_b" in data
    assert data["ship_a"]["seed"] == 1
    assert data["ship_b"]["seed"] == 2
    assert "dimensions" in data["ship_a"]
    assert "voxel_count" in data["ship_a"]


def test_api_compare_missing_seed(client):
    rv = client.get("/api/compare?seed_a=1")
    assert rv.status_code == 400
    assert "seed_b" in rv.get_json()["error"]


def test_api_compare_bad_palette(client):
    rv = client.get("/api/compare?seed_a=1&seed_b=2&palette=not_a_real_palette")
    assert rv.status_code == 400


def test_api_styles_returns_all_keys(client):
    resp = client.get("/api/styles")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"hull_styles", "engine_styles", "wing_styles", "greeble_types", "weapon_types"}
    for key in data:
        assert isinstance(data[key], list), f"{key} should be a list"
        assert len(data[key]) > 0, f"{key} should be non-empty"


def test_api_styles_hull_styles_contains_known_values(client):
    resp = client.get("/api/styles")
    data = resp.get_json()
    assert "arrow" in data["hull_styles"]
    assert "saucer" in data["hull_styles"]


def test_api_styles_greeble_types_contains_known_values(client):
    resp = client.get("/api/styles")
    data = resp.get_json()
    assert "turret" in data["greeble_types"]
    assert "dish" in data["greeble_types"]


def test_api_random_returns_keys(client):
    from spaceship_generator import presets as _presets
    from spaceship_generator.palette import list_palettes as _list_palettes

    resp = client.get("/api/random")
    assert resp.status_code == 200
    # Cache-Control: no-store so a proxy can't memoize a "spin" result.
    assert resp.headers.get("Cache-Control") == "no-store"
    data = resp.get_json()
    assert set(data.keys()) == {"seed", "palette", "preset"}
    assert isinstance(data["seed"], int)
    assert 0 <= data["seed"] <= 2**31 - 1
    assert isinstance(data["palette"], str)
    assert isinstance(data["preset"], str)
    assert data["palette"] in _list_palettes()
    assert data["preset"] in _presets.list_presets()


def test_api_random_two_calls_differ(client):
    # 5 calls — astronomical odds that all share the same triple if RNG
    # is sourced from secrets.randbits / SystemRandom as required.
    triples = set()
    for _ in range(5):
        data = client.get("/api/random").get_json()
        triples.add((data["seed"], data["palette"], data["preset"]))
    assert len(triples) >= 2


def test_api_random_with_seed_reproducible(client):
    a = client.get("/api/random?seed=42").get_json()
    b = client.get("/api/random?seed=42").get_json()
    assert a["seed"] == 42
    assert b["seed"] == 42
    assert a["palette"] == b["palette"]
    assert a["preset"] == b["preset"]
