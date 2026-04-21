"""Tests for :mod:`spaceship_generator.fleet`.

Covers:
* dataclass shapes + defaults
* size tier bounds (pure and mixed)
* determinism (same params → identical list)
* style coherence endpoints (0.0 → varied, 1.0 → single archetype)
* argument validation (count, size_tier, style_coherence)
* palette passthrough
* integration — a planned ship can actually be fed to ``generate()``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from spaceship_generator.engine_styles import EngineStyle
from spaceship_generator.fleet import (
    SIZE_TIERS,
    FleetParams,
    GeneratedShip,
    dims_in_tier,
    generate_fleet,
)
from spaceship_generator.generator import generate
from spaceship_generator.shape import CockpitStyle, ShapeParams
from spaceship_generator.structure_styles import HullStyle
from spaceship_generator.wing_styles import WingStyle

# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_fleet_params_is_dataclass_with_defaults():
    assert is_dataclass(FleetParams)
    p = FleetParams(count=3, palette="sci_fi_industrial")
    assert p.count == 3
    assert p.palette == "sci_fi_industrial"
    assert p.size_tier == "mixed"
    assert p.style_coherence == 0.7
    assert p.seed == 0


def test_generated_ship_is_frozen_dataclass():
    assert is_dataclass(GeneratedShip)
    ship = GeneratedShip(
        seed=1,
        dims=(10, 8, 20),
        hull_style=HullStyle.ARROW,
        engine_style=EngineStyle.SINGLE_CORE,
        wing_style=WingStyle.STRAIGHT,
        greeble_density=0.1,
        palette="sci_fi_industrial",
    )
    # Frozen → assignment raises
    with pytest.raises(FrozenInstanceError):
        ship.seed = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Count semantics
# ---------------------------------------------------------------------------


def test_generate_fleet_returns_exactly_n_ships():
    ships = generate_fleet(
        FleetParams(count=7, palette="sci_fi_industrial", seed=1)
    )
    assert len(ships) == 7


def test_generate_fleet_empty_when_count_is_zero():
    assert generate_fleet(FleetParams(count=0, palette="sci_fi_industrial")) == []


def test_generate_fleet_count_negative_raises():
    with pytest.raises(ValueError):
        generate_fleet(FleetParams(count=-1, palette="sci_fi_industrial"))


# ---------------------------------------------------------------------------
# Palette passthrough
# ---------------------------------------------------------------------------


def test_all_ships_share_input_palette():
    ships = generate_fleet(
        FleetParams(count=6, palette="cyberpunk_neon", seed=5)
    )
    assert all(s.palette == "cyberpunk_neon" for s in ships)


def test_palette_survives_coherence_zero():
    # Even with every stylistic dial random, palette must stay fixed.
    ships = generate_fleet(
        FleetParams(
            count=6,
            palette="stealth_black",
            style_coherence=0.0,
            seed=11,
        )
    )
    assert {s.palette for s in ships} == {"stealth_black"}


# ---------------------------------------------------------------------------
# Size tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", list(SIZE_TIERS))
def test_pure_tier_dims_stay_within_bounds(tier):
    # Large count so the parametric tolerance hits every slot.
    ships = generate_fleet(
        FleetParams(count=12, palette="sci_fi_industrial", size_tier=tier, seed=3)
    )
    assert all(dims_in_tier(s.dims, tier) for s in ships), [s.dims for s in ships]


def test_dims_honour_shape_params_minimums():
    # ShapeParams rejects length<8, width_max<4, height_max<4. Make sure the
    # smallest tier plus worst-case negative jitter never drifts below.
    ships = generate_fleet(
        FleetParams(count=20, palette="sci_fi_industrial", size_tier="small", seed=2025)
    )
    for s in ships:
        w, h, length = s.dims
        assert w >= 4
        assert h >= 4
        assert length >= 8


def test_mixed_tier_can_produce_multiple_tiers():
    # Probabilistic but with a fixed seed and 40 draws "mixed" should hit
    # at least two of the four concrete tiers.
    ships = generate_fleet(
        FleetParams(count=40, palette="sci_fi_industrial", size_tier="mixed", seed=17)
    )
    hits = {tier for tier in SIZE_TIERS if any(dims_in_tier(s.dims, tier) for s in ships)}
    assert len(hits) >= 2


def test_unknown_size_tier_raises():
    with pytest.raises(ValueError):
        generate_fleet(
            FleetParams(count=2, palette="sci_fi_industrial", size_tier="titanic")
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_params_same_seed_gives_identical_list():
    a = generate_fleet(
        FleetParams(count=8, palette="sci_fi_industrial", seed=12345)
    )
    b = generate_fleet(
        FleetParams(count=8, palette="sci_fi_industrial", seed=12345)
    )
    # Compare as tuples of the dataclass tuple form — frozen dataclasses are
    # hashable so this also covers tuple/list equality semantics.
    assert tuple(a) == tuple(b)


def test_different_seed_changes_fleet():
    a = generate_fleet(FleetParams(count=6, palette="sci_fi_industrial", seed=1))
    b = generate_fleet(FleetParams(count=6, palette="sci_fi_industrial", seed=2))
    # At least one ship must differ; with 6 ships the chance of an exact
    # collision under two independent RNG streams is vanishingly small.
    assert tuple(a) != tuple(b)


# ---------------------------------------------------------------------------
# Style coherence
# ---------------------------------------------------------------------------


def test_full_coherence_forces_matched_hull_and_engine():
    ships = generate_fleet(
        FleetParams(
            count=12,
            palette="sci_fi_industrial",
            style_coherence=1.0,
            seed=777,
        )
    )
    hulls = {s.hull_style for s in ships}
    engines = {s.engine_style for s in ships}
    assert len(hulls) == 1
    assert len(engines) == 1


def test_zero_coherence_yields_variety():
    # Seed chosen so the ten draws contain at least two distinct hull styles.
    ships = generate_fleet(
        FleetParams(
            count=10,
            palette="sci_fi_industrial",
            style_coherence=0.0,
            seed=99,
        )
    )
    hulls = {s.hull_style for s in ships}
    assert len(hulls) >= 2


def test_coherence_out_of_range_raises():
    with pytest.raises(ValueError):
        generate_fleet(
            FleetParams(count=1, palette="sci_fi_industrial", style_coherence=1.5)
        )
    with pytest.raises(ValueError):
        generate_fleet(
            FleetParams(count=1, palette="sci_fi_industrial", style_coherence=-0.01)
        )


# ---------------------------------------------------------------------------
# Field sanity
# ---------------------------------------------------------------------------


def test_greeble_density_within_shape_params_bounds():
    # generate()/ShapeParams reject greeble_density outside [0, 0.5].
    ships = generate_fleet(
        FleetParams(count=30, palette="sci_fi_industrial", seed=8)
    )
    for s in ships:
        assert 0.0 <= s.greeble_density <= 0.5


def test_styles_are_enum_members_not_strings():
    ships = generate_fleet(
        FleetParams(count=4, palette="sci_fi_industrial", seed=21)
    )
    for s in ships:
        assert isinstance(s.hull_style, HullStyle)
        assert isinstance(s.engine_style, EngineStyle)
        assert isinstance(s.wing_style, WingStyle)


def test_per_ship_seeds_are_distinct():
    # Collisions are possible but extremely unlikely on a 31-bit range;
    # a 16-ship fleet with one fixed seed should have 16 unique seeds.
    ships = generate_fleet(
        FleetParams(count=16, palette="sci_fi_industrial", seed=4242)
    )
    seeds = [s.seed for s in ships]
    assert len(set(seeds)) == len(seeds)


# ---------------------------------------------------------------------------
# Integration — one planned ship actually builds via generate().
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Cockpit + weapons extensions
# ---------------------------------------------------------------------------


def test_default_weapon_count_preserves_legacy_fleet_byte_for_byte():
    """``weapon_count_per_ship == 0`` (default) must not disturb the RNG
    stream. The pre-existing 7 fields of every :class:`GeneratedShip`
    must match the legacy snapshot exactly, and the new fields must sit
    at their no-op values (``cockpit_style=None``, ``weapon_count=0``).
    """
    # Golden snapshot for ``FleetParams(count=4, palette='sci_fi_industrial',
    # seed=12345)``. Update when HullStyle/EngineStyle/WingStyle enum members
    # change (the new members shift RNG sample indices); regenerate by running
    # the fleet and printing ``ship.hull_style.name`` etc.
    expected = [
        (1761311798, (38, 21, 71), HullStyle.BLOCKY_FREIGHTER, EngineStyle.SINGLE_CORE,
         WingStyle.SWEPT, 0.093, "sci_fi_industrial"),
        (1877275096, (29, 12, 48), HullStyle.HEXAGONAL_LATTICE, EngineStyle.SINGLE_CORE,
         WingStyle.SPLIT, 0.023, "sci_fi_industrial"),
        (2101613385, (29, 12, 41), HullStyle.HEXAGONAL_LATTICE, EngineStyle.SINGLE_CORE,
         WingStyle.DELTA, 0.081, "sci_fi_industrial"),
        (985348261,  (16, 11, 21), HullStyle.HEXAGONAL_LATTICE, EngineStyle.SINGLE_CORE,
         WingStyle.SWEPT, 0.193, "sci_fi_industrial"),
    ]
    ships = generate_fleet(
        FleetParams(count=4, palette="sci_fi_industrial", seed=12345)
    )
    assert len(ships) == len(expected)
    for ship, legacy in zip(ships, expected, strict=True):
        assert (
            ship.seed,
            ship.dims,
            ship.hull_style,
            ship.engine_style,
            ship.wing_style,
            ship.greeble_density,
            ship.palette,
        ) == legacy
        # New fields are no-ops when weapons are off.
        assert ship.cockpit_style is None
        assert ship.weapon_count == 0


def test_weapon_count_propagates_to_every_ship():
    ships = generate_fleet(
        FleetParams(
            count=6,
            palette="sci_fi_industrial",
            seed=1,
            weapon_count_per_ship=3,
        )
    )
    assert all(s.weapon_count == 3 for s in ships)
    # Cockpit selection is active once weapons are on, so each ship must
    # carry a real CockpitStyle rather than None.
    assert all(isinstance(s.cockpit_style, CockpitStyle) for s in ships)


def test_full_cockpit_coherence_forces_matched_cockpit():
    ships = generate_fleet(
        FleetParams(
            count=10,
            palette="sci_fi_industrial",
            seed=777,
            weapon_count_per_ship=2,
            cockpit_coherence=1.0,
        )
    )
    cockpits = {s.cockpit_style for s in ships}
    assert len(cockpits) == 1
    assert isinstance(next(iter(cockpits)), CockpitStyle)


def test_zero_cockpit_coherence_yields_cockpit_variety():
    # Seed chosen so twelve independent cockpit draws contain at least
    # two distinct :class:`CockpitStyle` members.
    ships = generate_fleet(
        FleetParams(
            count=12,
            palette="sci_fi_industrial",
            seed=12345,
            weapon_count_per_ship=1,
            cockpit_coherence=0.0,
        )
    )
    cockpits = {s.cockpit_style for s in ships}
    assert len(cockpits) >= 2


def test_generated_ship_extended_fields_are_frozen():
    """Adding cockpit + weapon fields must not break the frozen guarantee."""
    ship = GeneratedShip(
        seed=1,
        dims=(10, 8, 20),
        hull_style=HullStyle.ARROW,
        engine_style=EngineStyle.SINGLE_CORE,
        wing_style=WingStyle.STRAIGHT,
        greeble_density=0.1,
        palette="sci_fi_industrial",
        cockpit_style=CockpitStyle.BUBBLE,
        weapon_count=2,
    )
    with pytest.raises(FrozenInstanceError):
        ship.cockpit_style = CockpitStyle.POINTED  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ship.weapon_count = 4  # type: ignore[misc]


def test_negative_weapon_count_raises():
    with pytest.raises(ValueError):
        generate_fleet(
            FleetParams(
                count=2,
                palette="sci_fi_industrial",
                weapon_count_per_ship=-1,
            )
        )


def test_first_ship_builds_via_generate(tmp_path):
    ships = generate_fleet(
        FleetParams(count=3, palette="sci_fi_industrial", size_tier="small", seed=314)
    )
    head = ships[0]
    w, h, length = head.dims
    shape_params = ShapeParams(
        width_max=w,
        height_max=h,
        length=length,
        greeble_density=head.greeble_density,
        wing_style=head.wing_style,
    )
    result = generate(
        seed=head.seed,
        palette=head.palette,
        shape_params=shape_params,
        out_dir=tmp_path,
        hull_style=head.hull_style,
        engine_style=head.engine_style,
    )
    # Built file exists and has the expected shape.
    assert result.litematic_path.exists()
    assert result.role_grid.shape == (w, h, length)
    assert result.palette_name == "sci_fi_industrial"
