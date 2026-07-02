"""Tests for v2 cockpit placement — framed deck cockpits."""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape.blueprint import build_plan
from spaceship_generator.shape.cockpit import _place_cockpit
from spaceship_generator.shape.core import CockpitStyle, ShapeParams
from spaceship_generator.shape.hull import _place_hull

_NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _grid_with_cockpit(style: CockpitStyle, seed: int = 42):
    params = ShapeParams(cockpit_style=style)
    rng = np.random.default_rng(seed)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    _place_cockpit(grid, rng, params, plan)
    return grid, plan


@pytest.mark.parametrize("style", list(CockpitStyle))
def test_cockpit_glass_exists(style):
    grid, _ = _grid_with_cockpit(style)
    assert (grid == Role.COCKPIT_GLASS).any()


@pytest.mark.parametrize("style", list(CockpitStyle))
def test_every_glass_voxel_touches_hull(style):
    """Framed rule: no floating glass — every glass voxel has >= 1 HULL
    6-neighbor (deck below, frame beside, or collar around)."""
    grid, _ = _grid_with_cockpit(style)
    W, H, L = grid.shape
    for x, y, z in np.argwhere(grid == Role.COCKPIT_GLASS):
        touches = False
        for dx, dy, dz in _NEIGHBORS:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < W and 0 <= ny < H and 0 <= nz < L:
                if grid[nx, ny, nz] == Role.HULL:
                    touches = True
                    break
        assert touches, f"{style}: floating glass at {(int(x), int(y), int(z))}"


@pytest.mark.parametrize("style", list(CockpitStyle))
def test_glass_confined_to_planned_rect(style):
    """Glass never appears behind the planned rect. POINTED and WRAP_BRIDGE
    intentionally run forward onto the nose; OFFSET_TURRET is intentionally
    offset in X. Everything else stays inside the rect."""
    grid, plan = _grid_with_cockpit(style)
    W = grid.shape[0]
    cx = (W - 1) / 2.0
    cp = plan.cockpit
    coords = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert (coords[:, 2] >= cp.z0 - 1).all()
    if style not in (CockpitStyle.POINTED, CockpitStyle.WRAP_BRIDGE):
        assert (coords[:, 2] <= cp.z1 + 1).all()
    if style != CockpitStyle.OFFSET_TURRET:
        assert (np.abs(coords[:, 0] - cx) <= cp.half_w + 1.5).all()


def test_styles_produce_distinct_cockpits():
    grids = {s: _grid_with_cockpit(s)[0] for s in CockpitStyle}
    styles = list(CockpitStyle)
    distinct_pairs = 0
    total = 0
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            total += 1
            if not np.array_equal(grids[styles[i]], grids[styles[j]]):
                distinct_pairs += 1
    assert distinct_pairs == total, "every cockpit style must differ"
