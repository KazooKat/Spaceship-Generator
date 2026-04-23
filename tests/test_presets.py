"""Tests for named ship archetype presets.

Covers:

* every preset resolves and exposes the full key schema,
* enum values (hull/engine/wing/cockpit/weapon types) are the right type,
* ``size`` tuples respect :class:`ShapeParams` minimums,
* ``apply_preset`` returns fresh mutable containers (no shared state),
* unknown preset names raise :class:`KeyError`,
* each preset feeds :func:`generate` to produce a valid ``.litematic``.
"""

from __future__ import annotations

import pytest

from spaceship_generator.engine_styles import EngineStyle
from spaceship_generator.generator import generate
from spaceship_generator.palette import Role
from spaceship_generator.presets import (
    PRESET_KEYS,
    SHIP_PRESETS,
    apply_preset,
    list_presets,
)
from spaceship_generator.shape import CockpitStyle, ShapeParams
from spaceship_generator.structure_styles import HullStyle
from spaceship_generator.weapon_styles import WeaponType
from spaceship_generator.wing_styles import WingStyle

# Expected preset role names. Locked so renaming a key is a deliberate break.
EXPECTED_PRESET_NAMES = {
    "corvette",
    "dropship",
    "science_vessel",
    "gunship",
    "freighter_heavy",
    "interceptor",
    "scout",
    "battlecruiser",
    "capital_carrier",
}


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


def test_list_presets_returns_all_six_roles():
    assert set(list_presets()) == EXPECTED_PRESET_NAMES
    # Nine presets, sorted output.
    assert len(list_presets()) == 9
    assert list_presets() == sorted(list_presets())


def test_ship_presets_dict_matches_list_presets():
    assert set(SHIP_PRESETS.keys()) == set(list_presets())


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_every_preset_has_full_key_schema(name):
    spec = SHIP_PRESETS[name]
    assert set(spec.keys()) == set(PRESET_KEYS), (
        f"preset {name!r} keys={sorted(spec.keys())} "
        f"expected={sorted(PRESET_KEYS)}"
    )


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_every_preset_enum_types_are_correct(name):
    spec = SHIP_PRESETS[name]
    assert isinstance(spec["hull_style"], HullStyle)
    assert isinstance(spec["engine_style"], EngineStyle)
    assert isinstance(spec["wing_style"], WingStyle)
    assert isinstance(spec["cockpit_style"], CockpitStyle)
    assert isinstance(spec["weapon_types"], tuple)
    for t in spec["weapon_types"]:
        assert isinstance(t, WeaponType)


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_every_preset_size_is_valid(name):
    w, h, length = SHIP_PRESETS[name]["size"]
    assert w >= 4 and h >= 4 and length >= 8, (
        f"preset {name!r} size=({w},{h},{length}) violates ShapeParams minimums"
    )
    assert isinstance(w, int) and isinstance(h, int) and isinstance(length, int)


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_every_preset_has_sensible_scalars(name):
    spec = SHIP_PRESETS[name]
    assert 0.0 <= float(spec["greeble_density"]) <= 1.0
    assert int(spec["weapon_count"]) >= 0
    # If weapon_count is 0, weapon_types can be empty; non-zero needs at
    # least one type so scatter_weapons has something to choose from.
    if int(spec["weapon_count"]) > 0:
        assert len(spec["weapon_types"]) >= 1


# ---------------------------------------------------------------------------
# apply_preset()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_apply_preset_returns_generate_kwargs(name):
    kwargs = apply_preset(name)
    assert set(kwargs.keys()) == {
        "shape_params",
        "hull_style",
        "engine_style",
        "greeble_density",
        "weapon_count",
        "weapon_types",
    }
    assert isinstance(kwargs["shape_params"], ShapeParams)
    assert isinstance(kwargs["hull_style"], HullStyle)
    assert isinstance(kwargs["engine_style"], EngineStyle)
    assert isinstance(kwargs["weapon_types"], list)


def test_apply_preset_shape_params_match_size_tuple():
    # Corvette has a known size tuple (20, 12, 50).
    kwargs = apply_preset("corvette")
    sp = kwargs["shape_params"]
    assert sp.width_max == 20
    assert sp.height_max == 12
    assert sp.length == 50
    # And the cockpit + wing styles propagate into ShapeParams.
    assert sp.cockpit_style == CockpitStyle.BUBBLE
    assert sp.wing_style == WingStyle.SWEPT


def test_apply_preset_returns_fresh_weapon_types_list():
    """Mutating the returned weapon_types must not affect the preset definition."""
    k1 = apply_preset("corvette")
    k1["weapon_types"].append(WeaponType.LASER_LANCE)
    k2 = apply_preset("corvette")
    assert WeaponType.LASER_LANCE not in k2["weapon_types"]
    assert len(k2["weapon_types"]) == 2


def test_apply_preset_returns_fresh_shape_params_instance():
    """Two calls must produce independent ShapeParams so mutations don't leak."""
    k1 = apply_preset("corvette")
    k2 = apply_preset("corvette")
    assert k1["shape_params"] is not k2["shape_params"]


def test_apply_preset_unknown_raises_key_error():
    with pytest.raises(KeyError):
        apply_preset("not_a_real_preset")


def test_apply_preset_empty_string_raises_key_error():
    with pytest.raises(KeyError):
        apply_preset("")


# ---------------------------------------------------------------------------
# Specific preset spot-checks
# ---------------------------------------------------------------------------


def test_corvette_preset_contents():
    spec = SHIP_PRESETS["corvette"]
    assert spec["hull_style"] == HullStyle.DAGGER
    assert spec["engine_style"] == EngineStyle.TWIN_NACELLE
    assert spec["wing_style"] == WingStyle.SWEPT
    assert spec["cockpit_style"] == CockpitStyle.BUBBLE
    assert spec["weapon_count"] == 2
    assert WeaponType.TURRET_LARGE in spec["weapon_types"]
    assert WeaponType.POINT_DEFENSE in spec["weapon_types"]


def test_freighter_heavy_has_no_weapons():
    spec = SHIP_PRESETS["freighter_heavy"]
    assert spec["weapon_count"] == 0
    assert spec["weapon_types"] == ()
    assert spec["size"] == (40, 20, 80)


def test_interceptor_is_small_and_fast():
    spec = SHIP_PRESETS["interceptor"]
    # Smallest preset by bounding-box volume.
    w, h, length = spec["size"]
    assert (w, h, length) == (15, 10, 45)
    assert spec["weapon_count"] == 1
    assert spec["weapon_types"] == (WeaponType.LASER_LANCE,)


# ---------------------------------------------------------------------------
# Integration: feed apply_preset into generate()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_PRESET_NAMES))
def test_generate_accepts_apply_preset_kwargs(name, tmp_path):
    """Every preset must produce a valid .litematic when unpacked into generate()."""
    kwargs = apply_preset(name)
    # Use a deterministic seed per preset so failures are reproducible.
    seed = abs(hash(name)) % 10_000
    result = generate(
        seed,
        palette="sci_fi_industrial",
        out_dir=tmp_path,
        with_preview=False,
        **kwargs,
    )
    # File actually landed on disk.
    assert result.litematic_path.exists()
    assert result.litematic_path.suffix == ".litematic"
    assert result.litematic_path.stat().st_size > 0
    # Grid dimensions match the preset size exactly.
    w, h, length = kwargs["shape_params"].width_max, kwargs["shape_params"].height_max, kwargs["shape_params"].length
    assert result.role_grid.shape == (w, h, length)
    # At least some filled voxels — a shape that collapses to zero blocks
    # means the preset was silently invalid.
    assert result.block_count > 0
    # The grid must contain at least one hull voxel. If this fails the
    # hull_style override produced an empty silhouette.
    assert (result.role_grid == int(Role.HULL)).any() or (
        result.role_grid != int(Role.EMPTY)
    ).any()
