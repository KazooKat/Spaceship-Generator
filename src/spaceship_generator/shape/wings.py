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
    # Defensive clamp: ``wing_styles.place_wings``'s docstring promises
    # "All styles are clipped to the grid bounds", but the per-style writers
    # iterate ``for x in range(0, span)`` without a W clamp — passing
    # ``span > W`` raises ``IndexError`` on the unconditional
    # ``grid[x, ...] = Role.WING`` write (audit iter3 agent-10 bug 1). The
    # default scale tops out at ``(W // 5) * 1.5 ≈ 0.3·W << W`` so this is
    # a no-op for in-tree call sites, but the clamp keeps the docstring's
    # clip-safety claim honest in case a future structure style scales
    # span aggressively enough to cross the boundary.
    wing_span = min(wing_span, W)
    wing_thickness = max(1, int(round((H // 10) * thick_s)))
    wing_length = max(4, int(round((L // 3) * length_s)))
    # Guard: on very short ships ``L - wing_length`` may be <= 0, which would
    # collapse ``cz`` to 0 and truncate the wing. Clamp wing_length so the
    # wing still has a valid placement window.
    wing_length = max(2, min(wing_length, L - 1))
    cy = (H - 1) // 2
    # ``rng.integers(low, high)`` is half-open ``[low, high)``. For symmetric
    # jitter around 0 we want ``[-(L // 12), +(L // 12)]`` inclusive. The
    # explicit parens on ``-(L // 12)`` matter for short ships (audit iter3
    # agent-10 bug 5): without them, Python evaluates ``-L // 12 ==
    # floor(-L / 12) == -1`` for ``L`` in ``[8, 11]`` while
    # ``L // 12 + 1 == 1``, collapsing the range to ``{-1, 0}`` and biasing
    # the wing's ``cz`` rearward on the shortest legal ships. With parens,
    # ``-(L // 12) == 0`` for those L, yielding ``rng.integers(0, 1) ==
    # {0}`` — no jitter (correct, since the symmetric half-extent is 0).
    # From ``L >= 12`` onward both forms agree (``L // 12 >= 1``).
    cz = L // 3 + int(rng.integers(-(L // 12), L // 12 + 1))
    cz = max(0, min(L - wing_length, cz))

    y_lo = cy - wing_thickness // 2
    # ``y_hi`` is inclusive: every per-style writer in ``wing_styles.py``
    # iterates with ``range(..., min(H, y_hi + 1))``. Using
    # ``y_lo + wing_thickness`` here would write ``wing_thickness + 1``
    # y-cells per slice; subtracting 1 keeps the slab exactly
    # ``wing_thickness`` tall, matching ``_place_split``'s internal
    # ``t_hi = t_lo + thin - 1`` convention.
    y_hi = y_lo + wing_thickness - 1

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
