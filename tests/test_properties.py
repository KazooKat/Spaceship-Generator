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
from spaceship_generator.palette import Palette, Role, load_palette, palettes_dir
from spaceship_generator.presets import SHIP_PRESETS, apply_preset
from spaceship_generator.shape import (
    CockpitStyle,
    ShapeParams,
    StructureStyle,
    generate_shape,
)
from spaceship_generator.structure_styles import HullStyle
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
# The seed grid is fixed (deterministic + fast); five seeds × ~50 palettes is
# ~250 generate() calls, which runs in well under 60 s on the dev box (~20 ms
# per call at length=16/width=8/height=6). pytest's parametrize IDs make any
# failure self-naming as ``[palette-seed]``.

_PALETTE_NAMES = sorted(p.stem for p in palettes_dir().glob("*.yaml"))
_PALETTE_STABILITY_SEEDS = [0, 1, 7, 42, 99]


@pytest.mark.parametrize("palette_name", _PALETTE_NAMES)
@pytest.mark.parametrize("seed", _PALETTE_STABILITY_SEEDS)
def test_property_palette_seed_grid_generates_non_empty_litematic(
    tmp_path, palette_name, seed
):
    """Every shipped palette × small seed grid → ``generate()`` writes a non-empty file.

    Catches palette-driven regressions (missing role, malformed block id,
    pipeline crash on a specific palette × seed combo) one tick earlier
    than a pure shape-property test would. Failure messages name both the
    offending palette and seed via the parametrize IDs, plus an explicit
    ``pytest.fail`` message if the file is missing or zero-bytes.
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
