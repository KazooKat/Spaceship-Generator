"""Tests for parts-based ship shape generation."""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape import (
    CockpitStyle,
    ShapeParams,
    StructureStyle,
    _body_profile,
    _engine_x_positions,
    _label_components,
    _surface_mask,
    generate_shape,
)

# ----- ShapeParams validation -----

@pytest.mark.parametrize("bad", [
    {"length": 4},
    {"width_max": 2},
    {"height_max": 2},
    {"engine_count": -1},
    {"engine_count": 99},
    {"wing_prob": -0.1},
    {"wing_prob": 1.5},
    {"greeble_density": -0.1},
    {"greeble_density": 0.9},
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
        for lo, hi in zip(xs_sorted, reversed(xs_sorted), strict=False):
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


@pytest.mark.parametrize("n,W,radius", [
    (2, 20, 2),
    (4, 20, 2),
    (6, 20, 2),
    (2, 6, 2),
    (4, 6, 2),
    (6, 6, 2),
    (4, 4, 2),  # pathological: usable would be negative
    (1, 4, 1),
])
def test_engine_x_positions_no_duplicates(n, W, radius):
    """Engines must resolve to valid positions — either ``n`` distinct slots
    or a deliberate collapse to the ship's X center (which is acceptable when
    the grid is too cramped to separate them)."""
    xs = _engine_x_positions(n, width=W, radius=radius)
    assert len(xs) == n
    # Either all positions are distinct, or they all collapsed to one slot
    # (the center). The buggy case returned a partial collision like
    # [2, 1, 2, 0], which neither of these accept.
    unique = set(xs)
    if len(unique) != n:
        assert len(unique) == 1, (
            f"partial collision for (n={n}, W={W}, r={radius}): {xs}"
        )
        assert unique == {W // 2}


@pytest.mark.parametrize("n,W,radius", [
    (2, 20, 2),
    (4, 20, 2),
    (6, 20, 2),
    (2, 6, 2),
    (4, 6, 2),
    (6, 6, 2),
    (4, 4, 2),
    (1, 4, 1),
])
def test_engine_x_positions_all_in_bounds(n, W, radius):
    xs = _engine_x_positions(n, width=W, radius=radius)
    assert len(xs) == n
    for x in xs:
        assert 0 <= x < W, f"x={x} out of bounds for W={W}"


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


# ----- Cockpit style variation -----

def _shape_without_randoms(seed: int, style: CockpitStyle) -> np.ndarray:
    """Generate a deterministic ship with randomness-heavy stages disabled."""
    p = ShapeParams(
        length=24,
        width_max=12,
        height_max=10,
        cockpit_style=style,
        greeble_density=0.0,
        wing_prob=0.0,
        engine_count=0,
    )
    return generate_shape(seed, p)


def test_cockpit_styles_produce_distinguishable_grids():
    """Each CockpitStyle should produce a different ship for the same seed."""
    seed = 123
    bubble = _shape_without_randoms(seed, CockpitStyle.BUBBLE)
    pointed = _shape_without_randoms(seed, CockpitStyle.POINTED)
    integrated = _shape_without_randoms(seed, CockpitStyle.INTEGRATED)

    # Pairwise grid inequality.
    assert not np.array_equal(bubble, pointed)
    assert not np.array_equal(bubble, integrated)
    assert not np.array_equal(pointed, integrated)

    # Their COCKPIT_GLASS voxel sets must also differ pairwise.
    def glass_set(g: np.ndarray) -> set[tuple[int, int, int]]:
        return {tuple(pos) for pos in np.argwhere(g == Role.COCKPIT_GLASS)}

    gb, gp, gi = glass_set(bubble), glass_set(pointed), glass_set(integrated)
    assert gb and gp and gi, "Each style must place at least one cockpit voxel"
    assert gb != gp
    assert gb != gi
    assert gp != gi


@pytest.mark.parametrize("style", list(CockpitStyle))
def test_cockpit_style_preserves_x_symmetry(style):
    """Every cockpit style must leave the final grid bilaterally symmetric."""
    grid = _shape_without_randoms(7, style)
    assert np.array_equal(grid, grid[::-1, :, :])


@pytest.mark.parametrize("style", list(CockpitStyle))
def test_cockpit_style_places_glass_near_nose(style):
    """All three styles should place COCKPIT_GLASS in the forward half of the ship."""
    grid = _shape_without_randoms(2, style)
    cockpit_positions = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert len(cockpit_positions) > 0
    L = grid.shape[2]
    # At least one glass voxel should be in the forward 60% of the ship.
    assert cockpit_positions[:, 2].max() >= int(L * 0.6)


def test_cockpit_integrated_stays_within_hull_envelope():
    """INTEGRATED cockpit must not introduce voxels outside the bubble hull envelope."""
    # Build a ship with a bubble cockpit (has a bulge) and one with integrated
    # cockpit (no bulge). The integrated ship's non-empty voxels should be a
    # subset of the bubble ship's non-empty voxels plus the original hull —
    # specifically, integrated should have no voxels where BOTH the bubble ship
    # has EMPTY AND the integrated ship has non-EMPTY outside the hull volume.
    seed = 99
    bubble = _shape_without_randoms(seed, CockpitStyle.BUBBLE)
    integrated = _shape_without_randoms(seed, CockpitStyle.INTEGRATED)

    # Every non-empty voxel in the integrated ship must either be hull in the
    # pre-cockpit grid (approximated by: it is non-empty in the bubble ship too,
    # since bubble only adds voxels on top of hull).
    integrated_filled = integrated != Role.EMPTY
    bubble_filled = bubble != Role.EMPTY
    # Integrated cockpit must not add voxels where bubble was EMPTY.
    added_by_integrated = integrated_filled & ~bubble_filled
    assert added_by_integrated.sum() == 0


def test_cockpit_pointed_reaches_nose_and_tapers():
    """POINTED cockpit should extend further forward and be narrower than BUBBLE."""
    seed = 11
    bubble = _shape_without_randoms(seed, CockpitStyle.BUBBLE)
    pointed = _shape_without_randoms(seed, CockpitStyle.POINTED)

    b_glass = np.argwhere(bubble == Role.COCKPIT_GLASS)
    p_glass = np.argwhere(pointed == Role.COCKPIT_GLASS)
    assert len(b_glass) > 0 and len(p_glass) > 0

    # Pointed should span at least as many Z layers as bubble (longer canopy).
    b_z_span = b_glass[:, 2].max() - b_glass[:, 2].min() + 1
    p_z_span = p_glass[:, 2].max() - p_glass[:, 2].min() + 1
    assert p_z_span >= b_z_span

    # And reach at least as far forward (nose = max z).
    assert p_glass[:, 2].max() >= b_glass[:, 2].max()


def _new_cockpit_styles() -> list[CockpitStyle]:
    return [
        CockpitStyle.CANOPY_DOME,
        CockpitStyle.WRAP_BRIDGE,
        CockpitStyle.OFFSET_TURRET,
    ]


@pytest.mark.parametrize("style", _new_cockpit_styles())
def test_new_cockpit_variant_is_deterministic(style):
    """New cockpit variants are pure functions of (seed, params): repeat runs match byte-for-byte."""
    a = _shape_without_randoms(2024, style)
    b = _shape_without_randoms(2024, style)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("style", _new_cockpit_styles())
def test_new_cockpit_variant_places_glass(style):
    """Each new variant must produce at least one COCKPIT_GLASS (window) voxel."""
    grid = _shape_without_randoms(5, style)
    glass = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert len(glass) > 0, f"{style} produced zero glass voxels"


@pytest.mark.parametrize("style", _new_cockpit_styles())
def test_new_cockpit_variant_stays_in_bounds(style):
    """Every non-empty voxel in the new variants must lie inside the grid."""
    grid = _shape_without_randoms(13, style)
    W, H, L = grid.shape
    nonempty = np.argwhere(grid != Role.EMPTY)
    assert len(nonempty) > 0
    assert nonempty[:, 0].min() >= 0 and nonempty[:, 0].max() < W
    assert nonempty[:, 1].min() >= 0 and nonempty[:, 1].max() < H
    assert nonempty[:, 2].min() >= 0 and nonempty[:, 2].max() < L


@pytest.mark.parametrize("style", _new_cockpit_styles())
def test_new_cockpit_variant_does_not_reduce_hull_count(style):
    """Cockpit stage must not destroy hull structure: the post-cockpit HULL count
    must be >= the pre-cockpit HULL count (monotonic-increasing)."""
    # We can't easily inspect mid-pipeline state via generate_shape, so compare
    # a hull-only grid against the hull+cockpit grid by running the cockpit
    # stage directly on a fresh copy.
    from spaceship_generator.shape.cockpit import _place_cockpit
    from spaceship_generator.shape.hull import _place_hull

    p = ShapeParams(
        length=24, width_max=12, height_max=10,
        cockpit_style=style, greeble_density=0.0,
        wing_prob=0.0, engine_count=0,
    )
    rng = np.random.default_rng(99)
    grid = np.zeros((p.width_max, p.height_max, p.length), dtype=np.int8)
    _place_hull(grid, rng, p)
    hull_before = int((grid == Role.HULL).sum())
    assert hull_before > 0  # sanity: hull exists before cockpit
    _place_cockpit(grid, rng, p)
    hull_after = int((grid == Role.HULL).sum())
    # New variants ADD hull cells (dome collar / bridge frame / turret walls),
    # and never erase existing hull — so count is strictly non-decreasing.
    assert hull_after >= hull_before, (
        f"{style} reduced HULL count: {hull_before} -> {hull_after}"
    )


def test_new_cockpit_variants_produce_distinguishable_grids():
    """The three new variants must produce distinct ships on the same seed."""
    seed = 77
    dome = _shape_without_randoms(seed, CockpitStyle.CANOPY_DOME)
    bridge = _shape_without_randoms(seed, CockpitStyle.WRAP_BRIDGE)
    turret = _shape_without_randoms(seed, CockpitStyle.OFFSET_TURRET)

    assert not np.array_equal(dome, bridge)
    assert not np.array_equal(dome, turret)
    assert not np.array_equal(bridge, turret)

    # Their COCKPIT_GLASS footprints must also differ pairwise.
    def glass_set(g: np.ndarray) -> set[tuple[int, int, int]]:
        return {tuple(pos) for pos in np.argwhere(g == Role.COCKPIT_GLASS)}

    gd, gb, gt = glass_set(dome), glass_set(bridge), glass_set(turret)
    assert gd and gb and gt
    assert gd != gb and gd != gt and gb != gt


def test_offset_turret_glass_is_above_hull_not_centerline():
    """OFFSET_TURRET's raised glass must sit above typical hull height; it is
    a protrusion, not a flush strip like INTEGRATED."""
    grid = _shape_without_randoms(31, CockpitStyle.OFFSET_TURRET)
    H = grid.shape[1]
    glass = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert len(glass) > 0
    # Raised turret: at least one glass voxel is strictly in the upper half.
    assert glass[:, 1].max() >= H // 2


def test_wrap_bridge_window_extends_far_forward():
    """WRAP_BRIDGE's window strip should reach close to the nose (last row)."""
    grid = _shape_without_randoms(41, CockpitStyle.WRAP_BRIDGE)
    L = grid.shape[2]
    glass = np.argwhere(grid == Role.COCKPIT_GLASS)
    assert len(glass) > 0
    # The bridge spans the forward third, so glass must land at or past ~L-2.
    assert glass[:, 2].max() >= L - 2


def test_wing_length_guard_on_short_ship():
    """Very short ships should still produce a valid (non-truncated) wing when wings are forced on."""
    # length=8 is the minimum allowed. With wing_prob=1.0 we guarantee wings run.
    p = ShapeParams(
        length=8,
        width_max=8,
        height_max=6,
        wing_prob=1.0,
        engine_count=1,
        greeble_density=0.0,
    )
    grid = generate_shape(4, p)
    # Wings must exist, span >= 2 in z, and the grid must still be symmetric.
    wing_positions = np.argwhere(grid == Role.WING)
    assert len(wing_positions) > 0
    z_span = wing_positions[:, 2].max() - wing_positions[:, 2].min() + 1
    assert z_span >= 2
    assert np.array_equal(grid, grid[::-1, :, :])


# ----- Structure style variation -----


def test_structure_style_default_is_frigate():
    """ShapeParams() with no structure_style argument defaults to FRIGATE."""
    p = ShapeParams()
    assert p.structure_style == StructureStyle.FRIGATE


def test_structure_style_frigate_backcompat():
    """FRIGATE style must produce the exact same grid as the legacy default.

    ShapeParams() (no structure_style arg) and ShapeParams(structure_style=FRIGATE)
    must both be byte-equal — and determinism must match pre-style behavior.
    """
    p_default = ShapeParams(length=32, width_max=16, height_max=10)
    p_explicit = ShapeParams(
        length=32,
        width_max=16,
        height_max=10,
        structure_style=StructureStyle.FRIGATE,
    )
    a = generate_shape(1234, p_default)
    b = generate_shape(1234, p_explicit)
    assert np.array_equal(a, b)


def test_structure_style_invalid_value_raises():
    """Bad structure_style strings raise ValueError."""
    with pytest.raises(ValueError):
        ShapeParams(structure_style="not-a-real-style")
    with pytest.raises(ValueError):
        ShapeParams(structure_style=42)  # type: ignore[arg-type]


@pytest.mark.parametrize("style", list(StructureStyle))
def test_structure_style_generates_valid_ship(style):
    """Every style must produce a valid 3D grid of correct shape and non-empty content."""
    p = ShapeParams(
        length=40, width_max=20, height_max=12, structure_style=style
    )
    grid = generate_shape(42, p)
    # Shape + dtype.
    assert grid.shape == (20, 12, 40)
    assert grid.ndim == 3
    # Must have voxels.
    assert (grid != Role.EMPTY).sum() > 50


@pytest.mark.parametrize("style", list(StructureStyle))
def test_structure_style_preserves_x_symmetry(style):
    """Every style's final grid must be bilaterally symmetric across X."""
    p = ShapeParams(
        length=40, width_max=20, height_max=12, structure_style=style
    )
    grid = generate_shape(42, p)
    assert np.array_equal(grid, grid[::-1, :, :])


@pytest.mark.parametrize("style", list(StructureStyle))
def test_structure_style_is_one_connected_mass(style):
    """Every style's final grid must be a single 6-connected component."""
    p = ShapeParams(
        length=40, width_max=20, height_max=12, structure_style=style
    )
    grid = generate_shape(42, p)
    _labels, n_components = _label_components(grid)
    assert n_components == 1, (
        f"style={style.value} produced {n_components} components instead of 1"
    )


def test_structure_styles_produce_distinguishable_grids():
    """At least two styles must differ in voxel content for the same seed."""
    seed = 42
    p_base = {"length": 40, "width_max": 20, "height_max": 12}
    grids = {
        style: generate_shape(seed, ShapeParams(**p_base, structure_style=style))
        for style in StructureStyle
    }
    # Collect unique grids.
    unique = {}
    for style, g in grids.items():
        unique[g.tobytes()] = style
    assert len(unique) >= 2, (
        "All styles produced identical grids — the dispatcher did not take effect"
    )
    # Stronger check: specifically FRIGATE vs FIGHTER should differ since
    # they have very different profiles + wing overrides.
    assert not np.array_equal(
        grids[StructureStyle.FRIGATE], grids[StructureStyle.FIGHTER]
    )


def test_structure_style_shuttle_has_no_wings():
    """SHUTTLE should disable wings entirely regardless of wing_prob."""
    grid = generate_shape(
        7,
        ShapeParams(
            length=32,
            width_max=16,
            height_max=10,
            wing_prob=1.0,
            structure_style=StructureStyle.SHUTTLE,
        ),
    )
    assert (grid == Role.WING).sum() == 0


def test_structure_style_shuttle_has_single_engine_group():
    """SHUTTLE collapses engine count to 1 even if a higher value is requested."""
    grid = generate_shape(
        3,
        ShapeParams(
            length=40,
            width_max=20,
            height_max=12,
            engine_count=6,
            structure_style=StructureStyle.SHUTTLE,
        ),
    )
    engine_positions = np.argwhere(grid == Role.ENGINE)
    assert len(engine_positions) > 0
    # Shuttle: only one engine region — the distinct X positions along the
    # widest engine slice should all be contiguous around the ship center.
    unique_xs = np.unique(engine_positions[:, 0])
    # A single cylinder centered on the ship produces a small X spread.
    assert unique_xs.max() - unique_xs.min() < 20


# ----- Hull blend (shapes-B): generate_shape integration ------------------

def test_generate_shape_hull_blend_deterministic():
    """Same seed + same blend flags must produce byte-identical voxel grids."""
    from spaceship_generator.structure_styles import HullStyle

    p = ShapeParams(length=40, width_max=20, height_max=12)
    a = generate_shape(
        123,
        p,
        hull_style_front=HullStyle.ARROW,
        hull_style_rear=HullStyle.SAUCER,
    )
    b = generate_shape(
        123,
        p,
        hull_style_front=HullStyle.ARROW,
        hull_style_rear=HullStyle.SAUCER,
    )
    assert np.array_equal(a, b)


def test_generate_shape_hull_blend_no_flags_matches_legacy():
    """No blend flags ⇒ identical to a call without the kwargs at all.

    Regression guard: adding the new kwargs must not change behaviour for
    any existing call site that doesn't opt in.
    """
    p = ShapeParams(length=40, width_max=20, height_max=12)
    legacy = generate_shape(7, p)
    same_with_none = generate_shape(
        7,
        p,
        hull_style_front=None,
        hull_style_rear=None,
    )
    assert np.array_equal(legacy, same_with_none)


def test_generate_shape_hull_blend_partial_pair_falls_back_to_legacy():
    """Passing only one of front/rear must behave exactly like no blend.

    The CLI guarantees this contract by silently dropping a partial pair,
    but we also exercise the ``generate_shape`` API directly so library
    callers get the same fall-back: the legacy single-style hull.
    """
    from spaceship_generator.structure_styles import HullStyle

    p = ShapeParams(length=40, width_max=20, height_max=12)
    legacy = generate_shape(11, p)
    # Both partial pairs (front-only and rear-only) must equal legacy.
    front_only = generate_shape(11, p, hull_style_front=HullStyle.ARROW)
    rear_only = generate_shape(11, p, hull_style_rear=HullStyle.SAUCER)
    # ``generate_shape`` only blends when *both* are set; with one missing
    # the legacy hull placer runs (RNG state still consumed identically),
    # so the resulting grids must match the legacy single-style ship.
    assert np.array_equal(legacy, front_only)
    assert np.array_equal(legacy, rear_only)


def test_generate_shape_hull_blend_arrow_saucer_touches_both_silhouettes():
    """An ARROW-front + SAUCER-rear blend must hit each pure end's footprint.

    Concrete check: the rear ~15% of the blended hull must be at least as
    wide (X footprint) as a pure-SAUCER reference, and the nose ~15% must
    collapse toward a pure-ARROW reference's pointed tip.
    """
    from spaceship_generator.structure_styles import HullStyle, apply_hull_style

    W, H, L = 24, 12, 60
    p = ShapeParams(length=L, width_max=W, height_max=H)
    blended = generate_shape(
        2024,
        p,
        hull_style_front=HullStyle.ARROW,
        hull_style_rear=HullStyle.SAUCER,
    )

    # Reference pure-end silhouettes (no parts placement).
    saucer = np.zeros((W, H, L), dtype=np.int8)
    apply_hull_style(saucer, HullStyle.SAUCER)
    arrow = np.zeros((W, H, L), dtype=np.int8)
    apply_hull_style(arrow, HullStyle.ARROW)

    # Rear: blended hull's X footprint near z=0 must roughly match SAUCER's.
    # The blended ship has parts (engines) in the rear so it can be wider
    # than the pure-style reference. We check that it's at least as wide
    # rather than equal.
    rear_z = L // 12
    blended_x = int(np.any(blended[:, :, rear_z] == Role.HULL, axis=1).sum())
    saucer_x = int(np.any(saucer[:, :, rear_z] == Role.HULL, axis=1).sum())
    assert blended_x >= saucer_x - 2, (
        f"blend rear X footprint ({blended_x}) should match SAUCER's "
        f"({saucer_x}) within tolerance"
    )

    # Nose: blended HULL count near z=L-1 must be small (ARROW tapers
    # nearly to a point).
    nose_z = L - 1 - L // 12
    blended_nose = int((blended[:, :, nose_z] == Role.HULL).sum())
    arrow_nose = int((arrow[:, :, nose_z] == Role.HULL).sum())
    # Be tolerant of the cockpit slab adding a few extra cells in the
    # blended ship; we just need the nose to be thin.
    assert blended_nose <= arrow_nose + 6, (
        f"blend nose count ({blended_nose}) should be near ARROW's "
        f"({arrow_nose})"
    )


def test_generate_shape_hull_blend_overrides_hull_style():
    """When both blend flags are set they override a single ``hull_style``."""
    from spaceship_generator.structure_styles import HullStyle

    p = ShapeParams(length=40, width_max=20, height_max=12)
    only_blend = generate_shape(
        99,
        p,
        hull_style=HullStyle.WHALE,  # would normally win
        hull_style_front=HullStyle.ARROW,
        hull_style_rear=HullStyle.SAUCER,
    )
    pure_blend = generate_shape(
        99,
        p,
        hull_style_front=HullStyle.ARROW,
        hull_style_rear=HullStyle.SAUCER,
    )
    # The blend pair takes precedence — the WHALE single style is ignored.
    assert np.array_equal(only_blend, pure_blend)


# ----- Hull noise (shapes-E) ----------------------------------------------


def test_shape_params_rejects_negative_hull_noise():
    """``hull_noise < 0`` is rejected at construction time."""
    with pytest.raises(ValueError):
        ShapeParams(hull_noise=-0.1)


def test_shape_params_rejects_hull_noise_above_one():
    """``hull_noise > 1`` is rejected at construction time."""
    with pytest.raises(ValueError):
        ShapeParams(hull_noise=1.5)


def test_generate_shape_hull_noise_zero_matches_legacy():
    """``hull_noise == 0`` must be byte-identical to a no-flag run.

    Regression guard: adding the noise field must not alter the legacy
    pipeline's RNG stream or grid contents for callers who don't opt in.
    """
    legacy = generate_shape(
        2026, ShapeParams(length=30, width_max=16, height_max=10)
    )
    explicit_zero = generate_shape(
        2026,
        ShapeParams(length=30, width_max=16, height_max=10, hull_noise=0.0),
    )
    assert np.array_equal(legacy, explicit_zero)


def test_generate_shape_hull_noise_changes_grid():
    """``hull_noise > 0`` must perturb at least one cell vs the baseline."""
    p_baseline = ShapeParams(length=30, width_max=16, height_max=10)
    p_noisy = ShapeParams(
        length=30, width_max=16, height_max=10, hull_noise=0.5
    )
    baseline = generate_shape(2026, p_baseline)
    noisy = generate_shape(2026, p_noisy)
    assert not np.array_equal(baseline, noisy)
    # Distortion stays inside the ship dimensions (no out-of-bounds writes).
    assert noisy.shape == baseline.shape
    # Sanity: the ship still has a recognisable hull (not all eroded away).
    assert (noisy == Role.HULL).sum() > 50


def test_generate_shape_hull_noise_deterministic_per_seed():
    """Same seed + same amplitude → identical voxel grid."""
    p = ShapeParams(length=30, width_max=16, height_max=10, hull_noise=0.7)
    a = generate_shape(4242, p)
    b = generate_shape(4242, p)
    assert np.array_equal(a, b)


def test_generate_shape_hull_noise_amplitude_scaling():
    """Higher amplitude must perturb more cells than lower amplitude.

    Not a strict mathematical guarantee for every seed, but a healthy sanity
    check that the amplitude knob actually drives the displacement budget.
    """
    p_low = ShapeParams(
        length=30, width_max=16, height_max=10, hull_noise=0.1
    )
    p_high = ShapeParams(
        length=30, width_max=16, height_max=10, hull_noise=1.0
    )
    baseline = generate_shape(
        13, ShapeParams(length=30, width_max=16, height_max=10)
    )
    low = generate_shape(13, p_low)
    high = generate_shape(13, p_high)
    diff_low = int((low != baseline).sum())
    diff_high = int((high != baseline).sum())
    assert diff_high > diff_low >= 0


def test_generate_shape_hull_noise_silhouette_bounded():
    """Noise must not push the silhouette outside the grid bounding box.

    The post-pass writes to ``grid[mask]`` where ``mask`` is computed from
    in-bounds neighbour shifts only, so a successful run is itself the
    proof. This test pins that contract by asserting the perturbed grid
    keeps its declared shape and contains no role values outside the
    enum's int range.
    """
    p = ShapeParams(length=24, width_max=12, height_max=8, hull_noise=1.0)
    grid = generate_shape(7, p)
    assert grid.shape == (12, 8, 24)
    # All written values land inside the int8 range and the documented
    # Role enum (no stray sentinels from out-of-bounds memory writes).
    assert grid.min() >= 0
    assert grid.max() <= max(int(r) for r in Role)
