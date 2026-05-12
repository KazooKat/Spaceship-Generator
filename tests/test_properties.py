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

import os

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spaceship_generator.engine_styles import EngineStyle
from spaceship_generator.fleet import FleetParams, generate_fleet
from spaceship_generator.generator import generate
from spaceship_generator.greeble_styles import GreebleType
from spaceship_generator.palette import Palette, Role, load_palette, palettes_dir
from spaceship_generator.presets import SHIP_PRESETS, apply_preset
from spaceship_generator.shape import (
    CockpitStyle,
    ShapeParams,
    StructureStyle,
    generate_shape,
)
from spaceship_generator.structure_styles import HullStyle
from spaceship_generator.weapon_styles import WeaponType
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


# ==========================================================================
# Style-space edge cases (Wave 2).
#
# These ten tests probe the corners of the expanded style-space — full
# HullStyle × EngineStyle and StructureStyle × HullStyle matrices, weapon
# and greeble scaling, fleet cardinality, preset coverage, and a handful
# of pure-library determinism checks (cockpit, large seed, palette hash).
# Anything end-to-end runs inside ``settings(deadline=None, max_examples=20)``
# because full-pipeline generation can blow past the default 3 s deadline
# on CI.
# ==========================================================================

_hull_styles = st.sampled_from(list(HullStyle))
_engine_styles = st.sampled_from(list(EngineStyle))

_HEAVY_SETTINGS = settings(
    deadline=None,
    max_examples=20,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(seed=_seeds, hull=_hull_styles, engine=_engine_styles)
@_HEAVY_SETTINGS
def test_property_hull_x_engine_matrix_produces_valid_grid(
    tmp_path_factory, seed, hull, engine
):
    """(HullStyle × EngineStyle) → non-empty grid with all voxels in bounds."""
    out_dir = tmp_path_factory.mktemp("hxe")
    params = ShapeParams(length=24, width_max=12, height_max=8)
    res = generate(
        seed,
        shape_params=params,
        hull_style=hull,
        engine_style=engine,
        out_dir=out_dir,
    )
    W, H, L = res.role_grid.shape
    assert (W, H, L) == (12, 8, 24)
    assert res.block_count > 0
    filled = np.argwhere(res.role_grid != Role.EMPTY)
    # Every filled voxel sits inside the declared (W, H, L) bounds.
    assert filled.size > 0
    assert filled[:, 0].min() >= 0 and filled[:, 0].max() < W
    assert filled[:, 1].min() >= 0 and filled[:, 1].max() < H
    assert filled[:, 2].min() >= 0 and filled[:, 2].max() < L


@given(
    seed=_seeds,
    weapon_count=st.integers(min_value=0, max_value=8),
)
@_HEAVY_SETTINGS
def test_property_weapon_count_scales_weapon_specific_roles(
    tmp_path_factory, seed, weapon_count
):
    """weapon_count in [0, 8]: weapon-specific roles are monotonic vs the baseline.

    Every weapon builder writes into ``LIGHT`` and ``HULL_DARK`` (turret caps,
    missile/plasma glow dots, dark pedestals), so the combined
    ``LIGHT + HULL_DARK`` count is a reliable weapon-activity signal. We do
    NOT assert on ``HULL`` since weapon builders place HULL cells too — so
    HULL scales with weapon_count as well. block_count likewise grows.
    """
    out_dir = tmp_path_factory.mktemp("wc")
    params = ShapeParams(length=24, width_max=12, height_max=8)
    baseline = generate(
        seed, shape_params=params, weapon_count=0, out_dir=out_dir,
        filename="base.litematic",
    )
    variant = generate(
        seed, shape_params=params, weapon_count=weapon_count, out_dir=out_dir,
        filename="var.litematic",
    )
    base_weapon_cells = int(
        (baseline.role_grid == Role.LIGHT).sum()
        + (baseline.role_grid == Role.HULL_DARK).sum()
    )
    var_weapon_cells = int(
        (variant.role_grid == Role.LIGHT).sum()
        + (variant.role_grid == Role.HULL_DARK).sum()
    )
    # With count=0 the two runs are byte-equal; with count>0 the weapon
    # writer can only *add* LIGHT/HULL_DARK (it writes into Role.EMPTY).
    assert var_weapon_cells >= base_weapon_cells
    assert variant.block_count >= baseline.block_count
    if weapon_count == 0:
        assert np.array_equal(variant.role_grid, baseline.role_grid)


# ----------- weapon-count × seed-grid stability (5 counts × small seed set) -----------
#
# Companion to ``test_property_weapon_count_scales_weapon_specific_roles`` above.
# That sibling samples weapon counts via Hypothesis to assert monotonic scaling
# of weapon-specific roles, but it does not deterministically pin every count
# step in a fixed sweep. This parametrize test deterministically pins five
# weapon-count steps spanning the range ``generate()`` accepts crossed with the
# small fixed seed grid ``[0, 1, 7]`` so a regression in the weapon scatter at
# any single count × seed combo surfaces as a self-named ``[seed-weapon_count]``
# failure node. Note: at ``weapon_count=0`` the ship still generates (no weapons
# but hull/cockpit/engines/wings/greebles still produce a non-empty
# ``.litematic``), so the lower bound of the sweep is also a "no-weapons" sanity
# probe.


@pytest.mark.parametrize("weapon_count", [0, 1, 2, 4, 8])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_property_weapon_count_seed_grid_generates_non_empty_litematic(
    tmp_path, weapon_count, seed
):
    """Every ``weapon_count`` step × small seed grid → ``generate()`` writes a non-empty file.

    Mirrors how ``--weapon-count VAL`` plumbs into ``generate()`` —
    ``generate(weapon_count=VAL)`` accepts non-negative integers (with
    ``weapon_count=0`` meaning "skip the weapon scatter entirely"). At
    ``weapon_count=0`` the scatter no-ops but the ship still generates a
    non-empty hull/cockpit/engines/wings/greebles silhouette, so
    ``block_count > 0`` is the right floor invariant for every count step
    including zero. Failure messages name both the offending count and seed
    via the parametrize IDs, plus an explicit ``pytest.fail`` if the file is
    missing or zero-bytes. Companion to the sibling
    ``test_property_weapon_count_scales_weapon_specific_roles`` which checks
    weapon-role monotonicity but does so via Hypothesis sampling — this test
    pins five count steps deterministically so any single-count regression
    surfaces as a self-named failure node rather than relying on Hypothesis
    sampling.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        weapon_count=weapon_count,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"weapon_count={weapon_count} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"weapon_count={weapon_count} seed={seed}"
        )
    assert res.block_count > 0, (
        f"weapon_count={weapon_count} seed={seed} produced 0 blocks"
    )


@given(seed=_seeds)
@_HEAVY_SETTINGS
def test_property_greeble_density_monotonic_in_block_count(tmp_path_factory, seed):
    """For a fixed seed, block_count is monotonic-non-decreasing in density.

    ``scatter_greebles`` writes into empty cells only, so higher density
    can only *add* voxels. We sample three densities from the legal
    [0, 1] range exposed by ``generate`` and lock in ``bc_high >= bc_low``.
    """
    out_dir = tmp_path_factory.mktemp("gd")
    params = ShapeParams(length=24, width_max=12, height_max=8)
    low = generate(
        seed, shape_params=params, greeble_density=0.0, out_dir=out_dir,
        filename="lo.litematic",
    )
    mid = generate(
        seed, shape_params=params, greeble_density=0.5, out_dir=out_dir,
        filename="md.litematic",
    )
    high = generate(
        seed, shape_params=params, greeble_density=1.0, out_dir=out_dir,
        filename="hi.litematic",
    )
    assert low.block_count <= mid.block_count <= high.block_count


# ----------- greeble-density × seed-grid stability (5 densities × small seed set) -----------
#
# Companion to ``test_property_greeble_density_monotonic_in_block_count`` above.
# The Hypothesis-based shape tests sample greeble density but never deterministically
# pin every density-step in a fixed sweep, and the sibling monotonic test only
# samples three densities (0.0 / 0.5 / 1.0) in service of the monotonicity
# assertion. This parametrize test deterministically pins five density steps
# spanning the full ``[0.0, 1.0]`` ``generate()`` range crossed with the small
# fixed seed grid ``[0, 1, 7]`` so a regression in the scatter at any single
# density × seed combo surfaces as a self-named ``[seed-greeble_density]``
# failure node. Note: at ``greeble_density=0.0`` the ship still generates (no
# greebles, but hull/cockpit/engines/wings still produce a non-empty
# ``.litematic``), so the lower bound of the sweep is also a "bare-hull" sanity
# probe.


@pytest.mark.parametrize("greeble_density", [0.0, 0.25, 0.5, 0.75, 1.0])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_property_greeble_density_seed_grid_generates_non_empty_litematic(
    tmp_path, greeble_density, seed
):
    """Every ``greeble_density`` step × small seed grid → ``generate()`` writes a non-empty file.

    Mirrors how ``--greeble-density VAL`` plumbs into ``generate()`` —
    ``generate(greeble_density=VAL)`` accepts the full ``[0.0, 1.0]`` range
    (the ``ShapeParams.greeble_density`` cap of ``0.5`` doesn't apply here
    because we pass density directly to ``generate()`` rather than through
    ``ShapeParams``). At ``greeble_density=0.0`` the scatter no-ops but the
    ship still generates a non-empty hull/cockpit/engines/wings silhouette,
    so ``block_count > 0`` is the right floor invariant for every density
    step including zero. Failure messages name both the offending density
    and seed via the parametrize IDs, plus an explicit ``pytest.fail`` if
    the file is missing or zero-bytes. Companion to the sibling
    ``test_property_greeble_density_monotonic_in_block_count`` which checks
    monotonicity but only over three densities — this test pins five density
    steps deterministically so any single-density regression surfaces as a
    self-named failure node rather than relying on Hypothesis sampling.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        greeble_density=greeble_density,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"greeble_density={greeble_density} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"greeble_density={greeble_density} seed={seed}"
        )
    assert res.block_count > 0, (
        f"greeble_density={greeble_density} seed={seed} produced 0 blocks"
    )


@given(
    count=st.integers(min_value=1, max_value=20),
    coherence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    seed=_seeds,
)
@_HEAVY_SETTINGS
def test_property_fleet_produces_count_ships_with_distinct_seeds(
    count, coherence, seed
):
    """FleetParams(count=1..20, coherence in [0, 1]) → exactly count ships.

    Per-ship seeds are deterministically drawn from the fleet RNG; the
    seed space (0..2^31-1) is vast enough that a count-20 fleet hitting
    a collision is statistically impossible. We assert both cardinality
    and seed uniqueness.
    """
    fp = FleetParams(
        count=count,
        palette="sci_fi_industrial",
        style_coherence=coherence,
        seed=seed,
    )
    ships = generate_fleet(fp)
    assert len(ships) == count
    assert len({s.seed for s in ships}) == count


@pytest.mark.parametrize("preset_name", sorted(SHIP_PRESETS))
def test_property_preset_generates_non_empty_ship(tmp_path, preset_name):
    """Every preset in SHIP_PRESETS: apply → generate → block_count > 0.

    Parametrized (rather than hypothesized) so each preset gets its own
    pytest node for targeted failure reports. apply_preset returns a
    fresh dict per call so the parametrize collector is safe.
    """
    kwargs = apply_preset(preset_name)
    res = generate(1337, out_dir=tmp_path, **kwargs)
    assert res.block_count > 0
    assert res.litematic_path.exists()
    # Shape must match the preset's declared (width, height, length).
    width, height, length = SHIP_PRESETS[preset_name]["size"]
    assert res.shape == (width, height, length)


def test_property_shape_minimums_produce_valid_ship():
    """Minimum legal dims (W=4, H=4, L=8) still produce a symmetric, filled ship.

    Exercised over a small fixed seed set rather than via Hypothesis so the
    assertion locks a boundary rather than a probabilistic property.
    """
    p = ShapeParams(length=8, width_max=4, height_max=4)
    for seed in (0, 1, 2, 42, 9001):
        grid = generate_shape(seed, p)
        assert grid.shape == (4, 4, 8)
        assert np.array_equal(grid, grid[::-1, :, :])
        assert (grid != Role.EMPTY).sum() > 0


@given(seed=_seeds, cockpit=_cockpit_styles)
@_SHAPE_SETTINGS
def test_property_cockpit_style_deterministic_per_seed(seed, cockpit):
    """Same (seed, cockpit_style) → byte-identical grid across repeat calls."""
    p = ShapeParams(
        length=20, width_max=10, height_max=6, cockpit_style=cockpit,
    )
    a = generate_shape(seed, p)
    b = generate_shape(seed, p)
    assert np.array_equal(a, b)


@given(seed=st.integers(min_value=2**30, max_value=2**31 - 1))
@_SHAPE_SETTINGS
def test_property_large_seed_still_deterministic(seed):
    """Seeds close to int32 max produce deterministic, valid grids."""
    p = ShapeParams(length=24, width_max=12, height_max=8)
    a = generate_shape(seed, p)
    b = generate_shape(seed, p)
    assert np.array_equal(a, b)
    # And the grid still obeys bilateral symmetry and has filled cells.
    assert np.array_equal(a, a[::-1, :, :])
    assert (a != Role.EMPTY).sum() > 0


@given(
    seed=_seeds,
    structure=st.sampled_from(list(StructureStyle)),
    hull=_hull_styles,
)
@_HEAVY_SETTINGS
def test_property_structure_x_hull_cross_product_no_crash(seed, structure, hull):
    """Every (StructureStyle, HullStyle) pair generates a valid grid without crashing.

    This is the cross-product smoke test the individual style tests don't
    cover: structure_style drives taper + engine overrides while hull_style
    rewrites the base hull. The two dials *must* compose.
    """
    p = ShapeParams(
        length=24, width_max=12, height_max=8, structure_style=structure,
    )
    grid = generate_shape(seed, p, hull_style=hull)
    assert grid.shape == (12, 8, 24)
    # All cells must still be legal Role values.
    valid = {int(r) for r in Role}
    assert {int(v) for v in np.unique(grid).tolist()}.issubset(valid)


# ----------- palette × seed-grid stability (every palette, small seed set) -----------
#
# Discover palettes dynamically (matches ``tests/test_palette_lint.py`` style)
# so adding a new YAML to ``palettes/`` automatically widens the matrix.
# The seed grid is fixed (deterministic + fast) and matches the
# structure/cockpit/wing-style sibling tests' ``_SHAPE_STYLE_STABILITY_SEEDS``;
# three seeds × ~57 palettes is ~171 generate() calls, which runs in well under
# 60 s on the dev box (~20 ms per call at length=16/width=8/height=6). pytest's
# parametrize IDs make any failure self-naming as ``[seed-palette]``.

_PALETTE_NAMES = sorted(p.stem for p in palettes_dir().glob("*.yaml"))
_PALETTE_STABILITY_SEEDS = [0, 1, 7]


@pytest.mark.parametrize("palette_name", _PALETTE_NAMES, ids=lambda p: p)
@pytest.mark.parametrize("seed", _PALETTE_STABILITY_SEEDS)
def test_property_palette_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, seed
):
    """Every shipped palette × small seed grid → ``generate()`` writes a non-empty file.

    Catches palette-driven regressions (missing role, malformed block id,
    pipeline crash on a specific palette × seed combo) one tick earlier
    than a pure shape-property test would. Failure messages name both the
    offending palette and seed via the parametrize IDs, plus an explicit
    ``pytest.fail`` message if the file is missing or zero-bytes. Mirrors
    the structure/cockpit/wing-style sibling parametrize tests' seed grid
    (``_SHAPE_STYLE_STABILITY_SEEDS = [0, 1, 7]``) so the palette-axis and
    style-axis stability tests stay apples-to-apples on seed coverage.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for palette={palette_name} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for palette={palette_name} seed={seed}"
        )
    # Sanity: block_count should also be > 0 — a non-empty file with no
    # blocks would imply a corrupted palette → litematic mapping.
    assert res.block_count > 0, (
        f"palette={palette_name} seed={seed} produced 0 blocks"
    )


# ----------- preset × seed-grid stability (every named preset, small seed set) -----------
#
# Companion to ``test_property_palette_seed_grid_generates_non_empty_litematic``
# along the *preset* axis instead of the *palette* axis. The Hypothesis-based
# generator tests sample ``ShapeParams`` directly and never thread through
# ``apply_preset``, and the older ``test_property_preset_generates_non_empty_ship``
# pins each preset at a *single* seed (1337). This parametrize test pins every
# named preset (enumerated dynamically via the presets module API so adding a new
# preset to ``SHIP_PRESETS`` automatically widens the matrix) crossed with the
# small fixed seed grid ``[0, 1, 7]`` — same ``_SHAPE_STYLE_STABILITY_SEEDS``
# the structure/cockpit/wing-style sibling tests use — so a regression in any
# single preset's bundled (hull, engine, wing, cockpit, greeble, weapon) tuple
# at a non-1337 seed surfaces as a self-named ``[seed-preset_name]`` failure node.


@pytest.mark.parametrize("preset_name", sorted(SHIP_PRESETS), ids=lambda p: p)
@pytest.mark.parametrize("seed", _PALETTE_STABILITY_SEEDS)
def test_property_preset_seed_grid_generates_non_empty_litematic(
    tmp_path, preset_name, seed
):
    """Every named preset × small seed grid → ``generate()`` writes a non-empty file.

    Mirrors how the presets module API plumbs into ``generate()`` — callers
    unpack ``apply_preset(name)`` as kwargs (``generate(seed=..., **apply_preset(name))``)
    so we do the same here per preset to catch preset-bundle-driven regressions
    (a hull/engine/wing/cockpit/greeble/weapon combo that crashes at a specific
    seed, a missing role for the preset's chosen palette, etc.) one tick earlier
    than ``test_property_preset_generates_non_empty_ship`` would, since that
    sibling pins each preset at a single seed (1337) while this one explicitly
    visits a 3-seed grid per preset. Failure messages name both the offending
    preset and seed via the parametrize IDs, plus an explicit ``pytest.fail``
    message if the file is missing or zero-bytes. Lets the preset's own
    declared ``size`` (W, H, L) drive ``ShapeParams`` rather than overriding
    with the sibling tests' ``length=16/width=8/height=6`` so the preset's
    intended footprint is exercised.
    """
    kwargs = apply_preset(preset_name)
    res = generate(seed, out_dir=tmp_path, filename="ship.litematic", **kwargs)
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for preset={preset_name} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for preset={preset_name} seed={seed}"
        )
    assert res.block_count > 0, (
        f"preset={preset_name} seed={seed} produced 0 blocks"
    )


# ----------- shape-style × seed-grid stability (every enum member, small seed set) -----------
#
# Companion to ``test_property_palette_seed_grid_generates_non_empty_litematic``.
# The Hypothesis-based ``test_property_hull_x_engine_matrix_produces_valid_grid``
# above samples 20 random pairs and may legitimately skip enum members on any
# given run; these parametrize tests deterministically pin *every* HullStyle
# (and EngineStyle) member against a small fixed seed grid so a regression in
# any single style is guaranteed to surface as a self-named ``[style-seed]``
# failure node.

_SHAPE_STYLE_STABILITY_SEEDS = [0, 1, 7]


@pytest.mark.parametrize("hull_style", list(HullStyle), ids=lambda s: s.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_hull_style_seed_grid_generates_non_empty_litematic(
    tmp_path, hull_style, seed
):
    """Every ``HullStyle`` × small seed grid → ``generate()`` writes a non-empty file.

    Catches hull-style-driven regressions (silhouette helper crash, empty
    grid, missing ``.litematic`` write) one tick earlier than the
    Hypothesis-sampled ``hull_x_engine_matrix`` test would, since this
    explicitly visits every member rather than sampling. Failure messages
    name both the offending hull style and seed via the parametrize IDs,
    plus an explicit ``pytest.fail`` message if the file is missing or
    zero-bytes.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        hull_style=hull_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for hull_style={hull_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for hull_style={hull_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"hull_style={hull_style.value} seed={seed} produced 0 blocks"
    )


@pytest.mark.parametrize("engine_style", list(EngineStyle), ids=lambda s: s.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_engine_style_seed_grid_generates_non_empty_litematic(
    tmp_path, engine_style, seed
):
    """Every ``EngineStyle`` × small seed grid → ``generate()`` writes a non-empty file.

    Companion to the HullStyle parametrize above — ``EngineStyle`` is the
    other shape-style enum exposed directly on ``generate()``'s public
    signature (``engine_style=``), so it gets the same deterministic
    every-member coverage. ``WingStyle`` flows only via ``ShapeParams`` and
    is exercised by the Hypothesis ``all_style_combos_symmetric`` test
    plus the ``StructureStyle × HullStyle`` cross-product test, so it's
    not duplicated here.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        engine_style=engine_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for engine_style={engine_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for engine_style={engine_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"engine_style={engine_style.value} seed={seed} produced 0 blocks"
    )


@pytest.mark.parametrize("wing_style", list(WingStyle), ids=lambda s: s.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_wing_style_seed_grid_generates_non_empty_litematic(
    tmp_path, wing_style, seed
):
    """Every ``WingStyle`` × small seed grid → ``generate()`` writes a non-empty file.

    Companion to the HullStyle/EngineStyle parametrize tests above — ``WingStyle``
    is plumbed via ``ShapeParams.wing_style`` rather than a top-level ``generate()``
    kwarg, so it's threaded in by constructing a fresh ``ShapeParams`` per param
    pair instead of passed as a ``generate()`` argument. The Hypothesis-based
    ``test_property_all_style_combos_symmetric`` samples random style trios and
    may legitimately skip individual ``WingStyle`` members on any given run; this
    parametrize test deterministically pins *every* member so a regression in any
    single wing placer (``_place_straight`` / ``_place_swept`` / ``_place_delta``
    / ``_place_tapered`` / ``_place_gull`` / ``_place_split``) surfaces as a
    self-named ``[seed-wing_style]`` failure node.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, wing_style=wing_style,
    )
    res = generate(
        seed,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for wing_style={wing_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for wing_style={wing_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"wing_style={wing_style.value} seed={seed} produced 0 blocks"
    )


@pytest.mark.parametrize("cockpit_style", list(CockpitStyle), ids=lambda c: c.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_cockpit_style_seed_grid_generates_non_empty_litematic(
    tmp_path, cockpit_style, seed
):
    """Every ``CockpitStyle`` × small seed grid → ``generate()`` writes a non-empty file.

    Companion to the HullStyle/EngineStyle/WingStyle parametrize tests above —
    ``CockpitStyle`` is plumbed via ``ShapeParams.cockpit_style`` rather than a
    top-level ``generate()`` kwarg, so it's threaded in by constructing a fresh
    ``ShapeParams`` per param pair instead of passed as a ``generate()`` argument.
    The Hypothesis-based ``test_property_cockpit_style_deterministic_per_seed``
    asserts byte-equality across repeat calls but only over Hypothesis-sampled
    seeds and may legitimately skip individual ``CockpitStyle`` members on any
    given run; this parametrize test deterministically pins *every* member so a
    regression in any single cockpit placer (``bubble`` / ``pointed`` /
    ``integrated`` / ``canopy_dome`` / ``wrap_bridge`` / ``offset_turret``)
    surfaces as a self-named ``[seed-cockpit_style]`` failure node.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, cockpit_style=cockpit_style,
    )
    res = generate(
        seed,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for cockpit_style={cockpit_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for cockpit_style={cockpit_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"cockpit_style={cockpit_style.value} seed={seed} produced 0 blocks"
    )


@pytest.mark.parametrize(
    "structure_style", list(StructureStyle), ids=lambda s: s.value
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_structure_style_seed_grid_generates_non_empty_litematic(
    tmp_path, structure_style, seed
):
    """Every ``StructureStyle`` × small seed grid → ``generate()`` writes a non-empty file.

    Companion to the HullStyle/EngineStyle/WingStyle/CockpitStyle parametrize tests
    above — ``StructureStyle`` is plumbed via ``ShapeParams.structure_style`` rather
    than a top-level ``generate()`` kwarg, so it's threaded in by constructing a
    fresh ``ShapeParams`` per param pair instead of passed as a ``generate()``
    argument. The Hypothesis-based ``test_property_structure_x_hull_cross_product_no_crash``
    samples 20 random ``(StructureStyle, HullStyle)`` pairs and may legitimately
    skip individual ``StructureStyle`` members on any given run; this parametrize
    test deterministically pins *every* member so a regression in any single
    structure profile (``FRIGATE`` / ``FIGHTER`` / ``DREADNOUGHT`` / ``SHUTTLE`` /
    ``HAMMERHEAD`` / ``CARRIER``) surfaces as a self-named ``[seed-structure_style]``
    failure node.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, structure_style=structure_style,
    )
    res = generate(
        seed,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for structure_style={structure_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for structure_style={structure_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"structure_style={structure_style.value} seed={seed} produced 0 blocks"
    )


# ----------- greeble-type × seed-grid stability (every enum member, small seed set) -----------
#
# Companion to ``test_property_hull_style_seed_grid_generates_non_empty_litematic``
# and the engine-style sibling above. The Hypothesis-based shape tests sample
# greeble density but never restrict to a single ``GreebleType``, and the CLI
# ``--greeble-style TYPE`` plumbing (``cli.py:687`` → ``[GreebleType(args.greeble_style)]``
# → ``generate(..., greeble_types=[that_type])``) is exercised end-to-end nowhere
# else. This parametrize test deterministically pins *every* GreebleType member
# against the small fixed seed grid so a regression in any single greeble
# builder is guaranteed to surface as a self-named ``[seed-greeble_type]``
# failure node.


@pytest.mark.parametrize("greeble_type", list(GreebleType), ids=lambda t: t.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_greeble_type_seed_grid_generates_non_empty_litematic(
    tmp_path, greeble_type, seed
):
    """Every ``GreebleType`` × small seed grid → ``generate()`` writes a non-empty file.

    Mirrors how the ``--greeble-style TYPE`` CLI flag plumbs into ``generate()``
    — the CLI passes ``greeble_types=[GreebleType(args.greeble_style)]``, so we
    do the same here per enum member to catch greeble-builder-driven regressions
    (turret/dish/vent/antenna/panel_line/sensor_pod/circuit_board/battle_damage/
    pipe_cluster/organic_growth/nano_mesh) one tick earlier than the
    Hypothesis-sampled shape tests would, since this explicitly visits every
    member rather than sampling. A non-zero ``greeble_density`` is required so
    the scatter actually fires and the restricted-type list has a chance to
    matter. Failure messages name both the offending greeble type and seed via
    the parametrize IDs, plus an explicit ``pytest.fail`` message if the file
    is missing or zero-bytes.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, greeble_density=0.3,
    )
    res = generate(
        seed,
        shape_params=params,
        greeble_types=[greeble_type],
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for greeble_type={greeble_type.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for greeble_type={greeble_type.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"greeble_type={greeble_type.value} seed={seed} produced 0 blocks"
    )


# ----------- weapon-type × seed-grid stability (every enum member, small seed set) -----------
#
# Companion to ``test_property_greeble_type_seed_grid_generates_non_empty_litematic``
# and the hull/engine-style siblings. The Hypothesis-based
# ``test_property_weapon_count_scales_weapon_specific_roles`` samples weapon
# count but never restricts to a single ``WeaponType``, and the CLI
# ``--weapon-type TYPE`` plumbing (``[WeaponType(args.weapon_type)]`` →
# ``generate(..., weapon_types=[that_type])``) is exercised end-to-end nowhere
# else. This parametrize test deterministically pins *every* WeaponType member
# against the small fixed seed grid so a regression in any single weapon
# builder is guaranteed to surface as a self-named ``[seed-weapon_type]``
# failure node.


@pytest.mark.parametrize("weapon_type", list(WeaponType), ids=lambda t: t.value)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_weapon_type_seed_grid_generates_non_empty_litematic(
    tmp_path, weapon_type, seed
):
    """Every ``WeaponType`` × small seed grid → ``generate()`` writes a non-empty file.

    Mirrors how the ``--weapon-type TYPE`` CLI flag plumbs into ``generate()``
    — the CLI passes ``weapon_types=[WeaponType(args.weapon_type)]``, so we do
    the same here per enum member to catch weapon-builder-driven regressions
    (turret_large/missile_pod/laser_lance/point_defense/plasma_core) one tick
    earlier than the Hypothesis-sampled ``weapon_count_scales_weapon_specific_roles``
    test would, since this explicitly visits every member rather than sampling.
    A non-zero ``weapon_count`` is required so the scatter actually fires and
    the restricted-type list has a chance to matter. Failure messages name both
    the offending weapon type and seed via the parametrize IDs, plus an explicit
    ``pytest.fail`` message if the file is missing or zero-bytes.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        weapon_types=[weapon_type],
        weapon_count=4,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for weapon_type={weapon_type.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for weapon_type={weapon_type.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"weapon_type={weapon_type.value} seed={seed} produced 0 blocks"
    )


# ----------- (no_greebles, no_weapons) combos × seed-grid stability -----------
#
# Companion to the per-enum-member parametrize tests above. The CLI exposes
# ``--no-greebles`` and ``--no-weapons`` shortcut flags that translate to
# ``greeble_density=0.0`` and ``weapon_count=0`` respectively (see
# ``src/spaceship_generator/cli.py`` around the ``args.no_greebles`` /
# ``args.no_weapons`` branches). The Hypothesis-based generator tests sample
# greeble density and weapon count independently but never pin the full
# 2×2 boolean cross-product, so a regression that only surfaces with *both*
# flags on (the "bare hull" path: zero greebles + zero weapons → ship must
# still be a non-empty hull, never zero blocks) would not be caught. This
# parametrize test deterministically pins all four (no_greebles, no_weapons)
# combos crossed with the small fixed seed grid ``[0, 1, 7]`` so any
# regression in the no-greebles or no-weapons code paths surfaces as a
# self-named ``[seed-no_weapons-no_greebles]`` failure node.


@pytest.mark.parametrize("no_greebles", [False, True])
@pytest.mark.parametrize("no_weapons", [False, True])
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_no_greebles_no_weapons_combos_seed_grid_generates_non_empty_litematic(
    tmp_path, no_greebles, no_weapons, seed
):
    """Every (no_greebles, no_weapons) combo × small seed grid → non-empty ``.litematic``.

    Mirrors how the ``--no-greebles`` and ``--no-weapons`` CLI shortcut flags
    plumb into ``generate()``: the CLI sets ``greeble_density=0.0`` when
    ``--no-greebles`` is passed and ``weapon_count=0`` when ``--no-weapons``
    is passed, so this test does the same per combo. Even with both flags
    on (the "bare hull" path), the ship must still be a non-empty hull —
    ``block_count > 0`` — because shape generation always yields a
    bilaterally symmetric hull silhouette regardless of greeble/weapon
    decoration. Failure messages name the offending combo and seed via the
    parametrize IDs, plus an explicit ``pytest.fail`` message if the file
    is missing or zero-bytes.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    kwargs = {}
    if no_greebles:
        kwargs["greeble_density"] = 0.0
    if no_weapons:
        kwargs["weapon_count"] = 0
    res = generate(
        seed,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
        **kwargs,
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"no_greebles={no_greebles} no_weapons={no_weapons} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"no_greebles={no_greebles} no_weapons={no_weapons} seed={seed}"
        )
    assert res.block_count > 0, (
        f"no_greebles={no_greebles} no_weapons={no_weapons} seed={seed} "
        f"produced 0 blocks"
    )


# --------- cockpit_style × hull_style × seed-grid stability (cross-axis) ---------
#
# Companion to the single-axis sibling parametrize tests
# ``test_property_cockpit_style_seed_grid_generates_non_empty_litematic`` and
# ``test_property_hull_style_seed_grid_generates_non_empty_litematic``: those
# two pin every member of *one* enum at fixed seeds, but neither exercises the
# CROSS-axis interaction between cockpit placement (``ShapeParams.cockpit_style``
# → cockpit placer dispatch in ``shape/cockpit.py``) and hull silhouette
# (``hull_style=`` → hull profile in ``structure_styles.py``). A regression that
# only surfaces when, e.g., ``CockpitStyle.OFFSET_TURRET`` is combined with
# ``HullStyle.DAGGER`` (the narrowest hull) — say, the turret anchor falling
# outside the dagger's thin X-band — would slip past both single-axis tests.
# The full 6×5 cross-product would be 30 cockpit/hull pairs × 3 seeds = 90
# nodes, which inflates the suite without much marginal coverage; instead we
# slice each enum dynamically (first / middle / last members in declaration
# order, driven from ``list(CockpitStyle)`` / ``list(HullStyle)`` so the slice
# follows future enum reorderings or extensions) for 3 cockpit × 3 hull × 3
# seeds = 27 representative nodes that still hit the extremes of both axes.
# Failure node IDs read ``[seed-hull_style-cockpit_style]`` so a regression in
# any single (cockpit, hull) interaction is self-naming.


def _slice_first_middle_last(members):
    """Pick first / middle / last members of a sequence in declaration order.

    Driven dynamically off ``list(EnumCls)`` so the slice tracks future
    additions/reorderings of the enum without manual edits. For sequences
    shorter than 3 members the result is deduplicated while preserving order
    so the parametrize grid never accidentally repeats a node ID.
    """
    if len(members) <= 3:
        # Small enums: just dedupe-preserve all members so we still cover the
        # extremes (and the middle, if there is one).
        seen = []
        for m in members:
            if m not in seen:
                seen.append(m)
        return seen
    return [members[0], members[len(members) // 2], members[-1]]


_COCKPIT_HULL_GRID_COCKPITS = _slice_first_middle_last(list(CockpitStyle))
_COCKPIT_HULL_GRID_HULLS = _slice_first_middle_last(list(HullStyle))


@pytest.mark.parametrize(
    "cockpit_style", _COCKPIT_HULL_GRID_COCKPITS, ids=lambda c: c.value,
)
@pytest.mark.parametrize(
    "hull_style", _COCKPIT_HULL_GRID_HULLS, ids=lambda h: h.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_cockpit_x_hull_style_seed_grid_generates_non_empty_litematic(
    tmp_path, cockpit_style, hull_style, seed
):
    """``CockpitStyle`` × ``HullStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``cockpit_style_seed_grid`` and
    ``hull_style_seed_grid`` parametrize tests above. ``CockpitStyle`` is
    plumbed via ``ShapeParams.cockpit_style`` (cockpit placer dispatch in
    ``shape/cockpit.py``) while ``HullStyle`` is passed directly to
    ``generate(hull_style=...)`` (hull silhouette profile in
    ``structure_styles.py``); a regression that only surfaces in the
    interaction between a specific cockpit placement and a specific hull
    profile (e.g., a turret anchor landing outside a narrow dagger hull's
    X-band) would slip past both single-axis tests. We slice each enum to
    first / middle / last in declaration order — driven dynamically off
    ``list(EnumCls)`` so the slice tracks future enum additions — for 3 × 3
    × 3 = 27 representative nodes that still hit the extremes of both axes
    without inflating the suite to the full 6×5×3 = 90-node cross-product.
    Failure messages name the offending ``(cockpit_style, hull_style, seed)``
    tuple via the parametrize IDs plus an explicit ``pytest.fail`` message
    so a regression localizes immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, cockpit_style=cockpit_style,
    )
    res = generate(
        seed,
        shape_params=params,
        hull_style=hull_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"hull_style={hull_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"hull_style={hull_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"cockpit_style={cockpit_style.value} "
        f"hull_style={hull_style.value} seed={seed} produced 0 blocks"
    )


# --------- cockpit_style × wing_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the cockpit_style × hull_style cross-product test above:
# pins (CockpitStyle × WingStyle × seed) deterministically to catch regressions
# that only surface in the interaction between cockpit placement
# (``ShapeParams.cockpit_style`` → cockpit placer dispatch in ``shape/cockpit.py``)
# and wing placement (``ShapeParams.wing_style`` → wing placer dispatch in
# ``shape/wings.py``). A regression that only surfaces when, e.g., a tall
# canopy/dome cockpit is combined with a gull-wing layout (the wings'
# anchor-row interfering with the cockpit silhouette) would slip past both
# single-axis tests. We slice each enum to first / middle / last members in
# declaration order via the existing ``_slice_first_middle_last`` helper for
# 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-wing_style-cockpit_style]`` so a regression in any single
# (cockpit, wing) interaction is self-naming.


_COCKPIT_WING_GRID_COCKPITS = _slice_first_middle_last(list(CockpitStyle))
_COCKPIT_WING_GRID_WINGS = _slice_first_middle_last(list(WingStyle))


@pytest.mark.parametrize(
    "cockpit_style", _COCKPIT_WING_GRID_COCKPITS, ids=lambda c: c.value,
)
@pytest.mark.parametrize(
    "wing_style", _COCKPIT_WING_GRID_WINGS, ids=lambda w: w.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_cockpit_x_wing_style_seed_grid_generates_non_empty_litematic(
    tmp_path, cockpit_style, wing_style, seed
):
    """``CockpitStyle`` × ``WingStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``cockpit_style_seed_grid`` and
    ``wing_style_seed_grid`` parametrize tests above. Both ``CockpitStyle``
    and ``WingStyle`` are plumbed via ``ShapeParams`` (cockpit placer dispatch
    in ``shape/cockpit.py``; wing placer dispatch in ``shape/wings.py``); a
    regression that only surfaces in the interaction between a specific
    cockpit placement and a specific wing layout (e.g., a gull-wing anchor
    row interfering with a tall canopy/dome cockpit silhouette) would slip
    past both single-axis tests. We slice each enum to first / middle / last
    in declaration order via the existing ``_slice_first_middle_last`` helper
    for 3 × 3 × 3 = 27 representative nodes that still hit the extremes of
    both axes without inflating the suite to the full cross-product. Failure
    messages name the offending ``(cockpit_style, wing_style, seed)`` tuple
    via the parametrize IDs plus an explicit ``pytest.fail`` message so a
    regression localizes immediately.
    """
    params = ShapeParams(
        length=16,
        width_max=8,
        height_max=6,
        cockpit_style=cockpit_style,
        wing_style=wing_style,
    )
    res = generate(
        seed,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"cockpit_style={cockpit_style.value} "
        f"wing_style={wing_style.value} seed={seed} produced 0 blocks"
    )


# --------- hull_style × engine_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the cockpit×hull and cockpit×wing cross-product tests
# above: pins (HullStyle × EngineStyle × seed) deterministically to catch
# regressions that only surface in the interaction between hull silhouette
# (``hull_style=`` → hull profile in ``structure_styles.py``) and engine
# placement (``engine_style=`` → engine builder dispatch in
# ``engine_styles.py``). A regression that only surfaces when, e.g., a narrow
# dagger hull is combined with a wide quad-cluster engine layout (the engine
# anchor falling outside the dagger's thin Z-band stern) would slip past both
# single-axis tests. The Hypothesis-based ``hull_x_engine_matrix`` test above
# samples 20 random pairs and may legitimately skip representative pairs on
# any given run; this parametrize test deterministically pins first/middle/
# last × first/middle/last × seed for 3 × 3 × 3 = 27 nodes. Failure node IDs
# read ``[seed-engine_style-hull_style]`` so a regression in any single
# (hull, engine) interaction is self-naming.


_HULL_ENGINE_GRID_HULLS = _slice_first_middle_last(list(HullStyle))
_HULL_ENGINE_GRID_ENGINES = _slice_first_middle_last(list(EngineStyle))


@pytest.mark.parametrize(
    "hull_style", _HULL_ENGINE_GRID_HULLS, ids=lambda h: h.value,
)
@pytest.mark.parametrize(
    "engine_style", _HULL_ENGINE_GRID_ENGINES, ids=lambda e: e.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_hull_x_engine_style_seed_grid_generates_non_empty_litematic(
    tmp_path, hull_style, engine_style, seed
):
    """``HullStyle`` × ``EngineStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``hull_style_seed_grid`` and
    ``engine_style_seed_grid`` parametrize tests above, and a deterministic
    counterpart to the Hypothesis-sampled ``hull_x_engine_matrix`` test.
    Both ``HullStyle`` and ``EngineStyle`` are passed directly to
    ``generate()`` via top-level kwargs (``hull_style=`` for the hull
    silhouette profile in ``structure_styles.py``; ``engine_style=`` for the
    engine builder dispatch in ``engine_styles.py``); a regression that only
    surfaces in the interaction between a specific hull silhouette and a
    specific engine layout (e.g., a narrow dagger hull combined with a wide
    quad-cluster engine layout where the engine anchor falls outside the
    dagger's thin Z-band stern) would slip past both single-axis tests and
    may also be missed by the 20-sample Hypothesis matrix. We slice each
    enum to first / middle / last in declaration order via the existing
    ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative
    nodes that still hit the extremes of both axes. Failure messages name
    the offending ``(hull_style, engine_style, seed)`` tuple via the
    parametrize IDs plus an explicit ``pytest.fail`` message so a regression
    localizes immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        hull_style=hull_style,
        engine_style=engine_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"hull_style={hull_style.value} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"hull_style={hull_style.value} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"hull_style={hull_style.value} "
        f"engine_style={engine_style.value} seed={seed} produced 0 blocks"
    )


# --------- greeble_density × weapon_count × seed-grid stability (cross-axis) ---------
#
# Numeric-axis cross-product sibling of the enum cross-axis tests above
# (cockpit×hull / cockpit×wing / hull×engine). The single-axis siblings
# ``test_property_greeble_density_seed_grid_generates_non_empty_litematic``
# and ``test_property_weapon_count_seed_grid_generates_non_empty_litematic``
# pin each axis deterministically on its own, but a regression that only
# surfaces in the interaction between a specific greeble density and a
# specific weapon count (e.g., a maxed-out greeble scatter at
# ``greeble_density=1.0`` claiming every surface anchor so the weapon
# scatter at ``weapon_count=8`` cannot find empty cells to write into and
# silently no-ops, or a zero-greeble bare-hull at ``greeble_density=0.0``
# combined with ``weapon_count=0`` collapsing to a degenerate silhouette
# that fails to write blocks) would slip past both single-axis tests.
# We pin three densities (``0.0`` no-greebles bare-hull / ``0.5`` mid /
# ``1.0`` max scatter — same extremes as the
# ``test_property_greeble_density_monotonic_in_block_count`` companion) ×
# three weapon counts (``0`` no-weapons / ``2`` mid / ``8`` max — same
# upper/lower bounds as the weapon-count single-axis sweep) × the small
# fixed seed grid ``[0, 1, 7]`` (``_SHAPE_STYLE_STABILITY_SEEDS``) for
# 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-weapon_count-greeble_density]`` so a regression in any single
# (density, weapon_count) interaction is self-naming.


@pytest.mark.parametrize("greeble_density", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("weapon_count", [0, 2, 8])
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_greeble_density_x_weapon_count_seed_grid_generates_non_empty_litematic(
    tmp_path, greeble_density, weapon_count, seed
):
    """``greeble_density`` × ``weapon_count`` × small seed grid → non-empty ``.litematic``.

    Numeric-axis cross-product companion to the single-axis
    ``greeble_density_seed_grid`` and ``weapon_count_seed_grid`` parametrize
    tests above, and the numeric-axis sibling of the enum cross-axis tests
    (cockpit×hull / cockpit×wing / hull×engine). Both axes are passed
    directly to ``generate()`` via top-level kwargs (``greeble_density=`` for
    the multi-cell scatter pass in ``greeble_styles.scatter_greebles``,
    ``weapon_count=`` for the weapon scatter dispatch in
    ``weapon_styles.scatter_weapons``); a regression that only surfaces in
    the interaction between a specific density and a specific count (e.g.,
    a maxed-out greeble scatter at ``greeble_density=1.0`` claiming every
    surface anchor so the weapon scatter at ``weapon_count=8`` cannot find
    empty cells to write into) would slip past both single-axis tests. We
    pin three densities (``0.0`` / ``0.5`` / ``1.0``) × three weapon counts
    (``0`` / ``2`` / ``8``) × the small fixed seed grid ``[0, 1, 7]`` for
    3 × 3 × 3 = 27 representative nodes that hit the extremes of both
    numeric axes. At ``greeble_density=0.0`` the greeble scatter no-ops and
    at ``weapon_count=0`` the weapon scatter no-ops, but the ship still
    generates a non-empty hull/cockpit/engines/wings silhouette so
    ``block_count > 0`` is the right floor invariant for every node
    including the (0.0, 0) corner. Failure messages name the offending
    ``(greeble_density, weapon_count, seed)`` tuple via the parametrize
    IDs plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        greeble_density=greeble_density,
        weapon_count=weapon_count,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"greeble_density={greeble_density} "
            f"weapon_count={weapon_count} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"greeble_density={greeble_density} "
            f"weapon_count={weapon_count} seed={seed}"
        )
    assert res.block_count > 0, (
        f"greeble_density={greeble_density} "
        f"weapon_count={weapon_count} seed={seed} produced 0 blocks"
    )


# --------- palette × cockpit_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the enum/numeric cross-product tests above
# (cockpit×hull / cockpit×wing / hull×engine / greeble_density×weapon_count).
# The single-axis ``test_property_palette_seed_grid_generates_non_empty_litematic``
# pins every shipped palette × seed and the single-axis
# ``test_property_cockpit_style_seed_grid_generates_non_empty_litematic`` pins
# every ``CockpitStyle`` × seed, but neither exercises the CROSS-axis
# interaction between palette role coverage (palette YAML in ``palettes/`` →
# block-id mapping in ``palette.py``) and cockpit placement
# (``ShapeParams.cockpit_style`` → cockpit placer dispatch in
# ``shape/cockpit.py``). A regression that only surfaces when, e.g., a palette
# missing or stubbing the ``cockpit`` role is combined with a cockpit placer
# that emits a role variant the palette can't map (silent no-op → zero-block
# .litematic) would slip past both single-axis tests. We slice the palette
# list dynamically (first / middle / last alphabetically of ``_PALETTE_NAMES``,
# which is already ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``)
# and ``CockpitStyle`` to first / middle / last via the existing
# ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative nodes.
# Failure node IDs read ``[seed-cockpit_style-palette_name]`` so a regression
# in any single (palette, cockpit) interaction is self-naming.


_PALETTE_COCKPIT_GRID_PALETTES = _slice_first_middle_last(_PALETTE_NAMES)
_PALETTE_COCKPIT_GRID_COCKPITS = _slice_first_middle_last(list(CockpitStyle))


@pytest.mark.parametrize(
    "palette_name", _PALETTE_COCKPIT_GRID_PALETTES, ids=lambda p: p,
)
@pytest.mark.parametrize(
    "cockpit_style", _PALETTE_COCKPIT_GRID_COCKPITS, ids=lambda c: c.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_palette_x_cockpit_style_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, cockpit_style, seed
):
    """``palette`` × ``CockpitStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``palette_seed_grid`` and
    ``cockpit_style_seed_grid`` parametrize tests above. Palette is plumbed
    via ``generate(palette=...)`` (palette YAML → block-id mapping in
    ``palette.py``) while ``CockpitStyle`` is plumbed via
    ``ShapeParams.cockpit_style`` (cockpit placer dispatch in
    ``shape/cockpit.py``); a regression that only surfaces in the interaction
    between a specific palette and a specific cockpit placement (e.g., a
    palette missing or stubbing the ``cockpit`` role combined with a cockpit
    placer that emits a role variant the palette can't map) would slip past
    both single-axis tests. We slice the palette list dynamically — first /
    middle / last alphabetically of ``_PALETTE_NAMES`` (already
    ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``) — and slice
    ``CockpitStyle`` to first / middle / last in declaration order via the
    existing ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27
    representative nodes that hit the extremes of both axes without
    inflating the suite to the full palette-corpus × cockpit cross-product.
    Failure messages name the offending ``(palette, cockpit_style, seed)``
    tuple via the parametrize IDs plus an explicit ``pytest.fail`` message
    so a regression localizes immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, cockpit_style=cockpit_style,
    )
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"palette={palette_name} "
            f"cockpit_style={cockpit_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"palette={palette_name} "
            f"cockpit_style={cockpit_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"palette={palette_name} "
        f"cockpit_style={cockpit_style.value} seed={seed} produced 0 blocks"
    )


# --------- palette × greeble_density × seed-grid stability (cross-axis) ---------
#
# Numeric-axis sibling of the palette × cockpit_style cross-product test above:
# pins (palette × ``greeble_density`` × seed) deterministically to catch
# regressions that only surface in the interaction between palette role coverage
# (palette YAML in ``palettes/`` → block-id mapping in ``palette.py``) and the
# greeble scatter density (``greeble_density=`` top-level kwarg → multi-cell
# scatter pass in ``greeble_styles.scatter_greebles``). The single-axis
# ``test_property_palette_seed_grid_generates_non_empty_litematic`` pins every
# shipped palette × seed and the single-axis
# ``test_property_greeble_density_seed_grid_generates_non_empty_litematic`` pins
# the density axis on its own, but neither exercises the CROSS-axis interaction
# between palette role coverage and greeble density. A regression that only
# surfaces when, e.g., a palette stubbing the ``greeble`` role combined with
# ``greeble_density=1.0`` (max scatter claiming every surface anchor with a
# block id the palette cannot map → silent no-op) or a maxed-out density
# combined with a palette whose greeble role only covers a narrow subset of
# greeble variants would slip past both single-axis tests. We slice the palette
# list dynamically (first / middle / last alphabetically of ``_PALETTE_NAMES``,
# which is already ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``)
# and pin three densities (``0.0`` no-greebles bare-hull / ``0.5`` mid / ``1.0``
# max scatter — same extremes as the
# ``test_property_greeble_density_x_weapon_count_seed_grid`` sibling and the
# ``test_property_greeble_density_monotonic_in_block_count`` companion) for
# 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-greeble_density-palette_name]`` so a regression in any single
# (palette, density) interaction is self-naming. ``greeble_density`` is plumbed
# via the top-level ``generate(greeble_density=...)`` kwarg (not via
# ``ShapeParams``) since the top-level kwarg accepts the full ``[0.0, 1.0]``
# range and matches the numeric-axis sibling's plumbing.


_PALETTE_GREEBLE_GRID_PALETTES = _slice_first_middle_last(_PALETTE_NAMES)


@pytest.mark.parametrize(
    "palette_name", _PALETTE_GREEBLE_GRID_PALETTES, ids=lambda p: p,
)
@pytest.mark.parametrize("greeble_density", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_palette_x_greeble_density_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, greeble_density, seed
):
    """``palette`` × ``greeble_density`` × small seed grid → non-empty ``.litematic``.

    Numeric-axis cross-product companion to the single-axis
    ``palette_seed_grid`` and ``greeble_density_seed_grid`` parametrize tests
    above, and a sibling of the palette × cockpit_style enum cross-axis test
    immediately above. Palette is plumbed via ``generate(palette=...)`` (palette
    YAML → block-id mapping in ``palette.py``) while ``greeble_density`` is
    passed directly to ``generate()`` via the top-level ``greeble_density=``
    kwarg (multi-cell scatter pass in ``greeble_styles.scatter_greebles``); the
    top-level kwarg accepts the full ``[0.0, 1.0]`` range so we plumb it that
    way rather than through ``ShapeParams``, mirroring the numeric-axis sibling
    ``test_property_greeble_density_x_weapon_count_seed_grid`` exactly. A
    regression that only surfaces in the interaction between a specific palette
    and a specific density (e.g., a palette stubbing the ``greeble`` role
    combined with ``greeble_density=1.0`` claiming every surface anchor with a
    block id the palette cannot map) would slip past both single-axis tests.
    We slice the palette list dynamically — first / middle / last
    alphabetically of ``_PALETTE_NAMES`` (already
    ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``) — and pin three
    densities (``0.0`` / ``0.5`` / ``1.0``) × the small fixed seed grid
    ``[0, 1, 7]`` for 3 × 3 × 3 = 27 representative nodes that hit the
    extremes of both axes without inflating the suite to the full
    palette-corpus × density cross-product. At ``greeble_density=0.0`` the
    greeble scatter no-ops but the ship still generates a non-empty
    hull/cockpit/engines/wings silhouette so ``block_count > 0`` is the right
    floor invariant for every node. Failure messages name the offending
    ``(palette, greeble_density, seed)`` tuple via the parametrize IDs plus an
    explicit ``pytest.fail`` message so a regression localizes immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        greeble_density=greeble_density,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"palette={palette_name} "
            f"greeble_density={greeble_density} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"palette={palette_name} "
            f"greeble_density={greeble_density} seed={seed}"
        )
    assert res.block_count > 0, (
        f"palette={palette_name} "
        f"greeble_density={greeble_density} seed={seed} produced 0 blocks"
    )


# --------- palette × hull_style × seed-grid stability (cross-axis) ---------
#
# Enum-axis sibling of the palette × cockpit_style and palette × greeble_density
# cross-product tests above: pins (palette × ``HullStyle`` × seed) deterministically
# to catch regressions that only surface in the interaction between palette role
# coverage (palette YAML in ``palettes/`` → block-id mapping in ``palette.py``) and
# hull silhouette (``hull_style=`` top-level kwarg → hull profile in
# ``structure_styles.py``). The single-axis
# ``test_property_palette_seed_grid_generates_non_empty_litematic`` pins every
# shipped palette × seed and the single-axis
# ``test_property_hull_style_seed_grid_generates_non_empty_litematic`` pins the
# hull axis on its own, but neither exercises the CROSS-axis interaction between
# palette role coverage and hull silhouette. A regression that only surfaces when,
# e.g., a palette stubbing the ``hull`` / ``hull_dark`` role combined with a
# narrow dagger or saucer hull silhouette (whose tight Z-band leaves only a thin
# strip of hull cells the palette must successfully map to a block id) would slip
# past both single-axis tests. We slice the palette list dynamically (first /
# middle / last alphabetically of ``_PALETTE_NAMES``, which is already
# ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``) and ``HullStyle``
# to first / middle / last via the existing ``_slice_first_middle_last`` helper
# for 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-hull_style-palette_name]`` so a regression in any single (palette,
# hull_style) interaction is self-naming.


_PALETTE_HULL_GRID_PALETTES = _slice_first_middle_last(_PALETTE_NAMES)
_PALETTE_HULL_GRID_HULLS = _slice_first_middle_last(list(HullStyle))


@pytest.mark.parametrize(
    "palette_name", _PALETTE_HULL_GRID_PALETTES, ids=lambda p: p,
)
@pytest.mark.parametrize(
    "hull_style", _PALETTE_HULL_GRID_HULLS, ids=lambda h: h.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_palette_x_hull_style_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, hull_style, seed
):
    """``palette`` × ``HullStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``palette_seed_grid`` and
    ``hull_style_seed_grid`` parametrize tests above, and a sibling of the
    palette × cockpit_style / palette × greeble_density cross-axis tests
    immediately above. Palette is plumbed via ``generate(palette=...)``
    (palette YAML → block-id mapping in ``palette.py``) while ``HullStyle``
    is passed directly to ``generate()`` via the top-level ``hull_style=``
    kwarg (hull silhouette profile in ``structure_styles.py``); a regression
    that only surfaces in the interaction between a specific palette and a
    specific hull silhouette (e.g., a palette stubbing the ``hull`` /
    ``hull_dark`` role combined with a narrow dagger hull whose tight Z-band
    leaves only a thin strip of hull cells the palette must successfully map
    to a block id) would slip past both single-axis tests. We slice the
    palette list dynamically — first / middle / last alphabetically of
    ``_PALETTE_NAMES`` (already ``sorted(p.stem for p in
    palettes_dir().glob("*.yaml"))``) — and slice ``HullStyle`` to first /
    middle / last in declaration order via the existing
    ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative
    nodes that hit the extremes of both axes without inflating the suite to
    the full palette-corpus × hull cross-product. Failure messages name the
    offending ``(palette, hull_style, seed)`` tuple via the parametrize IDs
    plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        hull_style=hull_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"palette={palette_name} "
            f"hull_style={hull_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"palette={palette_name} "
            f"hull_style={hull_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"palette={palette_name} "
        f"hull_style={hull_style.value} seed={seed} produced 0 blocks"
    )


# --------- palette × engine_style × seed-grid stability (cross-axis) ---------
#
# Enum-axis sibling of the palette × cockpit_style / palette × greeble_density /
# palette × hull_style cross-product tests above: pins (palette × ``EngineStyle``
# × seed) deterministically to catch regressions that only surface in the
# interaction between palette role coverage (palette YAML in ``palettes/`` →
# block-id mapping in ``palette.py``) and engine layout (``engine_style=``
# top-level kwarg → engine builder dispatch in ``engine_styles.py``). The
# single-axis ``test_property_palette_seed_grid_generates_non_empty_litematic``
# pins every shipped palette × seed and the single-axis
# ``test_property_engine_style_seed_grid_generates_non_empty_litematic`` pins the
# engine axis on its own, but neither exercises the CROSS-axis interaction between
# palette role coverage and engine layout. A regression that only surfaces when,
# e.g., a palette stubbing the ``engine`` / ``engine_glow`` role combined with a
# wide quad-cluster engine layout (whose anchor row claims many engine-bell cells
# the palette must successfully map to a block id) would slip past both
# single-axis tests. We slice the palette list dynamically (first / middle / last
# alphabetically of ``_PALETTE_NAMES``, which is already
# ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``) and ``EngineStyle``
# to first / middle / last via the existing ``_slice_first_middle_last`` helper
# for 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-engine_style-palette_name]`` so a regression in any single (palette,
# engine_style) interaction is self-naming.


_PALETTE_ENGINE_GRID_PALETTES = _slice_first_middle_last(_PALETTE_NAMES)
_PALETTE_ENGINE_GRID_ENGINES = _slice_first_middle_last(list(EngineStyle))


@pytest.mark.parametrize(
    "palette_name", _PALETTE_ENGINE_GRID_PALETTES, ids=lambda p: p,
)
@pytest.mark.parametrize(
    "engine_style", _PALETTE_ENGINE_GRID_ENGINES, ids=lambda e: e.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_palette_x_engine_style_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, engine_style, seed
):
    """``palette`` × ``EngineStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``palette_seed_grid`` and
    ``engine_style_seed_grid`` parametrize tests above, and a sibling of the
    palette × cockpit_style / palette × greeble_density / palette × hull_style
    cross-axis tests immediately above. Palette is plumbed via
    ``generate(palette=...)`` (palette YAML → block-id mapping in
    ``palette.py``) while ``EngineStyle`` is passed directly to ``generate()``
    via the top-level ``engine_style=`` kwarg (engine builder dispatch in
    ``engine_styles.py``); a regression that only surfaces in the interaction
    between a specific palette and a specific engine layout (e.g., a palette
    stubbing the ``engine`` / ``engine_glow`` role combined with a wide
    quad-cluster engine anchor row claiming many engine-bell cells the palette
    must successfully map to a block id) would slip past both single-axis
    tests. We slice the palette list dynamically — first / middle / last
    alphabetically of ``_PALETTE_NAMES`` (already ``sorted(p.stem for p in
    palettes_dir().glob("*.yaml"))``) — and slice ``EngineStyle`` to first /
    middle / last in declaration order via the existing
    ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative
    nodes that hit the extremes of both axes without inflating the suite to
    the full palette-corpus × engine cross-product. Failure messages name the
    offending ``(palette, engine_style, seed)`` tuple via the parametrize IDs
    plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        engine_style=engine_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"palette={palette_name} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"palette={palette_name} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"palette={palette_name} "
        f"engine_style={engine_style.value} seed={seed} produced 0 blocks"
    )


# --------- palette × wing_style × seed-grid stability (cross-axis) ---------
#
# Enum-axis sibling of the palette × cockpit_style / palette × greeble_density /
# palette × hull_style / palette × engine_style cross-product tests above:
# pins (palette × ``WingStyle`` × seed) deterministically to catch regressions
# that only surface in the interaction between palette role coverage (palette
# YAML in ``palettes/`` → block-id mapping in ``palette.py``) and wing
# placement (``ShapeParams.wing_style`` → wing placer dispatch in
# ``shape/wings.py``). The single-axis
# ``test_property_palette_seed_grid_generates_non_empty_litematic`` pins every
# shipped palette × seed and the single-axis
# ``test_property_wing_style_seed_grid_generates_non_empty_litematic`` pins the
# wing axis on its own, but neither exercises the CROSS-axis interaction
# between palette role coverage and wing layout. A regression that only
# surfaces when, e.g., a palette stubbing the ``wing`` / ``wing_edge`` role
# combined with a swept-back gull wing layout (whose stern anchor column
# claims a wide strip of wing cells the palette must successfully map to a
# block id) would slip past both single-axis tests. We slice the palette list
# dynamically (first / middle / last alphabetically of ``_PALETTE_NAMES``,
# which is already ``sorted(p.stem for p in palettes_dir().glob("*.yaml"))``)
# and ``WingStyle`` to first / middle / last via the existing
# ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative nodes.
# Failure node IDs read ``[seed-wing_style-palette_name]`` so a regression in
# any single (palette, wing_style) interaction is self-naming.


_PALETTE_WING_GRID_PALETTES = _slice_first_middle_last(_PALETTE_NAMES)
_PALETTE_WING_GRID_WINGS = _slice_first_middle_last(list(WingStyle))


@pytest.mark.parametrize(
    "palette_name", _PALETTE_WING_GRID_PALETTES, ids=lambda p: p,
)
@pytest.mark.parametrize(
    "wing_style", _PALETTE_WING_GRID_WINGS, ids=lambda w: w.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_palette_x_wing_style_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, wing_style, seed
):
    """``palette`` × ``WingStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``palette_seed_grid`` and
    ``wing_style_seed_grid`` parametrize tests above, and a sibling of the
    palette × cockpit_style / palette × greeble_density / palette × hull_style
    / palette × engine_style cross-axis tests immediately above. Palette is
    plumbed via ``generate(palette=...)`` (palette YAML → block-id mapping in
    ``palette.py``) while ``WingStyle`` is plumbed via
    ``ShapeParams.wing_style`` (wing placer dispatch in ``shape/wings.py``);
    a regression that only surfaces in the interaction between a specific
    palette and a specific wing layout (e.g., a palette stubbing the ``wing``
    / ``wing_edge`` role combined with a swept-back gull wing whose stern
    anchor column claims a wide strip of wing cells the palette must
    successfully map to a block id) would slip past both single-axis tests.
    We slice the palette list dynamically — first / middle / last
    alphabetically of ``_PALETTE_NAMES`` (already ``sorted(p.stem for p in
    palettes_dir().glob("*.yaml"))``) — and slice ``WingStyle`` to first /
    middle / last in declaration order via the existing
    ``_slice_first_middle_last`` helper for 3 × 3 × 3 = 27 representative
    nodes that hit the extremes of both axes without inflating the suite to
    the full palette-corpus × wing cross-product. Failure messages name the
    offending ``(palette, wing_style, seed)`` tuple via the parametrize IDs
    plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, wing_style=wing_style,
    )
    res = generate(
        seed,
        palette=palette_name,
        shape_params=params,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"palette={palette_name} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"palette={palette_name} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"palette={palette_name} "
        f"wing_style={wing_style.value} seed={seed} produced 0 blocks"
    )


# --------- engine_style × wing_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the cockpit×hull / cockpit×wing / hull×engine /
# palette×cockpit cross-product tests above: pins (EngineStyle × WingStyle ×
# seed) deterministically to catch regressions that only surface in the
# interaction between engine placement (``engine_style=`` → engine builder
# dispatch in ``engine_styles.py``) and wing placement
# (``ShapeParams.wing_style`` → wing placer dispatch in ``shape/wings.py``).
# The single-axis ``engine_style_seed_grid`` and ``wing_style_seed_grid``
# parametrize tests above pin each axis on its own, but a regression that
# only surfaces when, e.g., a wide quad-cluster engine layout is combined
# with a swept-back gull wing (the engine anchor row colliding with the
# wing's stern anchor column at the same Z-band) would slip past both
# single-axis tests. We slice each enum to the first three members in
# declaration order via ``list(EngineStyle)[:3]`` / ``list(WingStyle)[:3]``
# (sourced dynamically off the enums so the slice tracks future
# reorderings) for 3 × 3 × 3 = 27 representative nodes. Failure node IDs
# read ``[seed-wing_style-engine_style]`` so a regression in any single
# (engine, wing) interaction is self-naming.


_ENGINE_WING_GRID_ENGINES = list(EngineStyle)[:3]
_ENGINE_WING_GRID_WINGS = list(WingStyle)[:3]


@pytest.mark.parametrize(
    "engine_style", _ENGINE_WING_GRID_ENGINES, ids=lambda e: e.value,
)
@pytest.mark.parametrize(
    "wing_style", _ENGINE_WING_GRID_WINGS, ids=lambda w: w.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_engine_style_x_wing_style_seed_grid_generates_non_empty_litematic(
    tmp_path, engine_style, wing_style, seed
):
    """``EngineStyle`` × ``WingStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``engine_style_seed_grid`` and
    ``wing_style_seed_grid`` parametrize tests above, and a sibling of the
    other enum cross-product tests (cockpit×hull / cockpit×wing /
    hull×engine / palette×cockpit). ``EngineStyle`` is passed directly to
    ``generate()`` via the top-level ``engine_style=`` kwarg (engine builder
    dispatch in ``engine_styles.py``) while ``WingStyle`` is plumbed via
    ``ShapeParams.wing_style`` (wing placer dispatch in ``shape/wings.py``);
    a regression that only surfaces in the interaction between a specific
    engine layout and a specific wing layout (e.g., a wide quad-cluster
    engine anchor colliding with a swept-back gull wing's stern anchor at
    the same Z-band) would slip past both single-axis tests. We slice each
    enum to the first three members in declaration order via
    ``list(EngineStyle)[:3]`` / ``list(WingStyle)[:3]`` (sourced dynamically
    off the enums so the slice tracks future reorderings) for 3 × 3 × 3 = 27
    representative nodes. Failure messages name the offending
    ``(engine_style, wing_style, seed)`` tuple via the parametrize IDs plus
    an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, wing_style=wing_style,
    )
    res = generate(
        seed,
        shape_params=params,
        engine_style=engine_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"engine_style={engine_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"engine_style={engine_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"engine_style={engine_style.value} "
        f"wing_style={wing_style.value} seed={seed} produced 0 blocks"
    )


# --------- cockpit_style × engine_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the cockpit×hull / cockpit×wing / hull×engine /
# engine×wing / palette×cockpit cross-product tests above: pins
# (CockpitStyle × EngineStyle × seed) deterministically to catch regressions
# that only surface in the interaction between cockpit placement
# (``ShapeParams.cockpit_style`` → cockpit placer dispatch in
# ``shape/cockpit.py``) and engine placement (``engine_style=`` → engine
# builder dispatch in ``engine_styles.py``). The single-axis
# ``cockpit_style_seed_grid`` and ``engine_style_seed_grid`` parametrize tests
# above pin each axis on its own, but a regression that only surfaces when,
# e.g., a tall canopy/dome cockpit silhouette is combined with a wide
# quad-cluster engine layout (the engine anchor row crowding the cockpit's
# Z-band at the stern transition) would slip past both single-axis tests. We
# slice each enum to the first three members in declaration order via
# ``list(CockpitStyle)[:3]`` / ``list(EngineStyle)[:3]`` (sourced dynamically
# off the enums so the slice tracks future reorderings) for 3 × 3 × 3 = 27
# representative nodes. Failure node IDs read
# ``[seed-engine_style-cockpit_style]`` so a regression in any single
# (cockpit, engine) interaction is self-naming.


_COCKPIT_ENGINE_GRID_COCKPITS = list(CockpitStyle)[:3]
_COCKPIT_ENGINE_GRID_ENGINES = list(EngineStyle)[:3]


@pytest.mark.parametrize(
    "cockpit_style", _COCKPIT_ENGINE_GRID_COCKPITS, ids=lambda c: c.value,
)
@pytest.mark.parametrize(
    "engine_style", _COCKPIT_ENGINE_GRID_ENGINES, ids=lambda e: e.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_cockpit_style_x_engine_style_seed_grid_generates_non_empty_litematic(
    tmp_path, cockpit_style, engine_style, seed
):
    """``CockpitStyle`` × ``EngineStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``cockpit_style_seed_grid`` and
    ``engine_style_seed_grid`` parametrize tests above, and a sibling of the
    other enum cross-product tests (cockpit×hull / cockpit×wing /
    hull×engine / engine×wing / palette×cockpit). ``CockpitStyle`` is plumbed
    via ``ShapeParams.cockpit_style`` (cockpit placer dispatch in
    ``shape/cockpit.py``) while ``EngineStyle`` is passed directly to
    ``generate()`` via the top-level ``engine_style=`` kwarg (engine builder
    dispatch in ``engine_styles.py``); a regression that only surfaces in
    the interaction between a specific cockpit silhouette and a specific
    engine layout (e.g., a tall dome cockpit colliding with a wide
    quad-cluster engine anchor at the same Z-band as the stern transition)
    would slip past both single-axis tests. We slice each enum to the first
    three members in declaration order via ``list(CockpitStyle)[:3]`` /
    ``list(EngineStyle)[:3]`` (sourced dynamically off the enums so the
    slice tracks future reorderings) for 3 × 3 × 3 = 27 representative
    nodes. Failure messages name the offending
    ``(cockpit_style, engine_style, seed)`` tuple via the parametrize IDs
    plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, cockpit_style=cockpit_style,
    )
    res = generate(
        seed,
        shape_params=params,
        engine_style=engine_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"cockpit_style={cockpit_style.value} "
            f"engine_style={engine_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"cockpit_style={cockpit_style.value} "
        f"engine_style={engine_style.value} seed={seed} produced 0 blocks"
    )


# --------- hull_style × wing_style × seed-grid stability (cross-axis) ---------
#
# Cross-axis sibling of the cockpit×hull / cockpit×wing / hull×engine /
# engine×wing / cockpit×engine / palette×cockpit cross-product tests above:
# pins (HullStyle × WingStyle × seed) deterministically to catch regressions
# that only surface in the interaction between hull silhouette
# (``hull_style=`` → hull profile in ``structure_styles.py``) and wing
# placement (``ShapeParams.wing_style`` → wing placer dispatch in
# ``shape/wings.py``). The single-axis ``hull_style_seed_grid`` and
# ``wing_style_seed_grid`` parametrize tests above pin each axis on its own,
# but a regression that only surfaces when, e.g., a narrow dagger hull is
# combined with a wide swept-back gull wing (the wing's stern anchor column
# falling outside the dagger's thin Z-band) would slip past both single-axis
# tests. We slice each enum to the first three members in declaration order
# via ``list(HullStyle)[:3]`` / ``list(WingStyle)[:3]`` (sourced dynamically
# off the enums so the slice tracks future reorderings) for 3 × 3 × 3 = 27
# representative nodes. Failure node IDs read
# ``[seed-wing_style-hull_style]`` so a regression in any single
# (hull, wing) interaction is self-naming.


_HULL_WING_GRID_HULLS = list(HullStyle)[:3]
_HULL_WING_GRID_WINGS = list(WingStyle)[:3]


@pytest.mark.parametrize(
    "hull_style", _HULL_WING_GRID_HULLS, ids=lambda h: h.value,
)
@pytest.mark.parametrize(
    "wing_style", _HULL_WING_GRID_WINGS, ids=lambda w: w.value,
)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_hull_style_x_wing_style_seed_grid_generates_non_empty_litematic(
    tmp_path, hull_style, wing_style, seed
):
    """``HullStyle`` × ``WingStyle`` × small seed grid → non-empty ``.litematic``.

    Cross-axis companion to the single-axis ``hull_style_seed_grid`` and
    ``wing_style_seed_grid`` parametrize tests above, and a sibling of the
    other enum cross-product tests (cockpit×hull / cockpit×wing /
    hull×engine / engine×wing / cockpit×engine / palette×cockpit).
    ``HullStyle`` is passed directly to ``generate()`` via the top-level
    ``hull_style=`` kwarg (hull silhouette profile in
    ``structure_styles.py``) while ``WingStyle`` is plumbed via
    ``ShapeParams.wing_style`` (wing placer dispatch in ``shape/wings.py``);
    a regression that only surfaces in the interaction between a specific
    hull silhouette and a specific wing layout (e.g., a narrow dagger hull
    combined with a swept-back gull wing where the wing's stern anchor
    column falls outside the dagger's thin Z-band) would slip past both
    single-axis tests. We slice each enum to the first three members in
    declaration order via ``list(HullStyle)[:3]`` / ``list(WingStyle)[:3]``
    (sourced dynamically off the enums so the slice tracks future
    reorderings) for 3 × 3 × 3 = 27 representative nodes. Failure messages
    name the offending ``(hull_style, wing_style, seed)`` tuple via the
    parametrize IDs plus an explicit ``pytest.fail`` message so a regression
    localizes immediately.
    """
    params = ShapeParams(
        length=16, width_max=8, height_max=6, wing_style=wing_style,
    )
    res = generate(
        seed,
        shape_params=params,
        hull_style=hull_style,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"hull_style={hull_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"hull_style={hull_style.value} "
            f"wing_style={wing_style.value} seed={seed}"
        )
    assert res.block_count > 0, (
        f"hull_style={hull_style.value} "
        f"wing_style={wing_style.value} seed={seed} produced 0 blocks"
    )


# --------- greeble_style × greeble_density × seed-grid stability (cross-axis) ---------
#
# Numeric-axis sibling of the palette × greeble_density and
# greeble_density × weapon_count cross-product tests above: pins
# (``GreebleType`` × ``greeble_density`` × seed) deterministically to catch
# regressions that only surface in the interaction between a single greeble
# builder (``greeble_types=[GreebleType(...)]`` → per-builder dispatch in
# ``greeble_styles.py``) and the multi-cell scatter density
# (``greeble_density=`` top-level kwarg → multi-cell scatter pass in
# ``greeble_styles.scatter_greebles``). The single-axis
# ``test_property_greeble_type_seed_grid_generates_non_empty_litematic`` pins
# every ``GreebleType`` member at a fixed mid density, and the single-axis
# ``test_property_greeble_density_seed_grid_generates_non_empty_litematic``
# pins the density axis on its own with the default unrestricted greeble-type
# list, but neither exercises the CROSS-axis interaction between a specific
# restricted-builder list and a specific scatter density. A regression that
# only surfaces when, e.g., the ``ANTENNA`` builder combined with
# ``greeble_density=1.0`` (max scatter claiming every surface anchor with the
# narrow column antenna footprint exhausting the surface anchor set) or the
# ``BATTLE_DAMAGE`` builder combined with ``greeble_density=0.0`` (no-op
# scatter so the restricted-type list never fires) would slip past both
# single-axis tests. We slice ``GreebleType`` to the first three members in
# declaration order via ``list(GreebleType)[:3]`` (sourced dynamically off the
# enum so the slice tracks future reorderings) and pin three densities
# (``0.0`` no-greebles bare-hull / ``0.5`` mid / ``1.0`` max scatter — same
# extremes as the ``test_property_greeble_density_x_weapon_count_seed_grid``
# and ``test_property_palette_x_greeble_density_seed_grid`` siblings) for
# 3 × 3 × 3 = 27 representative nodes. Failure node IDs read
# ``[seed-greeble_density-greeble_type]`` so a regression in any single
# (greeble_type, density) interaction is self-naming. ``greeble_density`` is
# plumbed via the top-level ``generate(greeble_density=...)`` kwarg (not via
# ``ShapeParams``) since the top-level kwarg accepts the full ``[0.0, 1.0]``
# range and matches the numeric-axis siblings' plumbing; ``greeble_types`` is
# passed as a single-member list mirroring how the ``--greeble-style TYPE``
# CLI flag plumbs (``cli.py:687`` → ``[GreebleType(args.greeble_style)]``).


_GREEBLE_DENSITY_GRID_TYPES = list(GreebleType)[:3]


@pytest.mark.parametrize(
    "greeble_type", _GREEBLE_DENSITY_GRID_TYPES, ids=lambda t: t.value,
)
@pytest.mark.parametrize("greeble_density", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_greeble_style_x_greeble_density_seed_grid_generates_non_empty_litematic(
    tmp_path, greeble_type, greeble_density, seed
):
    """``GreebleType`` × ``greeble_density`` × small seed grid → non-empty ``.litematic``.

    Numeric-axis cross-product companion to the single-axis
    ``greeble_type_seed_grid`` and ``greeble_density_seed_grid`` parametrize
    tests above, and a sibling of the numeric-axis
    ``greeble_density × weapon_count`` and ``palette × greeble_density``
    cross-axis tests. ``GreebleType`` is plumbed via ``generate(greeble_types=[...])``
    (per-builder dispatch in ``greeble_styles.py``, exactly how the
    ``--greeble-style TYPE`` CLI flag in ``cli.py`` plumbs) while
    ``greeble_density`` is passed directly to ``generate()`` via the top-level
    ``greeble_density=`` kwarg (multi-cell scatter pass in
    ``greeble_styles.scatter_greebles``); the top-level kwarg accepts the
    full ``[0.0, 1.0]`` range so we plumb it that way rather than through
    ``ShapeParams``, mirroring the numeric-axis siblings exactly. A
    regression that only surfaces in the interaction between a specific
    restricted-builder list and a specific density (e.g., the ``ANTENNA``
    builder combined with ``greeble_density=1.0`` exhausting the surface
    anchor set with a narrow column footprint) would slip past both
    single-axis tests. We slice ``GreebleType`` to the first three members
    in declaration order via ``list(GreebleType)[:3]`` (sourced dynamically
    off the enum so the slice tracks future reorderings) and pin three
    densities (``0.0`` / ``0.5`` / ``1.0``) × the small fixed seed grid
    ``[0, 1, 7]`` for 3 × 3 × 3 = 27 representative nodes that hit the
    extremes of both axes without inflating the suite to the full
    ``GreebleType`` × density cross-product. At ``greeble_density=0.0`` the
    greeble scatter no-ops but the ship still generates a non-empty
    hull/cockpit/engines/wings silhouette so ``block_count > 0`` is the right
    floor invariant for every node. Failure messages name the offending
    ``(greeble_type, greeble_density, seed)`` tuple via the parametrize IDs
    plus an explicit ``pytest.fail`` message so a regression localizes
    immediately.
    """
    params = ShapeParams(length=16, width_max=8, height_max=6)
    res = generate(
        seed,
        shape_params=params,
        greeble_types=[greeble_type],
        greeble_density=greeble_density,
        out_dir=tmp_path,
        filename="ship.litematic",
    )
    if not res.litematic_path.exists():
        pytest.fail(
            f"generate() did not write a .litematic for "
            f"greeble_type={greeble_type.value} "
            f"greeble_density={greeble_density} seed={seed}"
        )
    size = os.path.getsize(res.litematic_path)
    if size <= 0:
        pytest.fail(
            f"generate() wrote a zero-byte .litematic for "
            f"greeble_type={greeble_type.value} "
            f"greeble_density={greeble_density} seed={seed}"
        )
    assert res.block_count > 0, (
        f"greeble_type={greeble_type.value} "
        f"greeble_density={greeble_density} seed={seed} produced 0 blocks"
    )


@pytest.mark.parametrize(
    "palette_name",
    ["sci_fi_industrial", "sleek_modern", "cyberpunk_neon", "neon_arcade"],
)
def test_property_palette_parse_is_stable(palette_name):
    """Parsing the same palette YAML twice yields equal Palette objects.

    :class:`Palette` is a frozen dataclass, so ``==`` compares name + blocks
    + preview_colors. The round-trip check guards against accidental
    dependence on load-time state (e.g. mutation of a shared cache).
    """
    path = palettes_dir() / f"{palette_name}.yaml"
    a = Palette.load(path)
    b = Palette.load(path)
    assert a == b
    # Loading via the higher-level helper must agree too.
    c = load_palette(palette_name)
    assert a == c
    # Name round-trips verbatim.
    assert a.name == b.name
