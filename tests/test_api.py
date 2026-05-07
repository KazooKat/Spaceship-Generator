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
    # Flask's jsonify uses application/json; some servers may suffix
    # ``; charset=utf-8`` so accept either form (mirrors the assertion
    # style in test_api_health_ok / test_api_spec_status_and_content_type).
    ctype = rv.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
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
    ctype = rv.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = rv.get_json()
    assert "error" in data


def test_api_palette_detail_listed_in_openapi_spec(client):
    """``/api/spec`` must enumerate the single-palette detail path.

    Belt-and-braces alongside ``test_api_spec_lists_every_route`` (which
    walks the url_map): pin the exact OpenAPI path-template here so a
    refactor that drops the entry fails this test by name rather than the
    generic "missing routes" diff.
    """
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "/api/palettes/{name}" in data["paths"]
    op = data["paths"]["/api/palettes/{name}"].get("get")
    assert op is not None, "GET method missing for /api/palettes/{name}"
    assert "200" in op["responses"]
    assert "404" in op["responses"]


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


def test_api_shape_styles_returns_three_keys(client):
    """``GET /api/shape-styles`` mirrors the ``--list-shape-styles`` CLI flag:
    only hull/engine/wing — no greeble/weapon types."""
    resp = client.get("/api/shape-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"hull_styles", "engine_styles", "wing_styles"}
    for key in data:
        assert isinstance(data[key], list), f"{key} should be a list"
        assert len(data[key]) > 0, f"{key} should be non-empty"


def test_api_shape_styles_matches_styles_subset(client):
    """The three shape-style arrays must equal the matching arrays in
    ``/api/styles`` — same enum source, same serialization, same order."""
    full = client.get("/api/styles").get_json()
    narrow = client.get("/api/shape-styles").get_json()
    for key in ("hull_styles", "engine_styles", "wing_styles"):
        assert narrow[key] == full[key], f"{key} drifts between endpoints"


def test_api_shape_styles_in_openapi_spec(client):
    """The new ``/api/shape-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/shape-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/shape-styles"
    )
    op = spec["paths"]["/api/shape-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_greeble_types_ok(client):
    """``GET /api/greeble-types`` mirrors the ``--list-greeble-types`` CLI
    flag: returns just the ``GreebleType`` enum values in enum-declaration
    order under a single ``greeble_types`` key."""
    from spaceship_generator.greeble_styles import GreebleType

    resp = client.get("/api/greeble-types")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"greeble_types"}
    assert isinstance(data["greeble_types"], list)
    assert len(data["greeble_types"]) > 0
    # Every declared GreebleType.value must be present.
    declared = [t.value for t in GreebleType]
    for value in declared:
        assert value in data["greeble_types"], f"missing greeble type {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["greeble_types"] == declared


def test_api_greeble_types_listed_in_openapi_spec(client):
    """The new ``/api/greeble-types`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/greeble-types" in spec["paths"], (
        "OpenAPI spec must enumerate /api/greeble-types"
    )
    op = spec["paths"]["/api/greeble-types"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_weapon_types_ok(client):
    """``GET /api/weapon-types`` returns just the ``WeaponType`` enum
    values in enum-declaration order under a single ``weapon_types`` key.

    Companion to ``/api/shape-styles`` — narrower JSON sibling of
    ``/api/styles`` exposing only the weapon archetype catalog.
    """
    from spaceship_generator.weapon_styles import WeaponType

    resp = client.get("/api/weapon-types")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"weapon_types"}
    assert isinstance(data["weapon_types"], list)
    assert len(data["weapon_types"]) > 0
    # Every declared WeaponType.value must be present.
    declared = [t.value for t in WeaponType]
    for value in declared:
        assert value in data["weapon_types"], f"missing weapon type {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["weapon_types"] == declared


def test_api_weapon_types_listed_in_openapi_spec(client):
    """The new ``/api/weapon-types`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/weapon-types" in spec["paths"], (
        "OpenAPI spec must enumerate /api/weapon-types"
    )
    op = spec["paths"]["/api/weapon-types"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_cockpit_styles_ok(client):
    """``GET /api/cockpit-styles`` returns just the ``CockpitStyle`` enum
    values in enum-declaration order under a single ``cockpit_styles`` key.

    Companion to ``/api/shape-styles`` / ``/api/greeble-types`` /
    ``/api/weapon-types`` — narrower JSON sibling of ``/api/styles``
    exposing only the cockpit archetype catalog.
    """
    from spaceship_generator.shape.core import CockpitStyle

    resp = client.get("/api/cockpit-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"cockpit_styles"}
    assert isinstance(data["cockpit_styles"], list)
    assert len(data["cockpit_styles"]) > 0
    # Every declared CockpitStyle.value must be present.
    declared = [c.value for c in CockpitStyle]
    for value in declared:
        assert value in data["cockpit_styles"], f"missing cockpit style {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["cockpit_styles"] == declared


def test_api_cockpit_styles_listed_in_openapi_spec(client):
    """The new ``/api/cockpit-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/cockpit-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/cockpit-styles"
    )
    op = spec["paths"]["/api/cockpit-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_structure_styles_ok(client):
    """``GET /api/structure-styles`` returns just the ``StructureStyle`` enum
    values in enum-declaration order under a single ``structure_styles`` key.

    Companion to ``/api/shape-styles`` / ``/api/greeble-types`` /
    ``/api/weapon-types`` / ``/api/cockpit-styles`` — narrower JSON sibling
    of ``/api/styles`` exposing only the structure archetype catalog.
    """
    from spaceship_generator.structure_styles import StructureStyle

    resp = client.get("/api/structure-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"structure_styles"}
    assert isinstance(data["structure_styles"], list)
    assert len(data["structure_styles"]) > 0
    # Every declared StructureStyle.value must be present.
    declared = [s.value for s in StructureStyle]
    for value in declared:
        assert value in data["structure_styles"], f"missing structure style {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["structure_styles"] == declared


def test_api_structure_styles_listed_in_openapi_spec(client):
    """The new ``/api/structure-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/structure-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/structure-styles"
    )
    op = spec["paths"]["/api/structure-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_hull_styles_ok(client):
    """``GET /api/hull-styles`` returns just the ``HullStyle`` enum values
    in enum-declaration order under a single ``hull_styles`` key.

    Companion to ``/api/shape-styles`` / ``/api/greeble-types`` /
    ``/api/weapon-types`` / ``/api/cockpit-styles`` /
    ``/api/structure-styles`` — narrower JSON sibling of ``/api/styles``
    exposing only the hull archetype catalog.
    """
    from spaceship_generator.structure_styles import HullStyle

    resp = client.get("/api/hull-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"hull_styles"}
    assert isinstance(data["hull_styles"], list)
    assert len(data["hull_styles"]) > 0
    # Every declared HullStyle.value must be present.
    declared = [h.value for h in HullStyle]
    for value in declared:
        assert value in data["hull_styles"], f"missing hull style {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["hull_styles"] == declared


def test_api_hull_styles_listed_in_openapi_spec(client):
    """The new ``/api/hull-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/hull-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/hull-styles"
    )
    op = spec["paths"]["/api/hull-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_engine_styles_ok(client):
    """``GET /api/engine-styles`` returns just the ``EngineStyle`` enum
    values in enum-declaration order under a single ``engine_styles`` key.

    Companion to ``/api/shape-styles`` / ``/api/greeble-types`` /
    ``/api/weapon-types`` / ``/api/cockpit-styles`` /
    ``/api/structure-styles`` — narrower JSON sibling of ``/api/styles``
    exposing only the engine archetype catalog.
    """
    from spaceship_generator.engine_styles import EngineStyle

    resp = client.get("/api/engine-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"engine_styles"}
    assert isinstance(data["engine_styles"], list)
    assert len(data["engine_styles"]) > 0
    # Every declared EngineStyle.value must be present.
    declared = [e.value for e in EngineStyle]
    for value in declared:
        assert value in data["engine_styles"], f"missing engine style {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["engine_styles"] == declared


def test_api_engine_styles_listed_in_openapi_spec(client):
    """The new ``/api/engine-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/engine-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/engine-styles"
    )
    op = spec["paths"]["/api/engine-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_wing_styles_ok(client):
    """``GET /api/wing-styles`` returns just the ``WingStyle`` enum values
    in enum-declaration order under a single ``wing_styles`` key.

    Companion to ``/api/shape-styles`` / ``/api/greeble-types`` /
    ``/api/weapon-types`` / ``/api/cockpit-styles`` /
    ``/api/structure-styles`` — narrower JSON sibling of ``/api/styles``
    exposing only the wing archetype catalog.
    """
    from spaceship_generator.wing_styles import WingStyle

    resp = client.get("/api/wing-styles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"wing_styles"}
    assert isinstance(data["wing_styles"], list)
    assert len(data["wing_styles"]) > 0
    # Every declared WingStyle.value must be present.
    declared = [w.value for w in WingStyle]
    for value in declared:
        assert value in data["wing_styles"], f"missing wing style {value!r}"
    # Order must match enum-declaration order — same contract as
    # ``/api/styles`` and ``/api/shape-styles``.
    assert data["wing_styles"] == declared


def test_api_wing_styles_listed_in_openapi_spec(client):
    """The new ``/api/wing-styles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/wing-styles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/wing-styles"
    )
    op = spec["paths"]["/api/wing-styles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_roles_ok(client):
    """``GET /api/roles`` returns the ``Role`` enum as ``{name, value}``
    pairs in declaration order under a single ``roles`` key.

    Narrower JSON sibling of ``/api/styles`` / ``/api/meta`` exposing the
    integer values used in the ``shape_grid`` int8 array. Payload mirrors
    CLI ``--list-roles-json`` exactly.
    """
    from spaceship_generator.palette import Role

    resp = client.get("/api/roles")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"roles"}
    assert isinstance(data["roles"], list)
    assert len(data["roles"]) > 0
    for entry in data["roles"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"name", "value"}
        assert isinstance(entry["name"], str)
        assert isinstance(entry["value"], int)
    # Order + content must match enum-declaration order — same contract
    # as the CLI ``--list-roles-json`` flag.
    expected = [{"name": r.name, "value": int(r)} for r in Role]
    assert data["roles"] == expected


def test_api_roles_listed_in_openapi_spec(client):
    """The new ``/api/roles`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/roles" in spec["paths"], (
        "OpenAPI spec must enumerate /api/roles"
    )
    op = spec["paths"]["/api/roles"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


def test_api_version_returns_json_with_version_key(client):
    """``GET /api/version`` returns ``{"version": "<X.Y.Z>"}`` — narrower
    JSON sibling of ``/api/health`` / ``/api/meta`` exposing only the
    package version string. Companion to ``/api/roles``,
    ``/api/hull-styles``, etc.
    """
    resp = client.get("/api/version")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = resp.get_json()
    assert set(data.keys()) == {"version"}
    assert isinstance(data["version"], str)
    assert data["version"] != "", "version must be a non-empty string"
    # The endpoint must agree with whatever ``/api/health`` reports — same
    # source of truth, two different shapes.
    health = client.get("/api/health").get_json()
    assert data["version"] == health["version"]


def test_api_version_in_openapi_spec(client):
    """The new ``/api/version`` path must appear in ``/api/spec``."""
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    spec = rv.get_json()
    assert "/api/version" in spec["paths"], (
        "OpenAPI spec must enumerate /api/version"
    )
    op = spec["paths"]["/api/version"]["get"]
    assert "summary" in op
    assert "200" in op["responses"]


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


# --- /api/spec --------------------------------------------------------------


def _expected_api_paths():
    """Walk the live Flask url map, return the set of /api/* path templates
    in OpenAPI form (``<string:name>`` → ``{name}``, ``<gen_id>`` → ``{gen_id}``)."""
    import re

    from spaceship_generator.web.app import create_app

    app = create_app()
    out: set[str] = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        # Flask's converter syntax ``<conv:name>`` or ``<name>`` → OpenAPI ``{name}``.
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        out.add(path)
    return out


def test_api_spec_status_and_content_type(client):
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    # Flask's jsonify uses application/json; some servers may suffix
    # ``; charset=utf-8`` so accept either form.
    ctype = rv.headers.get("Content-Type", "")
    assert ctype.startswith("application/json")


def test_api_spec_is_json_parseable_openapi_3(client):
    rv = client.get("/api/spec")
    assert rv.status_code == 200
    # get_json() will raise / return None if the body isn't JSON.
    data = rv.get_json()
    assert isinstance(data, dict), "spec body must be a JSON object"
    # Top-level OpenAPI 3.x markers
    assert "openapi" in data
    assert isinstance(data["openapi"], str)
    assert data["openapi"].startswith("3."), data["openapi"]
    assert "info" in data and isinstance(data["info"], dict)
    assert "title" in data["info"]
    assert "version" in data["info"]
    assert "paths" in data and isinstance(data["paths"], dict)


def test_api_spec_lists_every_route(client):
    """The spec's ``paths`` dict must include every live /api/* endpoint."""
    rv = client.get("/api/spec")
    data = rv.get_json()
    spec_paths = set(data["paths"].keys())
    expected = _expected_api_paths()
    missing = expected - spec_paths
    extra = spec_paths - expected
    assert not missing, f"OpenAPI spec is missing routes: {sorted(missing)}"
    # Extras would mean we documented a non-existent endpoint — also a bug.
    assert not extra, f"OpenAPI spec lists unknown routes: {sorted(extra)}"


def test_api_spec_each_path_has_method_summary_and_response(client):
    rv = client.get("/api/spec")
    data = rv.get_json()
    for path, methods in data["paths"].items():
        assert isinstance(methods, dict) and methods, f"{path} has no methods"
        for method, op in methods.items():
            assert method in {"get", "post", "put", "patch", "delete"}, (
                f"{path}: unexpected method {method!r}"
            )
            assert "summary" in op, f"{path} {method}: missing summary"
            assert isinstance(op["summary"], str) and op["summary"].strip()
            assert "responses" in op, f"{path} {method}: missing responses"
            assert "200" in op["responses"], (
                f"{path} {method}: missing 200 response"
            )


# --- /api/health ------------------------------------------------------------


def test_api_health_ok(client):
    """Liveness probe: 200 + JSON with status/version/uptime_s keys."""
    from spaceship_generator import __version__ as pkg_version

    rv = client.get("/api/health")
    assert rv.status_code == 200
    ctype = rv.headers.get("Content-Type", "")
    assert ctype.startswith("application/json"), ctype
    data = rv.get_json()
    assert isinstance(data, dict)
    assert set(data.keys()) >= {"status", "version", "uptime_s"}
    assert data["status"] == "ok"
    assert data["version"] == pkg_version
    assert isinstance(data["uptime_s"], int)
    assert data["uptime_s"] >= 0


def test_api_health_no_store_cache_control(client):
    """Health must not be cached — every probe sees a fresh reading."""
    rv = client.get("/api/health")
    assert rv.status_code == 200
    assert rv.headers.get("Cache-Control") == "no-store"
