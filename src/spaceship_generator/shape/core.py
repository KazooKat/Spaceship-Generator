"""Core data types and the top-level ``generate_shape`` orchestrator.

The grid is indexed ``grid[x, y, z]`` where:

* ``x`` = width (mirror axis — ship is bilaterally symmetric across ``x = W/2``)
* ``y`` = height (Minecraft Y-up)
* ``z`` = length — ``z = 0`` is the rear (engine end), ``z = L - 1`` is the nose

Values are integer :class:`~spaceship_generator.palette.Role` codes. Only
coarse roles are set here (``HULL``, ``COCKPIT_GLASS``, ``ENGINE``, ``WING``,
``GREEBLE``). Fine detailing (windows, accent stripes, engine glow cores,
running lights) is the job of :mod:`spaceship_generator.texture`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from ..structure_styles import HullStyle, StructureStyle, apply_hull_style, wing_prob_override
from ..wing_styles import WingStyle


class CockpitStyle(StrEnum):
    BUBBLE = "bubble"
    POINTED = "pointed"
    INTEGRATED = "integrated"
    CANOPY_DOME = "canopy_dome"
    WRAP_BRIDGE = "wrap_bridge"
    OFFSET_TURRET = "offset_turret"


@dataclass
class ShapeParams:
    """User-tunable parameters for ship shape."""

    length: int = 40          # Z dimension (nose-to-tail)
    width_max: int = 20       # X dimension
    height_max: int = 12      # Y dimension
    engine_count: int = 2
    wing_prob: float = 0.75
    greeble_density: float = 0.05
    cockpit_style: CockpitStyle = CockpitStyle.BUBBLE
    structure_style: StructureStyle = StructureStyle.FRIGATE
    # Wing silhouette archetype. STRAIGHT reproduces legacy behavior
    # byte-for-byte; new styles (swept, delta, tapered, gull, split)
    # change only the cells written by ``_place_wings``.
    wing_style: WingStyle = WingStyle.STRAIGHT
    # Procedural-noise hull distortion amplitude in ``[0.0, 1.0]``.
    # ``0.0`` (default) skips the noise post-pass entirely so the resulting
    # voxel grid is byte-identical to legacy output. Higher values displace
    # hull-membrane cells via a deterministic 3D hash-noise field seeded
    # from the same ``seed`` that drives the rest of the pipeline; the
    # displacement is clamped to keep the silhouette legible (see
    # :func:`spaceship_generator.shape.hull._apply_hull_noise`).
    hull_noise: float = 0.0

    def __post_init__(self) -> None:
        if self.length < 8:
            raise ValueError("length must be >= 8")
        if self.width_max < 4:
            raise ValueError("width_max must be >= 4")
        if self.height_max < 4:
            raise ValueError("height_max must be >= 4")
        if self.engine_count < 0 or self.engine_count > 6:
            raise ValueError("engine_count must be in [0, 6]")
        if not 0.0 <= self.wing_prob <= 1.0:
            raise ValueError("wing_prob must be in [0, 1]")
        if not 0.0 <= self.greeble_density <= 0.5:
            raise ValueError("greeble_density must be in [0, 0.5]")
        if not 0.0 <= self.hull_noise <= 1.0:
            raise ValueError("hull_noise must be in [0, 1]")
        # Validate structure_style: accept enum or a string value; raise
        # ValueError on anything else (the web layer relies on this).
        if isinstance(self.structure_style, str) and not isinstance(
            self.structure_style, StructureStyle
        ):
            try:
                self.structure_style = StructureStyle(self.structure_style)
            except ValueError as exc:  # pragma: no cover - re-raised
                raise ValueError(
                    f"structure_style must be one of "
                    f"{[s.value for s in StructureStyle]}; got "
                    f"{self.structure_style!r}"
                ) from exc
        elif not isinstance(self.structure_style, StructureStyle):
            raise ValueError(
                f"structure_style must be a StructureStyle; got "
                f"{type(self.structure_style).__name__}"
            )

        # Validate wing_style — same shape as structure_style above.
        if isinstance(self.wing_style, str) and not isinstance(
            self.wing_style, WingStyle
        ):
            try:
                self.wing_style = WingStyle(self.wing_style)
            except ValueError as exc:  # pragma: no cover - re-raised
                raise ValueError(
                    f"wing_style must be one of "
                    f"{[s.value for s in WingStyle]}; got "
                    f"{self.wing_style!r}"
                ) from exc
        elif not isinstance(self.wing_style, WingStyle):
            raise ValueError(
                f"wing_style must be a WingStyle; got "
                f"{type(self.wing_style).__name__}"
            )


def _body_profile(t: float) -> float:
    """Taper profile along ship length.

    ``t = 0`` is the rear, ``t = 1`` is the nose. Peaks a little forward of
    the middle so the nose tapers more than the tail. This is the legacy
    (``FRIGATE``) profile; per-style profiles live in
    :mod:`spaceship_generator.structure_styles`.
    """
    peak = 0.55
    sigma = 0.32
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    return max(0.0, min(1.0, f))


def generate_shape(
    seed: int,
    params: ShapeParams | None = None,
    *,
    hull_style: HullStyle | None = None,
    hull_style_front: HullStyle | None = None,
    hull_style_rear: HullStyle | None = None,
    hull_blend_midband: float = 0.25,
) -> np.ndarray:
    """Return a ``(W, H, L)`` int8 array of :class:`Role` codes.

    Deterministic given ``seed``, ``params``, ``hull_style``, and the
    ``hull_style_front``/``hull_style_rear``/``hull_blend_midband`` blend
    parameters.

    Parameters
    ----------
    hull_style:
        Optional :class:`HullStyle` archetype. When set, the base hull is
        stamped by :func:`apply_hull_style` *instead of* the default
        :func:`_place_hull`. All downstream parts (cockpit, engines, wings,
        greebles) are then placed on top of that hull. ``None`` (default)
        preserves the original behavior byte-for-byte.
    hull_style_front, hull_style_rear:
        Optional pair of :class:`HullStyle` archetypes for blending two
        silhouettes along Z. **Both** must be provided for the blend to
        engage; if either is ``None`` the legacy hull selection (driven by
        ``hull_style`` / :attr:`ShapeParams.structure_style`) is used so
        existing call-sites are unchanged. When both are set, the blend
        takes precedence over ``hull_style``. ``rear`` shapes the engine
        end (``z = 0``); ``front`` shapes the nose (``z = L - 1``); the
        crossover is a cosine ramp centred at ``z = L/2``.
    hull_blend_midband:
        Fraction of the ship's length over which the front/rear crossover
        is centred. Default ``0.25`` — a 25% midband. Ignored unless both
        ``hull_style_front`` and ``hull_style_rear`` are set.
    """
    # Local imports so each stage module can safely import from ``core``
    # without creating an import cycle.
    from .assembly import (
        _connect_floaters,
        _enforce_x_symmetry,
    )
    from .cockpit import _place_cockpit
    from .engines import _place_engines
    from .greebles import _place_greebles
    from .hull import _apply_hull_noise, _place_hull, _place_hull_blend
    from .wings import _place_wings

    params = params or ShapeParams()
    rng = np.random.default_rng(seed)
    W, H, L = params.width_max, params.height_max, params.length
    grid = np.zeros((W, H, L), dtype=np.int8)

    if hull_style_front is not None and hull_style_rear is not None:
        # Z-axis blend wins over both legacy hull and single hull_style so
        # users opting in to the blend get exactly what they asked for.
        _place_hull_blend(
            grid,
            rng,
            hull_style_front,
            hull_style_rear,
            midband=hull_blend_midband,
        )
    elif hull_style is None:
        _place_hull(grid, rng, params)
    else:
        apply_hull_style(grid, hull_style)
    # Optional procedural-noise post-pass on the hull membrane. Runs before
    # cockpit/engines/wings/greebles so those parts always sit on top of the
    # final perturbed hull silhouette. Skipped entirely when ``hull_noise``
    # is zero so the legacy pipeline stays byte-identical.
    if params.hull_noise > 0.0:
        _apply_hull_noise(grid, rng, params)
    _place_cockpit(grid, rng, params)
    _place_engines(grid, rng, params)
    effective_wing_prob = wing_prob_override(params.structure_style, params.wing_prob)
    if rng.random() < effective_wing_prob:
        _place_wings(grid, rng, params)
    _place_greebles(grid, rng, params)
    _enforce_x_symmetry(grid)
    _connect_floaters(grid)
    _enforce_x_symmetry(grid)

    return grid
