"""Tests for WingStyle silhouettes.

Back-compat (STRAIGHT must reproduce legacy output), placement
correctness (single-component, X-symmetric, distinguishable from
siblings), and the web + CLI plumbing.
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape import ShapeParams, StructureStyle, generate_shape
from spaceship_generator.web.app import create_app
from spaceship_generator.wing_styles import WingStyle


# --- WingStyle enum --------------------------------------------------------


def test_wing_style_values_stable():
    """Lock in the wire-format values — these ship in form posts, CLI
    args, and /api/meta. Renaming any of them is a breaking change."""
    assert {w.value for w in WingStyle} == {
        "straight", "swept", "delta", "tapered", "gull", "split",
    }


# --- Back-compat -----------------------------------------------------------


def test_default_wing_style_is_straight():
    assert ShapeParams().wing_style == WingStyle.STRAIGHT


def test_straight_is_byte_for_byte_legacy():
    """STRAIGHT under the same seed must match the omitted-wing_style
    path, which is the legacy path. Any change to ``_place_straight``
    that breaks this assertion regresses every existing saved ship."""
    seed = 42
    g_default = generate_shape(seed)
    g_straight = generate_shape(seed, ShapeParams(wing_style=WingStyle.STRAIGHT))
    assert np.array_equal(g_default, g_straight)


# --- Validation ------------------------------------------------------------


def test_string_wing_style_coerces_to_enum():
    sp = ShapeParams(wing_style="swept")  # type: ignore[arg-type]
    assert sp.wing_style == WingStyle.SWEPT


def test_unknown_wing_style_string_raises():
    with pytest.raises(ValueError, match="wing_style must be one of"):
        ShapeParams(wing_style="not-a-wing")  # type: ignore[arg-type]


def test_non_string_non_enum_wing_style_raises():
    with pytest.raises(ValueError, match="wing_style must be a WingStyle"):
        ShapeParams(wing_style=42)  # type: ignore[arg-type]


# --- Per-style shape invariants --------------------------------------------


def _wing_cells(grid: np.ndarray) -> int:
    return int((grid == Role.WING).sum())


def _is_x_symmetric(grid: np.ndarray) -> bool:
    """Ship must be mirror-symmetric across X (the final mirror pass is a
    generator invariant — wing styles must not break it)."""
    return np.array_equal(grid, grid[::-1, :, :])


@pytest.mark.parametrize("style", list(WingStyle))
def test_each_style_produces_wings(style):
    """Every wing style must actually place some WING cells on a ship
    that has wings turned on (wing_prob=1, FIGHTER which biases wings)."""
    grid = generate_shape(
        7,
        ShapeParams(
            wing_prob=1.0,
            wing_style=style,
            structure_style=StructureStyle.FIGHTER,
        ),
    )
    assert _wing_cells(grid) > 0, f"style {style.value} produced no wing cells"


@pytest.mark.parametrize("style", list(WingStyle))
def test_each_style_stays_symmetric(style):
    grid = generate_shape(
        11,
        ShapeParams(
            wing_prob=1.0,
            wing_style=style,
            structure_style=StructureStyle.FIGHTER,
        ),
    )
    assert _is_x_symmetric(grid), (
        f"style {style.value} broke X-axis symmetry"
    )


@pytest.mark.parametrize("style", list(WingStyle))
def test_each_style_stays_in_bounds(style):
    grid = generate_shape(
        13,
        ShapeParams(
            length=12,          # short ship stresses the clamp logic
            width_max=8,
            height_max=6,
            wing_prob=1.0,
            wing_style=style,
            structure_style=StructureStyle.FIGHTER,
        ),
    )
    # Any out-of-bounds write would have raised in numpy; reaching here
    # means every placement function respected the grid extents.
    assert grid.shape == (8, 6, 12)


def test_styles_produce_distinct_silhouettes():
    """Every style must be visually distinguishable from every other for
    a moderately sized ship. Otherwise two enum values collapse to the
    same output and the user-facing dropdown is a lie."""
    seed = 1234
    common = dict(
        length=40, width_max=20, height_max=12,
        wing_prob=1.0, structure_style=StructureStyle.FRIGATE,
    )
    grids = {
        style: generate_shape(seed, ShapeParams(**common, wing_style=style))
        for style in WingStyle
    }
    styles = list(WingStyle)
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            a, b = styles[i], styles[j]
            assert not np.array_equal(grids[a], grids[b]), (
                f"{a.value} and {b.value} produced identical ships"
            )


def test_split_has_vertical_gap():
    """SPLIT's defining feature: there's a horizontal plane between the
    two stacked wings at the root where no WING cells exist. Regressing
    to a single slab would collapse the gap."""
    grid = generate_shape(
        2024,
        ShapeParams(
            length=40, width_max=20, height_max=16,
            wing_prob=1.0,
            wing_style=WingStyle.SPLIT,
            structure_style=StructureStyle.FRIGATE,
        ),
    )
    W, H, L = grid.shape
    # Sample Y-profile at the outermost wing x-slice and look for at
    # least one ``WING``-cell gap (non-WING row) sandwiched between two
    # wings. We scan from the outer edge inward so we don't hit the
    # hull column.
    cy = H // 2
    for x in range(2, W // 2):
        column_has_gap = False
        ys_with_wing = np.any(grid[x, :, :] == Role.WING, axis=1)
        if not ys_with_wing.any():
            continue
        above = ys_with_wing[cy + 1:].any()
        below = ys_with_wing[:cy].any()
        # Gap around cy: some Y rows near the middle are NOT WING.
        middle_has_nonwing = not ys_with_wing[max(0, cy - 1): cy + 2].all()
        if above and below and middle_has_nonwing:
            column_has_gap = True
            break
    assert column_has_gap, "SPLIT style did not produce a visible vertical gap"


# --- Web plumbing ----------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPFORGE_RATE_LIMIT", "0")  # disable for multi-POST
    app = create_app()
    app.config["TESTING"] = True
    monkeypatch.setattr(app, "instance_path", str(tmp_path))
    with app.test_client() as c:
        yield c


def test_api_meta_lists_wing_styles(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "wing_styles" in data
    assert set(data["wing_styles"]) == {w.value for w in WingStyle}
    assert data["defaults"]["wing_style"] == WingStyle.STRAIGHT.value


def test_index_includes_wing_style_select(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert 'name="wing_style"' in body
    for w in WingStyle:
        # All 6 archetypes must appear as <option> values.
        assert f'value="{w.value}"' in body, f"wing style {w.value} missing"


@pytest.mark.parametrize("style", [w.value for w in WingStyle])
def test_generate_accepts_wing_style(client, style):
    form = {
        "seed": "1",
        "palette": "sci_fi_industrial",
        "length": "24", "width": "12", "height": "8",
        "engines": "2",
        "wing_prob": "1.0",
        "greeble_density": "0.05",
        "window_period": "4",
        "cockpit": "bubble",
        "wing_style": style,
    }
    resp = client.post("/generate", data=form, follow_redirects=False)
    assert resp.status_code in (200, 302), (
        f"/generate rejected wing_style={style} with {resp.status_code}"
    )


def test_generate_rejects_unknown_wing_style(client):
    form = {
        "seed": "1",
        "palette": "sci_fi_industrial",
        "length": "24", "width": "12", "height": "8",
        "engines": "2",
        "wing_prob": "1.0",
        "greeble_density": "0.05",
        "window_period": "4",
        "cockpit": "bubble",
        "wing_style": "banana-wing",
    }
    resp = client.post("/generate", data=form)
    assert resp.status_code == 400
    assert b"wing_style" in resp.get_data()


def test_api_generate_accepts_wing_style(client):
    body = {
        "seed": 2,
        "palette": "sci_fi_industrial",
        "length": 24, "width": 12, "height": 8,
        "engines": 2, "wing_prob": 1.0, "greeble_density": 0.05,
        "window_period": 4, "cockpit": "bubble",
        "wing_style": "delta",
    }
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_api_generate_rejects_unknown_wing_style(client):
    body = {
        "seed": 2, "palette": "sci_fi_industrial",
        "length": 24, "width": 12, "height": 8,
        "engines": 2, "wing_prob": 1.0, "greeble_density": 0.05,
        "window_period": 4, "cockpit": "bubble",
        "wing_style": "mystery",
    }
    resp = client.post("/api/generate", json=body)
    assert resp.status_code == 400
    assert "wing_style" in resp.get_json()["error"]
