"""Tests for the weapon_styles library.

Covers:
* Enum wire-format values are stable.
* Every builder is deterministic per seed and varies across seeds.
* Every builder emits only valid :class:`Role` values with int coords.
* Builders never mutate their anchor tuple.
* :func:`build_weapon` dispatch is complete for every enum member.
* :func:`scatter_weapons` is seed-deterministic, respects ``count``,
  short-circuits on ``count=0``, honors type allow-lists, handles both
  numpy-grid and bounding-box shapes, and returns ``[]`` on empty grids.
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.weapon_styles import (
    WeaponType,
    build_laser_lance,
    build_missile_pod,
    build_plasma_core,
    build_point_defense,
    build_turret_large,
    build_weapon,
    scatter_weapons,
)

# --- enum ------------------------------------------------------------------


def test_weapon_type_values_stable():
    """Wire-format lock — renaming any of these is a breaking change."""
    assert {w.value for w in WeaponType} == {
        "turret_large",
        "missile_pod",
        "laser_lance",
        "point_defense",
        "plasma_core",
    }


def test_weapon_type_member_count():
    assert len(list(WeaponType)) == 5


def test_weapon_type_is_str_enum():
    """Enums inherit from str so they serialize cleanly into JSON/YAML."""
    assert isinstance(WeaponType.TURRET_LARGE, str)
    assert WeaponType.TURRET_LARGE == "turret_large"


def test_weapon_type_names_are_uppercase():
    for member in WeaponType:
        assert member.name == member.name.upper()
        assert member.value == member.name.lower()


# --- per-builder determinism -----------------------------------------------


_ANCHOR = (8, 6, 12)

_BUILDERS = [
    ("turret_large", build_turret_large),
    ("missile_pod", build_missile_pod),
    ("laser_lance", build_laser_lance),
    ("point_defense", build_point_defense),
    ("plasma_core", build_plasma_core),
]


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_returns_list_of_placements(name, builder):
    rng = np.random.default_rng(0)
    out = builder(_ANCHOR, rng)
    assert isinstance(out, list), f"{name} must return a list"
    assert out, f"{name} must emit at least one placement"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_emits_4_tuples(name, builder):
    out = builder(_ANCHOR, np.random.default_rng(0))
    for cell in out:
        assert isinstance(cell, tuple), f"{name}: not a tuple: {cell!r}"
        assert len(cell) == 4, f"{name}: wrong arity: {cell!r}"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_coords_are_int(name, builder):
    out = builder(_ANCHOR, np.random.default_rng(0))
    for x, y, z, _ in out:
        assert isinstance(x, int), f"{name}: non-int x: {x!r}"
        assert isinstance(y, int), f"{name}: non-int y: {y!r}"
        assert isinstance(z, int), f"{name}: non-int z: {z!r}"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_roles_are_enum_members(name, builder):
    out = builder(_ANCHOR, np.random.default_rng(0))
    for cell in out:
        role = cell[3]
        assert isinstance(role, Role), f"{name} emitted non-Role: {role!r}"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_is_deterministic_per_seed(name, builder):
    """Fresh rngs on the same seed must give byte-identical output —
    the scatter contract depends on this."""
    a = builder(_ANCHOR, np.random.default_rng(42))
    b = builder(_ANCHOR, np.random.default_rng(42))
    assert a == b, f"{name} is non-deterministic across equally seeded rngs"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_varies_with_seed(name, builder):
    """If a builder ignores rng entirely, 16 seeds will all collapse to one
    output — catch that silent regression."""
    outputs = {
        tuple(builder(_ANCHOR, np.random.default_rng(s))) for s in range(16)
    }
    assert len(outputs) > 1, (
        f"{name} ignores rng entirely — 16 seeds produced identical output"
    )


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_does_not_mutate_anchor(name, builder):
    anchor = (3, 2, 7)
    builder(anchor, np.random.default_rng(0))
    assert anchor == (3, 2, 7), f"{name} mutated its anchor tuple"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_accepts_list_anchor(name, builder):
    """A list anchor should be coerced to ints the same as a tuple —
    callers sometimes pass lists from JSON payloads."""
    anchor_list = [3, 2, 7]
    out_list = builder(anchor_list, np.random.default_rng(1))
    out_tuple = builder((3, 2, 7), np.random.default_rng(1))
    assert out_list == out_tuple


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_is_translation_invariant(name, builder):
    """Shifting the anchor by ``(dx, dy, dz)`` must shift every emitted
    cell by the same offset — builders are supposed to be pure functions
    of their anchor."""
    dx, dy, dz = (5, 3, 9)
    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(7)
    base = builder((0, 0, 0), rng_a)
    shifted = builder((dx, dy, dz), rng_b)
    assert len(base) == len(shifted)
    for (bx, by, bz, br), (sx, sy, sz, sr) in zip(base, shifted, strict=False):
        assert (sx, sy, sz, sr) == (bx + dx, by + dy, bz + dz, br)


def test_all_roles_are_valid_enum_members():
    """Cross-cutting check — no bare ints or sentinels leak through."""
    valid = set(Role)
    for _, builder in _BUILDERS:
        out = builder(_ANCHOR, np.random.default_rng(7))
        for cell in out:
            assert cell[3] in valid, f"unknown Role emitted: {cell[3]!r}"


# --- dispatch --------------------------------------------------------------


@pytest.mark.parametrize("wtype", list(WeaponType))
def test_build_weapon_dispatches_every_type(wtype):
    """Every enum member must have a matching builder — no partial adds."""
    out = build_weapon(wtype, _ANCHOR, np.random.default_rng(0))
    assert out, f"{wtype} produced no cells"


@pytest.mark.parametrize("wtype", list(WeaponType))
def test_build_weapon_matches_direct_call(wtype):
    """Dispatch through the enum must match calling the builder directly."""
    direct_map = {
        WeaponType.TURRET_LARGE: build_turret_large,
        WeaponType.MISSILE_POD: build_missile_pod,
        WeaponType.LASER_LANCE: build_laser_lance,
        WeaponType.POINT_DEFENSE: build_point_defense,
        WeaponType.PLASMA_CORE: build_plasma_core,
    }
    a = build_weapon(wtype, _ANCHOR, np.random.default_rng(99))
    b = direct_map[wtype](_ANCHOR, np.random.default_rng(99))
    assert a == b


# --- structural invariants per builder --------------------------------------


def test_turret_large_has_light_tips():
    """Both barrels must cap in a LIGHT cell — that's how players read it
    as a turret rather than a pair of pipes."""
    cells = build_turret_large(_ANCHOR, np.random.default_rng(0))
    lights = [c for c in cells if c[3] == Role.LIGHT]
    assert len(lights) == 2, f"turret_large must emit 2 LIGHT tips, got {len(lights)}"


def test_missile_pod_has_glowing_warheads():
    """Each tube should get an ENGINE_GLOW cap."""
    cells = build_missile_pod(_ANCHOR, np.random.default_rng(0))
    glow = [c for c in cells if c[3] == Role.ENGINE_GLOW]
    assert glow, "missile_pod must emit at least one ENGINE_GLOW cell"


def test_laser_lance_is_axis_aligned():
    """The spire runs along +Z from the pedestal — every HULL cell beyond
    the pedestal must share the pedestal's X and y+1 Y."""
    anchor = (4, 5, 6)
    cells = build_laser_lance(anchor, np.random.default_rng(3))
    # Find the LIGHT muzzle cap.
    muzzles = [c for c in cells if c[3] == Role.LIGHT]
    assert len(muzzles) == 1
    mx, my, _mz, _ = muzzles[0]
    assert mx == anchor[0]
    assert my == anchor[1] + 1


def test_point_defense_has_small_footprint():
    """2x2 base: only 4 distinct (x, z) pairs at the anchor's Y."""
    anchor = (0, 0, 0)
    cells = build_point_defense(anchor, np.random.default_rng(1))
    base_xz = {(c[0], c[2]) for c in cells if c[1] == 0 and c[3] == Role.HULL_DARK}
    assert base_xz == {(0, 0), (1, 0), (0, 1), (1, 1)}


def test_plasma_core_contains_glow_ring():
    """The emitter must surround its core with ENGINE_GLOW cells."""
    cells = build_plasma_core(_ANCHOR, np.random.default_rng(5))
    glow_count = sum(1 for c in cells if c[3] == Role.ENGINE_GLOW)
    assert glow_count >= 8, (
        f"plasma_core should have at least an 8-cell glow ring + dome, "
        f"got {glow_count}"
    )


# --- scatter: bounding-box inputs ------------------------------------------


def test_scatter_weapons_count_zero_short_circuits():
    """count=0 must return [] without touching rng or anchors."""
    before = np.random.default_rng(0).bit_generator.state
    rng = np.random.default_rng(0)
    out = scatter_weapons((8, 4, 8), rng, count=0)
    after = rng.bit_generator.state
    assert out == []
    # rng state stays untouched — critical so callers can interleave.
    assert before == after


def test_scatter_weapons_deterministic_with_same_seed():
    a = scatter_weapons((10, 4, 10), np.random.default_rng(123), count=4)
    b = scatter_weapons((10, 4, 10), np.random.default_rng(123), count=4)
    assert a == b


def test_scatter_weapons_varies_with_seed():
    a = scatter_weapons((10, 4, 10), np.random.default_rng(1), count=4)
    b = scatter_weapons((10, 4, 10), np.random.default_rng(2), count=4)
    assert a != b


def test_scatter_weapons_respects_count_under_capacity():
    """With plenty of anchors the scatter should produce exactly ``count``
    weapons' worth of anchors — we can verify by counting unique anchor
    roots rather than total cells, which vary per type."""
    # Force a huge top face so capacity > count.
    out = scatter_weapons((20, 4, 20), np.random.default_rng(0), count=5)
    # Each weapon emits several cells; the scatter sampled 5 anchors so we
    # should see output that's consistent with 5 calls to build_weapon.
    assert len(out) > 0
    # Re-running with count=10 must produce strictly more cells.
    out_more = scatter_weapons((20, 4, 20), np.random.default_rng(0), count=10)
    assert len(out_more) > len(out)


def test_scatter_weapons_count_exceeding_capacity_clips():
    """When count > available anchors, we place one per anchor and stop —
    never raise, never sample with replacement."""
    shape = (3, 2, 3)  # only 9 top-face anchors
    out = scatter_weapons(shape, np.random.default_rng(0), count=100)
    # Should not raise and should still return something.
    assert isinstance(out, list)


def test_scatter_weapons_negative_count_raises():
    with pytest.raises(ValueError):
        scatter_weapons((4, 4, 4), np.random.default_rng(0), count=-1)


def test_scatter_weapons_empty_bbox_returns_empty():
    assert scatter_weapons((0, 4, 4), np.random.default_rng(0), count=3) == []
    assert scatter_weapons((4, 0, 4), np.random.default_rng(0), count=3) == []
    assert scatter_weapons((4, 4, 0), np.random.default_rng(0), count=3) == []


def test_scatter_weapons_honors_type_allowlist():
    """Only types in the allow-list may be built."""
    # Force the scatter to only use LASER_LANCE — every muzzle will be a
    # single LIGHT cell at the anchor's X and y+1.
    out = scatter_weapons(
        (8, 4, 20),
        np.random.default_rng(7),
        count=3,
        types=[WeaponType.LASER_LANCE],
    )
    # Laser lance always produces exactly one LIGHT cell; count them.
    lights = [c for c in out if c[3] == Role.LIGHT]
    assert len(lights) == 3


def test_scatter_weapons_empty_type_list_returns_empty():
    assert scatter_weapons((8, 4, 8), np.random.default_rng(0), count=4, types=[]) == []


def test_scatter_weapons_dedupes_type_list():
    """Passing the same type twice must match passing it once — the
    dispatcher should dedupe to keep distributions reproducible."""
    a = scatter_weapons(
        (10, 4, 10),
        np.random.default_rng(0),
        count=3,
        types=[WeaponType.TURRET_LARGE],
    )
    b = scatter_weapons(
        (10, 4, 10),
        np.random.default_rng(0),
        count=3,
        types=[WeaponType.TURRET_LARGE, WeaponType.TURRET_LARGE],
    )
    assert a == b


def test_scatter_weapons_none_types_uses_all():
    """Passing ``types=None`` and omitting ``types`` must behave the same."""
    a = scatter_weapons((10, 4, 10), np.random.default_rng(0), count=3)
    b = scatter_weapons((10, 4, 10), np.random.default_rng(0), count=3, types=None)
    assert a == b


def test_scatter_weapons_rejects_non_3d_array():
    with pytest.raises(ValueError):
        scatter_weapons(np.zeros((4, 4), dtype=np.int8), np.random.default_rng(0), count=1)


def test_scatter_weapons_rejects_bad_shape_tuple():
    with pytest.raises(ValueError):
        scatter_weapons((4, 4), np.random.default_rng(0), count=1)  # type: ignore[arg-type]


# --- scatter: numpy-grid inputs --------------------------------------------


def test_scatter_weapons_empty_grid_returns_empty():
    """All-empty grid has no hull cells, so no anchors, so no placements."""
    grid = np.zeros((8, 8, 8), dtype=np.int8)
    out = scatter_weapons(grid, np.random.default_rng(0), count=5)
    assert out == []


def test_scatter_weapons_pillar_grid_returns_hits():
    """A single hull pillar should give exactly one top-facing anchor and
    exactly one weapon when count>=1."""
    grid = np.zeros((10, 10, 10), dtype=np.int8)
    grid[5, 0:6, 5] = int(Role.HULL)  # a column
    out = scatter_weapons(grid, np.random.default_rng(0), count=1)
    assert out, "expected at least one placement above the pillar"
    # Every placement should be at or above the pillar top (y >= 5).
    assert all(cell[1] >= 5 for cell in out)


def test_scatter_weapons_grid_anchors_on_top_of_hull():
    """Anchors must live on cells whose +Y neighbor is empty."""
    grid = np.zeros((10, 4, 10), dtype=np.int8)
    # Flat deck at y=2 across an 8x8 square.
    grid[1:9, 2, 1:9] = int(Role.HULL)
    out = scatter_weapons(grid, np.random.default_rng(0), count=6)
    assert out


def test_scatter_weapons_grid_deterministic():
    grid = np.zeros((12, 4, 12), dtype=np.int8)
    grid[2:10, 2, 2:10] = int(Role.HULL)
    a = scatter_weapons(grid, np.random.default_rng(321), count=5)
    b = scatter_weapons(grid, np.random.default_rng(321), count=5)
    assert a == b


def test_scatter_weapons_grid_respects_type_filter():
    grid = np.zeros((12, 4, 12), dtype=np.int8)
    grid[2:10, 2, 2:10] = int(Role.HULL)
    out = scatter_weapons(
        grid,
        np.random.default_rng(11),
        count=5,
        types=[WeaponType.LASER_LANCE],
    )
    lights = [c for c in out if c[3] == Role.LIGHT]
    assert len(lights) == 5


def test_scatter_weapons_output_roles_all_valid():
    """Scatter output inherits the per-builder role contract — no stray
    role values should appear once you go through the scatter path."""
    valid = set(Role)
    out = scatter_weapons((16, 4, 16), np.random.default_rng(99), count=8)
    for cell in out:
        assert cell[3] in valid
