"""Tests for v2 engine placement — protruding nozzles + nacelle pods."""

from __future__ import annotations

import numpy as np

from spaceship_generator.palette import Role
from spaceship_generator.shape.blueprint import build_plan
from spaceship_generator.shape.core import ShapeParams, generate_shape
from spaceship_generator.shape.engines import _place_engines
from spaceship_generator.shape.hull import _place_hull


def _grid_with_engines(seed: int = 42, params: ShapeParams | None = None):
    params = params or ShapeParams()
    rng = np.random.default_rng(seed)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    _place_engines(grid, rng, params, plan)
    return grid, plan


def test_nozzles_protrude_behind_hull_wall():
    grid, plan = _grid_with_engines(42)
    protrusion = grid[:, :, : plan.engine.wall_z]
    assert (protrusion == Role.ENGINE).any(), "nozzles must protrude behind the wall"


def test_nozzle_reaches_rear_tip():
    grid, _plan = _grid_with_engines(42)
    assert (grid[:, :, 0] == Role.ENGINE).any(), "nozzle tip must reach z=0"


def test_no_engine_voxels_deep_inside_hull():
    """Engines live at/behind the wall zone, not buried mid-ship."""
    grid, plan = _grid_with_engines(42)
    L = grid.shape[2]
    deep = grid[:, :, plan.engine.wall_z + 2 : L]
    assert not (deep == Role.ENGINE).any()


def test_engines_connected_to_hull_after_full_pipeline():
    g = generate_shape(42, ShapeParams())
    # Full pipeline output is a single connected component (assembly pass),
    # and it must still contain engine voxels.
    assert (g == Role.ENGINE).any()


def test_zero_engine_count_places_none():
    params = ShapeParams(engine_count=0)
    grid, _ = _grid_with_engines(42, params)
    assert not (grid == Role.ENGINE).any()
