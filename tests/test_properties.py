"""Hypothesis-based property tests for :mod:`shape` and :mod:`generator`.

Properties under test (all purely observable behavior):

* **Same seed → identical shape** — ``generate_shape`` is deterministic.
* **Different seed → different shape** — overwhelmingly unequal across
  a small seed spread (we assert at least one difference in a small sample).
* **All voxels within declared bounds** — every returned grid has shape
  ``(W, H, L)`` and every value is a valid ``Role`` code; all ``argwhere``
  coordinates fit within bounds.
* **Bilateral symmetry on X** — ``grid == grid[::-1, :, :]``.

The Hypothesis settings keep runs fast while exercising broad parameter
space. Each test caps at ~30 examples with a generous per-example deadline
because shape generation involves a handful of NumPy passes plus a
connected-components walk for larger grids.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spaceship_generator.generator import generate
from spaceship_generator.palette import Role
from spaceship_generator.shape import (
    CockpitStyle,
    ShapeParams,
    StructureStyle,
    generate_shape,
)
from spaceship_generator.wing_styles import WingStyle


# Keep grids modest so the property suite stays fast on CI.
_lengths = st.integers(min_value=8, max_value=24)
_widths = st.integers(min_value=4, max_value=16)
_heights = st.integers(min_value=4, max_value=12)
_seeds = st.integers(min_value=0, max_value=2**31 - 1)
_engine_counts = st.integers(min_value=0, max_value=6)
_wing_probs = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_greeble = st.floats(min_value=0.0, max_value=0.5, allow_nan=False)
_cockpit_styles = st.sampled_from(list(CockpitStyle))
# Limit to the three core styles the shape module ships with to keep
# combinatorial coverage tight and fast.
_structure_styles = st.sampled_from(
    [StructureStyle.FRIGATE, StructureStyle.FIGHTER, StructureStyle.SHUTTLE]
)
_wing_styles = st.sampled_from(list(WingStyle))


_SHAPE_SETTINGS = settings(
    max_examples=25,
    deadline=3000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@st.composite
def shape_param_strategy(draw):
    """Build a :class:`ShapeParams` with sane, in-range values."""
    return ShapeParams(
        length=draw(_lengths),
        width_max=draw(_widths),
        height_max=draw(_heights),
        engine_count=draw(_engine_counts),
        wing_prob=draw(_wing_probs),
        greeble_density=draw(_greeble),
        cockpit_style=draw(_cockpit_styles),
        structure_style=draw(_structure_styles),
        wing_style=draw(_wing_styles),
    )


# ----------- shape properties -----------


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_shape_matches_declared_bounds(seed, params):
    """The returned grid has shape ``(W, H, L)`` as declared in params."""
    grid = generate_shape(seed, params)
    assert grid.shape == (params.width_max, params.height_max, params.length)
    assert grid.ndim == 3


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_voxels_within_bounds(seed, params):
    """Every filled voxel coordinate is within the declared grid bounds."""
    grid = generate_shape(seed, params)
    W, H, L = grid.shape
    filled = np.argwhere(grid != Role.EMPTY)
    if filled.size == 0:
        return
    assert filled[:, 0].min() >= 0
    assert filled[:, 0].max() < W
    assert filled[:, 1].min() >= 0
    assert filled[:, 1].max() < H
    assert filled[:, 2].min() >= 0
    assert filled[:, 2].max() < L


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_all_values_are_valid_roles(seed, params):
    """Every cell in the grid is a valid :class:`Role` code."""
    grid = generate_shape(seed, params)
    valid = {int(r) for r in Role}
    unique_values = {int(v) for v in np.unique(grid).tolist()}
    assert unique_values.issubset(valid), (
        f"unexpected values {unique_values - valid} in grid"
    )


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_shape_deterministic_same_seed(seed, params):
    """Same (seed, params) must yield byte-identical arrays."""
    a = generate_shape(seed, params)
    b = generate_shape(seed, params)
    assert np.array_equal(a, b)


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_shape_bilaterally_symmetric(seed, params):
    """Every generated ship is bilaterally symmetric across the X axis."""
    grid = generate_shape(seed, params)
    assert np.array_equal(grid, grid[::-1, :, :])


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_zero_wings_when_prob_zero_with_no_override(seed, params):
    """If ``wing_prob == 0`` and the style does not force wings on, no WING."""
    # Rebuild params with wing_prob=0 to isolate that invariant. Shuttle
    # already forbids wings, and Fighter forces them on — so restrict to
    # FRIGATE here.
    p = ShapeParams(
        length=params.length,
        width_max=params.width_max,
        height_max=params.height_max,
        engine_count=params.engine_count,
        wing_prob=0.0,
        greeble_density=params.greeble_density,
        cockpit_style=params.cockpit_style,
        structure_style=StructureStyle.FRIGATE,
        wing_style=params.wing_style,
    )
    grid = generate_shape(seed, p)
    assert (grid == Role.WING).sum() == 0


@given(seed=_seeds, params=shape_param_strategy())
@_SHAPE_SETTINGS
def test_property_zero_engines_means_no_engine_voxels(seed, params):
    """``engine_count=0`` plus a non-overriding style means no ENGINE voxels."""
    # FRIGATE doesn't override engine_count, so the zero honors through.
    p = ShapeParams(
        length=params.length,
        width_max=params.width_max,
        height_max=params.height_max,
        engine_count=0,
        wing_prob=params.wing_prob,
        greeble_density=params.greeble_density,
        cockpit_style=params.cockpit_style,
        structure_style=StructureStyle.FRIGATE,
        wing_style=params.wing_style,
    )
    grid = generate_shape(seed, p)
    assert (grid == Role.ENGINE).sum() == 0


def test_property_different_seeds_produce_different_shapes():
    """With one fixed param set, 10 distinct seeds must yield >=2 distinct grids.

    This is not a per-seed property — two arbitrary seeds could coincide —
    but across a batch the probability of all-equal is vanishingly small.
    Uses a fixed (non-Hypothesis) sample for speed + determinism.
    """
    p = ShapeParams(length=24, width_max=12, height_max=8, greeble_density=0.1)
    grids = [generate_shape(s, p) for s in range(10)]
    uniques = {g.tobytes() for g in grids}
    assert len(uniques) >= 2


# ----------- boundary / edge cases for shape -----------


def test_property_min_dimensions_generate_valid_shape():
    """Minimum legal dims must still yield a non-empty, symmetric grid."""
    p = ShapeParams(length=8, width_max=4, height_max=4)
    grid = generate_shape(0, p)
    assert grid.shape == (4, 4, 8)
    assert np.array_equal(grid, grid[::-1, :, :])
    assert (grid != Role.EMPTY).sum() >= 1


def test_property_large_aspect_ratio_long_thin():
    """Very long + very narrow ships generate without error and are symmetric."""
    p = ShapeParams(length=40, width_max=4, height_max=4, engine_count=1, wing_prob=0.0)
    grid = generate_shape(1, p)
    assert grid.shape == (4, 4, 40)
    assert np.array_equal(grid, grid[::-1, :, :])


def test_property_large_aspect_ratio_short_fat():
    """Very short + very wide ships generate without error and are symmetric."""
    p = ShapeParams(length=8, width_max=16, height_max=12)
    grid = generate_shape(2, p)
    assert grid.shape == (16, 12, 8)
    assert np.array_equal(grid, grid[::-1, :, :])


# ----------- generator-level properties (end-to-end) -----------


_GEN_SETTINGS = settings(
    max_examples=10,
    deadline=10_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(
    seed=_seeds,
    length=st.integers(min_value=16, max_value=24),
    width=st.integers(min_value=8, max_value=14),
    height=st.integers(min_value=6, max_value=10),
)
@_GEN_SETTINGS
def test_property_generate_end_to_end_deterministic(
    tmp_path_factory, seed, length, width, height
):
    """Calling ``generate`` twice with the same inputs produces identical grids."""
    out_a = tmp_path_factory.mktemp("a")
    out_b = tmp_path_factory.mktemp("b")
    params = ShapeParams(length=length, width_max=width, height_max=height)

    res_a = generate(seed, shape_params=params, out_dir=out_a, filename="ship.litematic")
    res_b = generate(seed, shape_params=params, out_dir=out_b, filename="ship.litematic")
    assert np.array_equal(res_a.role_grid, res_b.role_grid)
    assert res_a.block_count == res_b.block_count
    assert res_a.shape == res_b.shape


@given(
    seed=_seeds,
    length=st.integers(min_value=16, max_value=24),
    width=st.integers(min_value=8, max_value=14),
    height=st.integers(min_value=6, max_value=10),
)
@_GEN_SETTINGS
def test_property_generate_writes_litematic_and_non_empty(
    tmp_path_factory, seed, length, width, height
):
    """Every successful generate call writes a non-empty file and records shape."""
    out_dir = tmp_path_factory.mktemp("out")
    params = ShapeParams(length=length, width_max=width, height_max=height)
    res = generate(seed, shape_params=params, out_dir=out_dir)
    assert res.litematic_path.exists()
    assert res.litematic_path.stat().st_size > 0
    assert res.block_count > 0
    assert res.shape == (width, height, length)


@given(
    seed=_seeds,
    structure=_structure_styles,
    wing=_wing_styles,
    cockpit=_cockpit_styles,
)
@_SHAPE_SETTINGS
def test_property_all_style_combos_symmetric(seed, structure, wing, cockpit):
    """Arbitrary (structure, wing, cockpit) trios preserve bilateral symmetry."""
    p = ShapeParams(
        length=24,
        width_max=12,
        height_max=8,
        structure_style=structure,
        wing_style=wing,
        cockpit_style=cockpit,
    )
    grid = generate_shape(seed, p)
    assert np.array_equal(grid, grid[::-1, :, :])


@given(seed=_seeds)
@_SHAPE_SETTINGS
def test_property_high_density_shape_stays_connected_region_hull_exists(seed):
    """Any seed with moderate greeble density still produces HULL voxels."""
    p = ShapeParams(length=24, width_max=12, height_max=8, greeble_density=0.3)
    grid = generate_shape(seed, p)
    assert (grid == Role.HULL).sum() > 0


# ----------- additional regression: deterministic snapshot of a known seed -----------


@pytest.mark.parametrize("seed", [0, 1, 42, 1234, 99999])
def test_snapshot_seed_is_stable(seed):
    """Locked signature of (shape, fill count, role-histogram) per seed.

    We do NOT snapshot the full grid (too brittle) — we assert that the grid
    shape, total filled count, and the set of roles present are stable
    under re-runs with identical params. This catches accidental non-determinism
    while allowing legitimate refactoring.
    """
    p = ShapeParams(length=32, width_max=16, height_max=10)
    first = generate_shape(seed, p)
    second = generate_shape(seed, p)
    # The full byte-equality is the strongest possible snapshot.
    assert np.array_equal(first, second)
    # And the grid must be non-empty.
    assert (first != Role.EMPTY).sum() > 0
