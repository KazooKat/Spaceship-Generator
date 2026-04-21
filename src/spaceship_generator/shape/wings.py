"""Wing slab placement — mirrored on X via the final symmetry pass."""

from __future__ import annotations

import numpy as np

from ..structure_styles import wing_size_scale
from ..wing_styles import place_wings as _place_wing_cells
from .core import ShapeParams


def _place_wings(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Flat slabs protruding from the hull on the X axis. Mirrored.

    Wing span/thickness/length are scaled per
    :attr:`ShapeParams.structure_style`; ``FRIGATE`` uses the original
    values. The actual cell-writing pattern is chosen by
    :attr:`ShapeParams.wing_style` and implemented in
    :mod:`spaceship_generator.wing_styles` — this function is just the
    placement-box math.
    """
    W, H, L = grid.shape
    span_s, thick_s, length_s = wing_size_scale(params.structure_style)
    wing_span = max(2, int(round((W // 5) * span_s)))
    wing_thickness = max(1, int(round((H // 10) * thick_s)))
    wing_length = max(4, int(round((L // 3) * length_s)))
    # Guard: on very short ships ``L - wing_length`` may be <= 0, which would
    # collapse ``cz`` to 0 and truncate the wing. Clamp wing_length so the
    # wing still has a valid placement window.
    wing_length = max(2, min(wing_length, L - 1))
    cy = (H - 1) // 2
    cz = L // 3 + int(rng.integers(-L // 12, L // 12 + 1))
    cz = max(0, min(L - wing_length, cz))

    y_lo = cy - wing_thickness // 2
    y_hi = y_lo + wing_thickness

    # Left wing — right side is produced by the final mirror pass.
    _place_wing_cells(
        grid,
        params.wing_style,
        span=wing_span,
        thickness=wing_thickness,
        length=wing_length,
        cy=cy,
        cz=cz,
        y_lo=y_lo,
        y_hi=y_hi,
    )
