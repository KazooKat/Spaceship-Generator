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
