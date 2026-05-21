"""Greeble sprinkling and surface-mask computation."""

from __future__ import annotations

import numpy as np

from ..palette import Role
from .core import ShapeParams


def _place_greebles(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Sprinkle 1-voxel bumps on the hull surface.

    Greebles are sampled only from left-half (``x < (W + 1) // 2``) HULL/
    WING surface voxels. Two reasons:

    1. ``generate_shape`` calls ``_enforce_x_symmetry`` after this function,
       which copies the left half onto the right half — so any greeble
       written at ``x`` *strictly past* the centerline would be overwritten
       and effectively wasted budget. The mirror loop is
       ``for x in range(W // 2): grid[W - 1 - x] = grid[x]`` — for even
       ``W`` that touches every index from ``W // 2`` to ``W - 1``, so the
       safe write range is ``nx < W // 2``; for odd ``W`` the center column
       ``x = W // 2`` is NEVER touched by the mirror (audit iter3 agent-10
       bug 3) and is therefore safe to host greebles. The half-bound
       ``(W + 1) // 2`` captures both cases (matches the idiom used by
       ``shape/hull.py``'s ``left_half_x[: (W + 1) // 2] = True``).
    2. Non-HULL/WING surface voxels (cockpit glass, engines, weapons,
       thrusters, etc.) cannot host greebles — the per-iteration role
       filter below would ``continue`` past them anyway. Filtering them
       out of the coord pool *before* computing ``count`` keeps the
       effective density honest instead of silently shrinking it on
       cockpit-heavy ships.
    """
    if params.greeble_density <= 0:
        return

    W, H, L = grid.shape
    # Restrict the candidate pool to (a) the left half of the grid, since
    # the subsequent X-symmetry pass wipes the right half, and (b) HULL/
    # WING voxels, since only those can host a greeble (see docstring).
    # ``(W + 1) // 2`` is the exclusive upper bound on safe-from-mirror
    # columns: for even W this is ``W // 2`` (the centerline is wiped),
    # for odd W this is ``W // 2 + 1`` (the centerline survives — see
    # ``shape/assembly.py::_enforce_x_symmetry``'s ``range(W // 2)``).
    half_bound = (W + 1) // 2
    surface = _surface_mask(grid)
    eligible_role = (grid == Role.HULL) | (grid == Role.WING)
    half_mask = np.zeros((W, 1, 1), dtype=bool)
    half_mask[:half_bound, :, :] = True
    surface = surface & eligible_role & half_mask
    coords = np.argwhere(surface)
    if coords.size == 0:
        return

    count = int(len(coords) * params.greeble_density)
    if count == 0:
        return

    order = rng.permutation(len(coords))
    directions = [(0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]

    for i in range(count):
        x, y, z = coords[order[i]]
        for dx, dy, dz in directions:
            nx, ny, nz = int(x + dx), int(y + dy), int(z + dz)
            if not (0 <= nx < W and 0 <= ny < H and 0 <= nz < L):
                continue
            # Reject writes that would be wiped by the subsequent mirror
            # pass (audit iter3 agent-10 bug 2). The candidate source
            # ``x`` is already constrained to ``x < half_bound`` but the
            # ``(1, 0, 0)`` direction can push the neighbor target past
            # it: e.g. a source at ``x = half_bound - 1`` writes to
            # ``nx = half_bound``, which for even W is the column
            # ``W // 2`` that the mirror loop overwrites from
            # ``x = W // 2 - 1``. Treat that as out-of-bounds so the
            # placement falls through to the next direction instead of
            # being silently overwritten by the mirror pass. The bug is
            # latent under the default symmetric hull (the +X neighbor
            # is already filled and the EMPTY check below rejects the
            # write anyway), but it surfaces the moment a future hull
            # stamper breaks left-right pairing at the centerline.
            if nx >= half_bound:
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
