"""Tests for role refinement (texture.py)."""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape import ShapeParams, generate_shape
from spaceship_generator.texture import TextureParams, assign_roles


@pytest.fixture
def grid():
    return generate_shape(
        99, ShapeParams(length=40, width_max=20, height_max=12, greeble_density=0.05)
    )


def test_assign_roles_preserves_filled_cells(grid):
    out = assign_roles(grid)
    filled_before = grid != Role.EMPTY
    filled_after = out != Role.EMPTY
    assert np.array_equal(filled_before, filled_after)


def test_assign_roles_returns_copy(grid):
    out = assign_roles(grid)
    assert out is not grid
    assert not np.shares_memory(out, grid)


def test_assign_roles_preserves_symmetry(grid):
    out = assign_roles(grid)
    # grid is X-symmetric → output must stay X-symmetric
    assert np.array_equal(out, out[::-1, :, :])


def test_assign_roles_produces_interior(grid):
    out = assign_roles(grid)
    assert (out == Role.INTERIOR).sum() > 0


def test_assign_roles_produces_windows(grid):
    out = assign_roles(grid)
    assert (out == Role.WINDOW).sum() > 0


def test_assign_roles_produces_engine_glow(grid):
    out = assign_roles(grid)
    glow = np.argwhere(out == Role.ENGINE_GLOW)
    assert len(glow) > 0
    # All glow cells at rear (z == 0 with default glow depth)
    assert glow[:, 2].max() == 0


def test_assign_roles_keeps_cockpit_glass(grid):
    out = assign_roles(grid)
    cockpit_before = (grid == Role.COCKPIT_GLASS).sum()
    cockpit_after = (out == Role.COCKPIT_GLASS).sum()
    assert cockpit_after == cockpit_before


def test_assign_roles_no_hull_left_if_interior_accounted_for(grid):
    out = assign_roles(grid)
    # Some HULL cells survive on the surface (not windows, not stripes) — fine.
    # But no INTERIOR cell should be on the surface and no non-surface HULL should remain.
    from spaceship_generator.shape import _surface_mask
    surface = _surface_mask(out != Role.EMPTY)  # shape doesn't matter, we just want filled mask
    # Interior cells must not be surface
    interior = out == Role.INTERIOR
    # Re-derive surface from the filled mask of the refined grid:
    filled = out != Role.EMPTY
    # Build surface mask directly on filled
    surface = _surface_mask(filled.astype(np.int8))
    assert not ((interior & surface).any())


def test_assign_roles_windows_only_on_upper_hull():
    # Build a simple fake hull: a rectangular slab.
    grid = np.full((10, 10, 20), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    out = assign_roles(grid, TextureParams(window_period_cells=4))
    windows = np.argwhere(out == Role.WINDOW)
    # All windows should be in the upper half (y > 4.5)
    assert len(windows) > 0
    assert windows[:, 1].min() >= 5


def test_assign_roles_with_engine_and_wing():
    grid = np.full((10, 10, 20), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    # Engine at z=0..2
    grid[4:6, 4:6, 0:3] = Role.ENGINE
    # Wings
    grid[0:2, 4:6, 8:14] = Role.WING
    grid[8:10, 4:6, 8:14] = Role.WING

    out = assign_roles(grid, TextureParams(engine_glow_depth=2))
    # Rear-most engine slabs become glow
    assert (out[:, :, 0] == Role.ENGINE_GLOW).sum() > 0
    assert (out[:, :, 1] == Role.ENGINE_GLOW).sum() > 0
    # Wings contain at least one LIGHT at the leading edge on outer X
    lights = np.argwhere(out == Role.LIGHT)
    assert len(lights) > 0
    outer_x = {0, 9}
    assert all(int(l[0]) in outer_x for l in lights)


def test_assign_roles_rejects_non_3d():
    with pytest.raises(ValueError):
        assign_roles(np.zeros((3, 3)))


def test_assign_roles_no_wings_no_lights():
    grid = np.full((8, 8, 8), Role.EMPTY, dtype=np.int8)
    grid[2:6, 2:6, 2:6] = Role.HULL
    out = assign_roles(grid)
    assert (out == Role.LIGHT).sum() == 0


def test_assign_roles_deterministic(grid):
    a = assign_roles(grid)
    b = assign_roles(grid)
    assert np.array_equal(a, b)


def test_assign_roles_produces_dark_stripe():
    grid = np.full((10, 10, 30), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:28] = Role.HULL
    out = assign_roles(grid, TextureParams(accent_stripe_period=6))
    assert (out == Role.HULL_DARK).sum() > 0
