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
