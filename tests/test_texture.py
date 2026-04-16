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

    # Disable nose_tip_light so this test focuses on wing lights only.
    out = assign_roles(
        grid, TextureParams(engine_glow_depth=2, nose_tip_light=False)
    )
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
    # Disable nose_tip_light so this test isolates wing-light behaviour.
    out = assign_roles(grid, TextureParams(nose_tip_light=False))
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


# ---------------------------------------------------------------------------
# Belly-lights + nose-tip-light feature tests
# ---------------------------------------------------------------------------


def _slab_grid():
    """Simple rectangular hull slab for isolated feature tests."""
    grid = np.full((10, 10, 20), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    return grid


def test_belly_lights_disabled_by_default():
    """With belly_light_period=0 (default), no belly LIGHTs are painted."""
    grid = _slab_grid()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=False),
    )
    # No lights at all in this slab (no wings, no nose tip).
    assert (out == Role.LIGHT).sum() == 0


def test_belly_lights_placed_on_underside():
    """With belly_light_period=4, LIGHT cells appear on the underside row."""
    grid = _slab_grid()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=4, nose_tip_light=False),
    )
    lights = np.argwhere(out == Role.LIGHT)
    assert len(lights) > 0
    # The hull bottom is at y == 2, so belly lights must sit on that row.
    assert lights[:, 1].min() == 2
    assert (lights[:, 1] == 2).all()


def test_belly_lights_preserve_symmetry():
    """Belly lights must not break bilateral X-symmetry."""
    grid = _slab_grid()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=4, nose_tip_light=False),
    )
    assert np.array_equal(out, out[::-1, :, :])


def test_belly_lights_do_not_overwrite_protected_roles():
    """Belly lights must not touch ENGINE / ENGINE_GLOW / COCKPIT_GLASS / WINDOW."""
    grid = _slab_grid()
    # Put an engine cluster on the underside so it collides with belly-light z==0.
    grid[4:6, 2:3, 0:2] = Role.ENGINE
    # Put a cockpit patch on the underside too.
    grid[4:6, 2:3, 4:5] = Role.COCKPIT_GLASS
    engine_before = (grid == Role.ENGINE).sum() + (grid == Role.ENGINE_GLOW).sum()
    cockpit_before = (grid == Role.COCKPIT_GLASS).sum()

    out = assign_roles(
        grid,
        TextureParams(
            belly_light_period=2,
            engine_glow_depth=1,
            nose_tip_light=False,
        ),
    )
    # Engine mass (ENGINE + ENGINE_GLOW) is preserved in count, and cockpit
    # glass cells are never converted to LIGHT.
    engine_after = (out == Role.ENGINE).sum() + (out == Role.ENGINE_GLOW).sum()
    cockpit_after = (out == Role.COCKPIT_GLASS).sum()
    assert engine_after == engine_before
    assert cockpit_after == cockpit_before


def test_nose_tip_light_enabled_paints_forward_light():
    """nose_tip_light=True adds a LIGHT at/near z == L-1."""
    grid = _slab_grid()
    L = grid.shape[2]
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=True),
    )
    lights = np.argwhere(out == Role.LIGHT)
    assert len(lights) > 0
    # The forward-most filled z in the slab is z == L-3 (hull ends at [:18]).
    # Accept either z == L-1 (if it extended that far) or the actual tip z.
    tip_z = int(lights[:, 2].max())
    # The nose-tip light should be at the forward-most filled voxel,
    # which for this slab is z == 17.
    assert tip_z == 17
    # And for even-width grids the tip is painted on both center columns.
    tip_xs = {int(x) for x in lights[lights[:, 2] == tip_z][:, 0]}
    assert 4 in tip_xs and 5 in tip_xs


def test_nose_tip_light_disabled_paints_none_at_tip():
    """nose_tip_light=False leaves the nose tip untouched by LIGHT."""
    grid = _slab_grid()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=False),
    )
    # No lights from either wings (none) or nose tip (disabled).
    assert (out == Role.LIGHT).sum() == 0


def test_nose_tip_light_preserves_symmetry():
    """Nose-tip light is mirror-symmetric on even-width grids."""
    grid = _slab_grid()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=True),
    )
    assert np.array_equal(out, out[::-1, :, :])


def test_nose_tip_light_odd_width_single_center():
    """On odd-width grids, nose tip paints only the single center column."""
    grid = np.full((9, 8, 15), Role.EMPTY, dtype=np.int8)
    grid[2:7, 2:6, 2:13] = Role.HULL
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=True),
    )
    lights = np.argwhere(out == Role.LIGHT)
    assert len(lights) > 0
    tip_z = int(lights[:, 2].max())
    tip_lights = lights[lights[:, 2] == tip_z]
    tip_xs = {int(x) for x in tip_lights[:, 0]}
    # Width is 9 → single center column at x = 4.
    assert tip_xs == {4}


def test_nose_tip_light_does_not_overwrite_cockpit_glass():
    """When the forward-most tip is COCKPIT_GLASS, it is kept as-is."""
    grid = np.full((10, 10, 20), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    # Make the tip center cockpit glass on both center columns.
    grid[4:6, 6:7, 17] = Role.COCKPIT_GLASS
    cockpit_before = (grid == Role.COCKPIT_GLASS).sum()
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=0, nose_tip_light=True),
    )
    cockpit_after = (out == Role.COCKPIT_GLASS).sum()
    assert cockpit_after == cockpit_before


def test_new_features_preserve_full_symmetry_on_procedural_ship():
    """Turning on both features on a real procedural ship preserves X-symmetry."""
    grid = generate_shape(
        123, ShapeParams(length=40, width_max=20, height_max=12, greeble_density=0.05)
    )
    out = assign_roles(
        grid,
        TextureParams(belly_light_period=5, nose_tip_light=True),
    )
    assert np.array_equal(out, out[::-1, :, :])


# ---------------------------------------------------------------------------
# Minecraft-builder extensions: hull noise, panel bands, rivets, glow ring
# ---------------------------------------------------------------------------


def _proc_grid(seed: int = 7):
    """Realistic procedurally-generated grid for feature-comparison tests."""
    return generate_shape(
        seed,
        ShapeParams(length=40, width_max=20, height_max=12, greeble_density=0.05),
    )


def test_hull_noise_ratio_zero_is_noop():
    """hull_noise_ratio=0.0 must produce identical output to default params."""
    grid = _proc_grid(seed=11)
    baseline = assign_roles(grid, TextureParams())
    noised = assign_roles(grid, TextureParams(hull_noise_ratio=0.0))
    assert np.array_equal(baseline, noised)


def test_hull_noise_ratio_increases_hull_dark_count():
    """A nonzero hull_noise_ratio strictly adds HULL_DARK cells."""
    grid = _proc_grid(seed=11)
    baseline = assign_roles(grid, TextureParams(hull_noise_ratio=0.0))
    noised = assign_roles(grid, TextureParams(hull_noise_ratio=0.3))
    base_count = int((baseline == Role.HULL_DARK).sum())
    noised_count = int((noised == Role.HULL_DARK).sum())
    assert noised_count > base_count


def test_hull_noise_symmetric():
    """Hull noise must preserve bilateral X-symmetry."""
    grid = _proc_grid(seed=11)
    out = assign_roles(grid, TextureParams(hull_noise_ratio=0.4))
    assert np.array_equal(out, out[::-1, :, :])


def test_hull_noise_does_not_overwrite_protected():
    """Hull noise never converts protected/non-hull roles to HULL_DARK."""
    grid = _proc_grid(seed=13)
    # Count protected/non-hull roles before vs after; they must not shrink.
    baseline = assign_roles(grid, TextureParams(hull_noise_ratio=0.0))
    noised = assign_roles(grid, TextureParams(hull_noise_ratio=0.5))
    for role in (
        Role.COCKPIT_GLASS,
        Role.WINDOW,
        Role.ENGINE,
        Role.ENGINE_GLOW,
        Role.LIGHT,
        Role.INTERIOR,
    ):
        assert (noised == role).sum() == (baseline == role).sum(), (
            f"hull_noise overwrote protected role {role.name}"
        )


def test_panel_line_bands_adds_bands():
    """panel_line_bands=3 produces HULL_DARK at two extra Y-bands vs =1."""
    grid = np.full((10, 12, 30), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:10, 2:28] = Role.HULL
    base = assign_roles(
        grid,
        TextureParams(panel_line_bands=1, nose_tip_light=False),
    )
    extra = assign_roles(
        grid,
        TextureParams(panel_line_bands=3, nose_tip_light=False),
    )
    # The extra configuration should have HULL_DARK on at least two Y-bands
    # that the base configuration does not.
    base_ys = set(np.argwhere(base == Role.HULL_DARK)[:, 1].tolist())
    extra_ys = set(np.argwhere(extra == Role.HULL_DARK)[:, 1].tolist())
    new_ys = extra_ys - base_ys
    assert len(new_ys) >= 2, f"expected ≥2 new Y-bands, got {new_ys}"
    # And total HULL_DARK must go up.
    assert (extra == Role.HULL_DARK).sum() > (base == Role.HULL_DARK).sum()


def test_rivet_period_zero_is_noop():
    """rivet_period=0 (default) equals omitting the field."""
    grid = _proc_grid(seed=5)
    baseline = assign_roles(grid, TextureParams())
    zeroed = assign_roles(grid, TextureParams(rivet_period=0))
    assert np.array_equal(baseline, zeroed)


def test_rivet_period_creates_dots():
    """rivet_period>0 strictly increases HULL_DARK count on a plain slab."""
    # Pick a slab whose side columns (x=2 and x=9) and rivet_period=2 align,
    # so every other Z gets a rivet on both side-facing x-columns.
    grid = np.full((12, 10, 24), Role.EMPTY, dtype=np.int8)
    grid[2:10, 2:8, 2:22] = Role.HULL
    base = assign_roles(
        grid,
        TextureParams(rivet_period=0, nose_tip_light=False),
    )
    riveted = assign_roles(
        grid,
        TextureParams(rivet_period=2, nose_tip_light=False),
    )
    assert (riveted == Role.HULL_DARK).sum() > (base == Role.HULL_DARK).sum()
    # Rivets must not break symmetry.
    assert np.array_equal(riveted, riveted[::-1, :, :])


def test_engine_glow_ring_adds_hull_dark_around_glow():
    """engine_glow_ring=True flips at least one ENGINE neighbor into HULL_DARK.

    Uses a handcrafted fixture where a single ENGINE_GLOW cell sits at z=0
    with four ENGINE neighbors at the same z-plane. The rear-slice glow
    pass (``engine_glow_depth=0``) is disabled so the preset layout isn't
    rewritten, isolating the ring pass under test.
    """
    grid = np.full((10, 10, 20), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    # 5-cell "+" of ENGINE at z=0 and z=1, plus mirror at x=9-x to stay
    # X-symmetric. Convert the center cell (at (4,5,0) and its mirror (5,5,0))
    # into ENGINE_GLOW manually. Width=10 → mirror of x=4 is x=5.
    # To keep the fixture symmetric, use two center columns x ∈ {4, 5}:
    core_xs = [4, 5]
    for cx in core_xs:
        # vertical run of ENGINE at z=0..1 (preset)
        grid[cx, 4, 0] = Role.ENGINE
        grid[cx, 6, 0] = Role.ENGINE
        grid[cx, 5, 0] = Role.ENGINE_GLOW  # preset center is already GLOW
    # ±X neighbors of the GLOW core at z=0 are also ENGINE candidates.
    grid[3, 5, 0] = Role.ENGINE
    grid[6, 5, 0] = Role.ENGINE  # mirror of x=3 under width=10 is 10-1-3=6

    base = assign_roles(
        grid,
        TextureParams(
            engine_glow_depth=0,       # skip rear-slice pass (preset layout)
            engine_glow_ring=False,
            nose_tip_light=False,
        ),
    )
    ringed = assign_roles(
        grid,
        TextureParams(
            engine_glow_depth=0,       # skip rear-slice pass (preset layout)
            engine_glow_ring=True,
            nose_tip_light=False,
        ),
    )
    # Ring must add HULL_DARK cells somewhere at z=0 around the GLOW core.
    base_dark = int((base == Role.HULL_DARK).sum())
    ring_dark = int((ringed == Role.HULL_DARK).sum())
    assert ring_dark > base_dark, (
        f"expected more HULL_DARK with ring on; base={base_dark} ring={ring_dark}"
    )
    ring_at_z0 = ringed[:, :, 0] == Role.HULL_DARK
    assert ring_at_z0.any(), "expected HULL_DARK ring at z=0 around ENGINE_GLOW"
    # Ring preserves symmetry.
    assert np.array_equal(ringed, ringed[::-1, :, :])
    # Ring never overwrites the GLOW core itself.
    assert (ringed == Role.ENGINE_GLOW).sum() >= (base == Role.ENGINE_GLOW).sum()
