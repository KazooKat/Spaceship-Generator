"""Hull placement — tapered ellipsoid-of-revolution along Z."""

from __future__ import annotations

import numpy as np

from ..palette import Role
from ..structure_styles import hull_rx_ry_scale, profile_fn
from .core import ShapeParams


def _place_hull(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Fill a tapered ellipsoid-of-revolution along Z with HULL voxels.

    The taper profile, and the X/Y radius scaling, are picked per
    :attr:`ShapeParams.structure_style`. ``FRIGATE`` preserves the original
    behavior exactly.
    """
    W, H, L = grid.shape
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0

    # Slight random thickness variation per axis so not every ship is identical.
    thickness = 0.9 + rng.random() * 0.1

    # Style dispatchers: profile function + rx/ry scale multipliers.
    profile_f = profile_fn(params.structure_style)
    rx_scale, ry_scale = hull_rx_ry_scale(params.structure_style)

    for z in range(L):
        t = z / max(L - 1, 1)          # 0 at rear, 1 at nose
        profile = profile_f(t)         # [0..1] bell-ish
        rx = max(0.5, (W * 0.5 - 0.5) * profile * thickness * rx_scale)
        ry = max(
            0.5, (H * 0.5 - 0.5) * profile * thickness * 0.7 * ry_scale
        )  # flatter than wide

        for x in range(W):
            for y in range(H):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.HULL
