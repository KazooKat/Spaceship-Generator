"""Tests for v2 wing placement — rooted, proportional, hull-preserving."""

from __future__ import annotations

import numpy as np

from spaceship_generator.palette import Role
from spaceship_generator.shape.blueprint import build_plan
from spaceship_generator.shape.core import ShapeParams, generate_shape
from spaceship_generator.shape.hull import _place_hull
from spaceship_generator.shape.wings import _place_wings


def _grid_with_wings(seed: int = 42, params: ShapeParams | None = None):
    params = params or ShapeParams(wing_prob=1.0)
    rng = np.random.default_rng(seed)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    hull_before = int((grid == Role.HULL).sum())
    _place_wings(grid, rng, params, plan)
    return grid, plan, hull_before


def test_wings_present_and_touch_hull():
    grid, _plan, _ = _grid_with_wings(42)
    wings = np.argwhere(grid == Role.WING)
    assert len(wings) > 0
    # At least one wing voxel must have a HULL 6-neighbor (rooted contact).
    W, H, L = grid.shape
    touching = False
    for x, y, z in wings:
        for dx, dy, dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            nx, ny, nz = x+dx, y+dy, z+dz
            if 0 <= nx < W and 0 <= ny < H and 0 <= nz < L:
                if grid[nx, ny, nz] == Role.HULL:
                    touching = True
                    break
        if touching:
            break
    assert touching, "wing must touch the hull"


def test_wings_never_overwrite_hull():
    grid, _plan, hull_before = _grid_with_wings(42)
    assert int((grid == Role.HULL).sum()) == hull_before


def test_wing_reaches_grid_edge_zone():
    grid, _plan, _ = _grid_with_wings(42)
    wings = np.argwhere(grid == Role.WING)
    assert int(wings[:, 0].min()) <= 1, "wing tip should reach near the grid edge"


def test_wing_thickness_at_least_two():
    grid, _plan, _ = _grid_with_wings(42)
    wings = np.argwhere(grid == Role.WING)
    # At the innermost wing column, y-extent must span >= 2 rows.
    x_root = int(wings[:, 0].max())
    ys = wings[wings[:, 0] == x_root][:, 1]
    assert ys.max() - ys.min() + 1 >= 2


def test_wing_prob_zero_places_none():
    params = ShapeParams(wing_prob=0.0)
    g = generate_shape(7, params)
    assert not (g == Role.WING).any()
