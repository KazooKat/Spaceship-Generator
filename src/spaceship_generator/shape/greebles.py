"""Greeble sprinkling and surface-mask computation."""

from __future__ import annotations

import numpy as np

from ..palette import Role
from .core import ShapeParams


def _place_greebles(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Sprinkle 1-voxel bumps on the hull surface."""
    if params.greeble_density <= 0:
        return

    surface = _surface_mask(grid)
    coords = np.argwhere(surface)
    if coords.size == 0:
        return

    count = int(len(coords) * params.greeble_density)
    if count == 0:
        return

    order = rng.permutation(len(coords))
    W, H, L = grid.shape
    directions = [(0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]

    for i in range(count):
        x, y, z = coords[order[i]]
        # Don't drop greebles on engines or cockpit glass.
        if grid[x, y, z] not in (Role.HULL, Role.WING):
            continue
        for dx, dy, dz in directions:
            nx, ny, nz = int(x + dx), int(y + dy), int(z + dz)
            if not (0 <= nx < W and 0 <= ny < H and 0 <= nz < L):
                continue
            if grid[nx, ny, nz] == Role.EMPTY:
                grid[nx, ny, nz] = Role.GREEBLE
                break


def _surface_mask(grid: np.ndarray) -> np.ndarray:
    """Boolean array: True where voxel is filled and has at least one empty neighbor."""
    filled = grid != Role.EMPTY
    W, H, L = grid.shape
    surface = np.zeros_like(filled)
    for dx, dy, dz in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
        # Treat out-of-bounds neighbors as EMPTY so ship's outer shell is surface.
        shifted = np.zeros_like(filled, dtype=bool)
        xs = slice(max(0, -dx), W - max(0, dx))
        ys = slice(max(0, -dy), H - max(0, dy))
        zs = slice(max(0, -dz), L - max(0, dz))
        src_xs = slice(xs.start + dx, xs.stop + dx)
        src_ys = slice(ys.start + dy, ys.stop + dy)
        src_zs = slice(zs.start + dz, zs.stop + dz)
        shifted[xs, ys, zs] = filled[src_xs, src_ys, src_zs]
        surface |= filled & ~shifted
    return surface
