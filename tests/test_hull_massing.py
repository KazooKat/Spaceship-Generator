"""Tests for the v2 superellipse segmented hull massing."""

from __future__ import annotations

import numpy as np

from spaceship_generator.palette import Role
from spaceship_generator.shape.blueprint import build_plan
from spaceship_generator.shape.core import ShapeParams, generate_shape
from spaceship_generator.shape.hull import _place_hull


def _hull_only_grid(seed: int = 42, params: ShapeParams | None = None) -> np.ndarray:
    params = params or ShapeParams()
    rng = np.random.default_rng(seed)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    return grid


def test_hull_has_flat_side_panel():
    """At mid-Z the outermost hull column must be flat over >= 3 y-cells."""
    params = ShapeParams(length=40, width_max=20, height_max=12)
    grid = _hull_only_grid(42, params)
    z = params.length // 2
    xs = np.argwhere((grid[:, :, z] == Role.HULL).any(axis=1))[:, 0]
    x_min = int(xs.min())
    col = grid[x_min, :, z] == Role.HULL
    assert int(col.sum()) >= 3, "outermost column should be a flat side panel"


def test_hull_has_flat_deck():
    """At mid-Z the topmost hull row must be flat over >= 3 x-cells."""
    params = ShapeParams(length=40, width_max=20, height_max=12)
    grid = _hull_only_grid(42, params)
    z = params.length // 2
    ys = np.argwhere((grid[:, :, z] == Role.HULL).any(axis=0))[:, 0]
    y_max = int(ys.max())
    row = grid[:, y_max, z] == Role.HULL
    assert int(row.sum()) >= 3, "topmost row should be a flat deck"


def test_hull_leaves_wing_room():
    """Hull half-width stays <= 45% of grid width."""
    params = ShapeParams(length=40, width_max=20, height_max=12)
    grid = _hull_only_grid(42, params)
    cx = (params.width_max - 1) / 2.0
    hull_xs = np.argwhere((grid == Role.HULL).any(axis=(1, 2)))[:, 0]
    max_half = max(abs(x - cx) for x in hull_xs)
    assert max_half <= params.width_max * 0.45


def test_hull_empty_before_wall():
    """No hull voxels in the nozzle protrusion zone [0, wall_z)."""
    params = ShapeParams(length=40, width_max=20, height_max=12)
    rng = np.random.default_rng(42)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    assert not (grid[:, :, : plan.engine.wall_z] == Role.HULL).any()


def test_generate_shape_still_deterministic():
    a = generate_shape(123, ShapeParams())
    b = generate_shape(123, ShapeParams())
    assert np.array_equal(a, b)


def test_generate_shape_x_symmetric():
    g = generate_shape(99, ShapeParams())
    assert np.array_equal(g, g[::-1, :, :])
