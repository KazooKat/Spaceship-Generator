"""Wing placement — rooted into the hull, spanning to the grid edge.

The planform outline still comes from :mod:`spaceship_generator.wing_styles`
(straight / swept / delta / tapered / gull / split). v2 changes the box the
outline is drawn in: the wing runs from the grid edge (``x = 0``) all the
way *into* the hull volume, so the root is embedded rather than floating.
The outline is stamped onto a scratch grid and merged into EMPTY cells only,
so hull voxels are never overwritten — the embedded root simply guarantees
face contact with the hull surface at every z-slice of the chord.
"""

from __future__ import annotations

import numpy as np

from ..palette import Role
from ..wing_styles import place_wings as _place_wing_cells
from .blueprint import ShipPlan
from .core import ShapeParams


def _place_wings(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    plan: ShipPlan,
) -> None:
    """Stamp the left wing per the plan; the mirror pass makes the right.

    ``rng`` is unused (variation lives in the plan) but kept for signature
    symmetry with the other placers.
    """
    if not plan.wing.present:
        return
    W, H, L = grid.shape
    wing = plan.wing
    cx = (W - 1) / 2.0

    # Hull half-width at the wing's chord midpoint decides how deep the
    # wing box reaches: 2 voxels past the hull surface (embedded root).
    mid_z = min(L - 1, wing.root_z + wing.root_chord // 2)
    half_w, _, _, _ = plan.hull_half_at(mid_z)
    x_surface = int(np.floor(cx - half_w))
    total_span = max(2, x_surface + 3)  # columns [0, total_span) — 2 inside hull

    thickness = wing.thickness
    y_lo = max(0, wing.y_anchor - thickness // 2)
    y_hi = min(H - 1, y_lo + thickness - 1)

    scratch = np.zeros_like(grid)
    _place_wing_cells(
        scratch,
        wing.style,
        span=total_span,
        thickness=thickness,
        length=wing.root_chord,
        cy=wing.y_anchor,
        cz=wing.root_z,
        y_lo=y_lo,
        y_hi=y_hi,
    )
    merge = (scratch == Role.WING) & (grid == Role.EMPTY)
    grid[merge] = Role.WING
