"""Tests for parts-based ship shape generation."""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape import (
    CockpitStyle,
    ShapeParams,
    _body_profile,
    _engine_x_positions,
    _surface_mask,
    generate_shape,
)


# ----- ShapeParams validation -----

@pytest.mark.parametrize("bad", [
    dict(length=4),
    dict(width_max=2),
    dict(height_max=2),
    dict(engine_count=-1),
    dict(engine_count=99),
    dict(wing_prob=-0.1),
    dict(wing_prob=1.5),
    dict(greeble_density=-0.1),
    dict(greeble_density=0.9),
])
def test_shape_params_validate(bad):
    with pytest.raises(ValueError):
        ShapeParams(**bad)


def test_shape_params_defaults():
    p = ShapeParams()
    assert p.length == 40
    assert p.cockpit_style == CockpitStyle.BUBBLE


# ----- generate_shape basics -----

def test_generate_shape_returns_array_of_correct_shape():
    p = ShapeParams(length=30, width_max=16, height_max=10)
    grid = generate_shape(1, p)
    assert grid.shape == (16, 10, 30)
    assert grid.dtype == np.int8


def test_generate_shape_has_content():
    grid = generate_shape(7, ShapeParams(length=30, width_max=16, height_max=10))
    assert (grid != Role.EMPTY).sum() > 50


def test_generate_shape_reproducible():
    p = ShapeParams(length=30, width_max=16, height_max=10)
    a = generate_shape(42, p)
    b = generate_shape(42, p)
    assert np.array_equal(a, b)


def test_generate_shape_different_seeds_differ():
    p = ShapeParams(length=30, width_max=16, height_max=10, greeble_density=0.15)
    a = generate_shape(1, p)
    b = generate_shape(2, p)
    assert not np.array_equal(a, b)


def test_generate_shape_bilateral_symmetry():
    grid = generate_shape(7, ShapeParams(length=30, width_max=16, height_max=10))
    # grid[x, y, z] == grid[W-1-x, y, z]
    flipped = grid[::-1, :, :]
    assert np.array_equal(grid, flipped)


def test_generate_shape_has_hull_cockpit_engines():
    grid = generate_shape(3, ShapeParams(length=40, width_max=20, height_max=12, engine_count=2))
    # Must contain HULL
    assert (grid == Role.HULL).sum() > 100
    # Must contain COCKPIT_GLASS somewhere near the nose (high z)
    cockpit_positions = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert len(cockpit_positions) > 0
    assert cockpit_positions[:, 2].max() >= 30  # near front
    # Must contain ENGINE at the rear (low z)
    engine_positions = np.argwhere(grid == Role.ENGINE)
    assert len(engine_positions) > 0
    assert engine_positions[:, 2].min() == 0


def test_generate_shape_zero_engines():
    grid = generate_shape(
        3, ShapeParams(length=40, width_max=20, height_max=12, engine_count=0)
    )
    assert (grid == Role.ENGINE).sum() == 0


def test_generate_shape_wing_prob_zero():
    grid = generate_shape(
        3, ShapeParams(length=40, width_max=20, height_max=12, wing_prob=0.0)
    )
    assert (grid == Role.WING).sum() == 0


def test_generate_shape_no_greebles_when_density_zero():
    grid = generate_shape(
        3, ShapeParams(length=40, width_max=20, height_max=12, greeble_density=0.0)
    )
    assert (grid == Role.GREEBLE).sum() == 0


def test_generate_shape_greebles_appear_when_density_positive():
    grid = generate_shape(
        3, ShapeParams(length=40, width_max=20, height_max=12, greeble_density=0.25)
    )
    assert (grid == Role.GREEBLE).sum() > 0


def test_generate_shape_stays_in_bounds():
    p = ShapeParams(length=40, width_max=20, height_max=12)
    grid = generate_shape(1, p)
    # numpy guarantees bounds by construction, but double-check dtype/shape:
    assert grid.shape == (20, 12, 40)


def test_generate_shape_accepts_none_params():
    # None params → defaults should work
    grid = generate_shape(0, None)
    assert grid.ndim == 3
    assert (grid != Role.EMPTY).sum() > 0


# ----- Helpers -----

def test_body_profile_peaks_in_middle():
    # Peak around t=0.55
    samples = [(_body_profile(t), t) for t in np.linspace(0, 1, 21)]
    peak_val, peak_t = max(samples)
    assert 0.4 < peak_t < 0.7
    assert 0.95 <= peak_val <= 1.0
    # Endpoints should be smaller
    assert _body_profile(0.0) < 0.4
    assert _body_profile(1.0) < 0.4


def test_body_profile_returns_unit_range():
    for t in np.linspace(0, 1, 11):
        v = _body_profile(float(t))
        assert 0.0 <= v <= 1.0


def test_engine_x_positions_symmetric_pairs():
    # For n >= 2, positions come in mirrored pairs summing to width-1.
    for n in range(2, 6):
        xs = _engine_x_positions(n, width=21, radius=1)  # odd width → clean center
        xs_sorted = sorted(xs)
        for lo, hi in zip(xs_sorted, reversed(xs_sorted)):
            assert lo + hi == 20  # width - 1 = 20


def test_engine_x_positions_single_centered():
    # n == 1 sits at (or near) the ship's X center.
    xs = _engine_x_positions(1, width=20, radius=1)
    assert len(xs) == 1
    assert xs[0] == 10  # width // 2


def test_engine_x_positions_odd_count_includes_center():
    xs = _engine_x_positions(3, width=21, radius=1)
    assert len(xs) == 3
    assert 10 in xs  # odd count on odd width → exact center present


def test_surface_mask_all_filled_has_only_outer_shell():
    grid = np.full((3, 3, 3), Role.HULL, dtype=np.int8)
    surface = _surface_mask(grid)
    # Outer shell = 3^3 - 1^3 = 26 (everything except the one fully-interior cell).
    assert surface.sum() == 26
    assert not surface[1, 1, 1]  # exact center is interior


def test_surface_mask_larger_cube_outer_shell():
    # 5^3 - 3^3 = 98 surface cells (hollow-looking outer shell).
    grid = np.full((5, 5, 5), Role.HULL, dtype=np.int8)
    surface = _surface_mask(grid)
    assert surface.sum() == 98


def test_surface_mask_hollow_center():
    grid = np.full((5, 5, 5), Role.HULL, dtype=np.int8)
    grid[2, 2, 2] = Role.EMPTY  # single empty in the middle
    surface = _surface_mask(grid)
    # Six neighbors of that empty cell are interior surface voxels; plus all outer faces
    assert surface[1, 2, 2]
    assert surface[3, 2, 2]
    assert surface[2, 1, 2]
    # Center of a face (not adjacent to the empty) is still surface (outer face)
    assert surface[0, 2, 2]


def test_surface_mask_all_empty_is_empty():
    grid = np.zeros((4, 4, 4), dtype=np.int8)
    assert _surface_mask(grid).sum() == 0
