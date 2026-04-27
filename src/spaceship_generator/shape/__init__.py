"""Parts-based procedural ship shape generation.

Pipeline:

    hull  ->  cockpit  ->  engines  ->  (maybe) wings  ->  greebles  ->  mirror on X

The grid is indexed ``grid[x, y, z]`` where:

* ``x`` = width (mirror axis — ship is bilaterally symmetric across ``x = W/2``)
* ``y`` = height (Minecraft Y-up)
* ``z`` = length — ``z = 0`` is the rear (engine end), ``z = L - 1`` is the nose

Values are integer :class:`Role` codes. Only coarse roles are set here
(``HULL``, ``COCKPIT_GLASS``, ``ENGINE``, ``WING``, ``GREEBLE``). Fine detailing
(windows, accent stripes, engine glow cores, running lights) is the job of
:mod:`spaceship_generator.texture`.

This package is the split form of the former ``shape.py`` module; the public
API is preserved here so ``from spaceship_generator.shape import ...`` keeps
working for every existing call site and test.
"""

from __future__ import annotations

# Re-export the public API. StructureStyle is re-exported from the
# ``structure_styles`` module because tests and other callers import it from
# ``spaceship_generator.shape``.
from ..structure_styles import StructureStyle
from .assembly import (
    _connect_floaters,
    _draw_line_hull,
    _enforce_x_symmetry,
    _label_components,
)
from .cockpit import (
    _place_cockpit,
    _place_cockpit_bubble,
    _place_cockpit_integrated,
    _place_cockpit_pointed,
)
from .core import CockpitStyle, ShapeParams, _body_profile, generate_shape
from .engines import _engine_x_positions, _place_engines
from .greebles import _place_greebles, _surface_mask
from .hull import _apply_hull_noise, _place_hull
from .wings import _place_wings

__all__ = [
    # Public API.
    "CockpitStyle",
    "ShapeParams",
    "StructureStyle",
    "generate_shape",
    # Internal helpers consumed by other modules / tests.
    "_apply_hull_noise",
    "_body_profile",
    "_connect_floaters",
    "_draw_line_hull",
    "_engine_x_positions",
    "_enforce_x_symmetry",
    "_label_components",
    "_place_cockpit",
    "_place_cockpit_bubble",
    "_place_cockpit_integrated",
    "_place_cockpit_pointed",
    "_place_engines",
    "_place_greebles",
    "_place_hull",
    "_place_wings",
    "_surface_mask",
]
