"""Named ship archetype presets.

A :data:`preset <SHIP_PRESETS>` bundles together hull, engine, wing, cockpit,
greeble, and weapon parameters under a single role name (``"corvette"``,
``"dropship"``, ...). Callers can use :func:`apply_preset` to turn a role
name into a kwargs dict suitable for unpacking into
:func:`spaceship_generator.generator.generate`:

    >>> from spaceship_generator.generator import generate
    >>> from spaceship_generator.presets import apply_preset
    >>> kwargs = apply_preset("corvette")
    >>> result = generate(seed=1337, **kwargs)

Presets are a Python-library-level convenience. CLI and web integration is
deliberately deferred to a future wave — this module only supplies the
parameter bundles.

Each preset exposes the following keys (mirrors the subset of
:func:`generate` kwargs the presets control):

* ``shape_params`` — :class:`~spaceship_generator.shape.ShapeParams` with
  ``cockpit_style``, ``wing_style``, and ``(width_max, height_max,
  length)`` sized from the preset's ``size`` tuple.
* ``hull_style`` — :class:`~spaceship_generator.structure_styles.HullStyle`.
* ``engine_style`` — :class:`~spaceship_generator.engine_styles.EngineStyle`.
* ``greeble_density`` — top-level :func:`generate` kwarg driving
  :func:`~spaceship_generator.greeble_styles.scatter_greebles`.
* ``weapon_count`` — non-negative int.
* ``weapon_types`` — tuple of :class:`~spaceship_generator.weapon_styles.WeaponType`
  members (possibly empty). ``apply_preset`` returns a fresh ``list`` so
  the caller cannot mutate the preset's underlying tuple.

Adding a new preset is a single-step change: add another entry to
:data:`SHIP_PRESETS`. Tests pin the schema and enum membership so typos
surface immediately.
"""

from __future__ import annotations

from typing import Any

from .engine_styles import EngineStyle
from .shape import CockpitStyle, ShapeParams
from .structure_styles import HullStyle
from .weapon_styles import WeaponType
from .wing_styles import WingStyle

# Keys every preset entry carries. Kept as a module-level tuple so tests
# can assert the schema without duplicating the list.
PRESET_KEYS: tuple[str, ...] = (
    "hull_style",
    "engine_style",
    "wing_style",
    "cockpit_style",
    "greeble_density",
    "weapon_count",
    "weapon_types",
    "size",
)


# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------
#
# ``size`` is ``(width, height, length)`` and maps directly onto
# :class:`ShapeParams` (``width_max``, ``height_max``, ``length``).
#
# ``weapon_types`` is stored as a tuple so the underlying preset dict is
# effectively immutable; :func:`apply_preset` materializes a fresh ``list``
# for callers.
SHIP_PRESETS: dict[str, dict[str, Any]] = {
    "corvette": {
        "hull_style": HullStyle.DAGGER,
        "engine_style": EngineStyle.TWIN_NACELLE,
        "wing_style": WingStyle.SWEPT,
        "cockpit_style": CockpitStyle.BUBBLE,
        "greeble_density": 0.1,
        "weapon_count": 2,
        "weapon_types": (WeaponType.TURRET_LARGE, WeaponType.POINT_DEFENSE),
        "size": (20, 12, 50),
    },
    "dropship": {
        "hull_style": HullStyle.BLOCKY_FREIGHTER,
        "engine_style": EngineStyle.QUAD_CLUSTER,
        "wing_style": WingStyle.TAPERED,
        "cockpit_style": CockpitStyle.INTEGRATED,
        "greeble_density": 0.05,
        "weapon_count": 0,
        "weapon_types": (),
        "size": (25, 15, 35),
    },
    "science_vessel": {
        "hull_style": HullStyle.SAUCER,
        "engine_style": EngineStyle.RING,
        "wing_style": WingStyle.GULL,
        "cockpit_style": CockpitStyle.CANOPY_DOME,
        "greeble_density": 0.08,
        "weapon_count": 1,
        "weapon_types": (WeaponType.PLASMA_CORE,),
        "size": (30, 15, 50),
    },
    "gunship": {
        "hull_style": HullStyle.ARROW,
        "engine_style": EngineStyle.ION_ARRAY,
        "wing_style": WingStyle.DELTA,
        "cockpit_style": CockpitStyle.OFFSET_TURRET,
        "greeble_density": 0.05,
        "weapon_count": 4,
        "weapon_types": (WeaponType.MISSILE_POD, WeaponType.TURRET_LARGE),
        "size": (22, 13, 55),
    },
    "freighter_heavy": {
        "hull_style": HullStyle.WHALE,
        "engine_style": EngineStyle.SINGLE_CORE,
        "wing_style": WingStyle.STRAIGHT,
        "cockpit_style": CockpitStyle.WRAP_BRIDGE,
        "greeble_density": 0.03,
        "weapon_count": 0,
        "weapon_types": (),
        "size": (40, 20, 80),
    },
    "interceptor": {
        "hull_style": HullStyle.DAGGER,
        "engine_style": EngineStyle.ION_ARRAY,
        "wing_style": WingStyle.SPLIT,
        "cockpit_style": CockpitStyle.POINTED,
        "greeble_density": 0.02,
        "weapon_count": 1,
        "weapon_types": (WeaponType.LASER_LANCE,),
        "size": (15, 10, 45),
    },
    "scout": {
        "hull_style": HullStyle.SLEEK_RACING,
        "engine_style": EngineStyle.ION_ARRAY,
        "wing_style": WingStyle.SWEPT,
        "cockpit_style": CockpitStyle.BUBBLE,
        "greeble_density": 0.05,
        "weapon_count": 1,
        "weapon_types": (WeaponType.POINT_DEFENSE,),
        "size": (8, 5, 14),
    },
    "battlecruiser": {
        "hull_style": HullStyle.ARROW,
        "engine_style": EngineStyle.QUAD_CLUSTER,
        "wing_style": WingStyle.DELTA,
        "cockpit_style": CockpitStyle.WRAP_BRIDGE,
        "greeble_density": 0.2,
        "weapon_count": 6,
        "weapon_types": (WeaponType.TURRET_LARGE, WeaponType.MISSILE_POD, WeaponType.POINT_DEFENSE),
        "size": (22, 12, 40),
    },
    "capital_carrier": {
        "hull_style": HullStyle.MODULAR_BLOCK,
        "engine_style": EngineStyle.RING,
        "wing_style": WingStyle.STRAIGHT,
        "cockpit_style": CockpitStyle.OFFSET_TURRET,
        "greeble_density": 0.15,
        "weapon_count": 8,
        "weapon_types": (WeaponType.TURRET_LARGE, WeaponType.MISSILE_POD, WeaponType.POINT_DEFENSE),
        "size": (30, 16, 50),
    },
}


def list_presets() -> list[str]:
    """Return the sorted list of preset role names.

    Sorting stabilizes the CLI listing and any future ``--help`` text.
    """
    return sorted(SHIP_PRESETS.keys())


def apply_preset(name: str) -> dict[str, Any]:
    """Return a kwargs dict for :func:`generate` built from preset ``name``.

    The returned dict is safe to unpack as a subset of the ``generate``
    keyword arguments::

        generate(seed=42, **apply_preset("corvette"))

    Every call constructs a **fresh** :class:`ShapeParams` instance and
    a fresh ``weapon_types`` list, so the caller can mutate the result
    without corrupting the underlying preset definition.

    Parameters
    ----------
    name:
        Role name. Must be a key of :data:`SHIP_PRESETS`.

    Returns
    -------
    dict
        Kwargs keyed by ``shape_params``, ``hull_style``, ``engine_style``,
        ``greeble_density``, ``weapon_count``, ``weapon_types``.

    Raises
    ------
    KeyError
        If ``name`` is not a known preset.
    """
    if name not in SHIP_PRESETS:
        raise KeyError(
            f"unknown preset {name!r}; known presets: {list_presets()}"
        )

    spec = SHIP_PRESETS[name]
    width, height, length = spec["size"]

    shape_params = ShapeParams(
        length=length,
        width_max=width,
        height_max=height,
        cockpit_style=spec["cockpit_style"],
        wing_style=spec["wing_style"],
    )

    return {
        "shape_params": shape_params,
        "hull_style": spec["hull_style"],
        "engine_style": spec["engine_style"],
        "greeble_density": float(spec["greeble_density"]),
        "weapon_count": int(spec["weapon_count"]),
        # Fresh list per call so callers can mutate without polluting SHIP_PRESETS.
        "weapon_types": list(spec["weapon_types"]),
    }


__all__ = [
    "PRESET_KEYS",
    "SHIP_PRESETS",
    "apply_preset",
    "list_presets",
]
