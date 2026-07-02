"""Greeble placement — clustered machinery patches, plus surface-mask helper.

v2 replaces the old single-voxel sprinkle with rectangular *patches* stamped
on flat deck areas of the rear/mid hull. Each patch carries one motif:

* ``panel_outline`` — a raised rectangular border ring (hatch / access panel)
* ``vent_row``      — alternating raised rows (heat-sink louvres)
* ``pipe_run``      — a raised centerline pipe with end couplings
* ``antenna_cluster`` — 2–4-voxel masts at the patch corners (deck sensors)

Every motif writes contiguous GREEBLE cells into EMPTY space directly above
flat HULL, so no greeble voxel is ever isolated or floating.
``greeble_density`` scales the number of patch attempts.
"""

from __future__ import annotations

import numpy as np

from ..palette import Role
from .blueprint import ShipPlan
from .core import ShapeParams


def _deck_tops(grid: np.ndarray) -> np.ndarray:
    """Return ``(W, L)`` int array: y of the topmost HULL cell with EMPTY
    above it, or -1 where the column has no exposed hull deck."""
    W, H, L = grid.shape
    tops = np.full((W, L), -1, dtype=np.int32)
    hull = grid == Role.HULL
    for y in range(H - 1):
        exposed = hull[:, y, :] & (grid[:, y + 1, :] == Role.EMPTY)
        tops[exposed] = y
    # Top row: hull at the very top of the grid has no room for greebles.
    return tops


def _place_greebles(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    plan: ShipPlan,
) -> None:
    """Stamp clustered greeble patches on flat decks of the rear/mid hull."""
    if params.greeble_density <= 0:
        return
    W, H, L = grid.shape

    # Patch zone: engine + mid segments, keeping clear of the cockpit rect.
    z_lo = plan.segments[0].z0 + 1
    z_hi = min(plan.segments[1].z1 - 1, plan.cockpit.z0 - 1)
    if z_hi - z_lo < 4:
        return

    tops = _deck_tops(grid)
    # Scale patch attempts with the actual exposed deck area in the patch
    # zone so the same density gives comparable visual coverage on a small
    # scout and a capital ship (a fixed multiplier under-greebles large
    # hulls by ~100x). 0.17 reproduces the old default of ~40 attempts at
    # density 1.0 on the default 20x12x40 hull.
    deck_cols = int((tops[:, z_lo:z_hi] >= 0).sum())
    attempts = max(1, int(round(params.greeble_density * deck_cols * 0.17)))

    for _ in range(attempts):
        motif = int(rng.integers(0, 4))
        pw = int(rng.integers(2, 5))            # patch width  (x)
        pl = int(rng.integers(3, 8))            # patch length (z)
        px = int(rng.integers(0, max(1, W - pw)))
        pz = int(rng.integers(z_lo, max(z_lo + 1, z_hi - pl)))
        pz1 = min(z_hi, pz + pl)
        if pz1 - pz < 3:
            continue

        # Flatness gate: every column in the rect must expose deck at the
        # same height. Uneven ground → skip; another attempt will land.
        patch_tops = tops[px : px + pw, pz:pz1]
        if (patch_tops < 0).any():
            continue
        y0 = int(patch_tops.flat[0])
        if not (patch_tops == y0).all():
            continue
        y = y0 + 1
        if y >= H:
            continue

        if motif == 0:
            _motif_panel_outline(grid, px, pw, pz, pz1, y)
        elif motif == 1:
            _motif_vent_row(grid, px, pw, pz, pz1, y)
        elif motif == 2:
            _motif_pipe_run(grid, px, pw, pz, pz1, y)
        else:
            _motif_antenna_cluster(grid, rng, px, pw, pz, pz1, y)


def _put(grid: np.ndarray, x: int, y: int, z: int) -> None:
    if grid[x, y, z] == Role.EMPTY:
        grid[x, y, z] = Role.GREEBLE


def _motif_panel_outline(
    grid: np.ndarray, px: int, pw: int, pz: int, pz1: int, y: int
) -> None:
    """Raised border ring around the patch rect."""
    for x in range(px, px + pw):
        for z in range(pz, pz1):
            on_edge = x in (px, px + pw - 1) or z in (pz, pz1 - 1)
            if on_edge:
                _put(grid, x, y, z)


def _motif_vent_row(
    grid: np.ndarray, px: int, pw: int, pz: int, pz1: int, y: int
) -> None:
    """Alternating raised full-width rows (louvres) along z."""
    for z in range(pz, pz1, 2):
        for x in range(px, px + pw):
            _put(grid, x, y, z)


def _motif_pipe_run(
    grid: np.ndarray, px: int, pw: int, pz: int, pz1: int, y: int
) -> None:
    """Centerline pipe along z with 2-high couplings at both ends."""
    H = grid.shape[1]
    x_mid = px + pw // 2
    for z in range(pz, pz1):
        _put(grid, x_mid, y, z)
    for z in (pz, pz1 - 1):
        if y + 1 < H:
            _put(grid, x_mid, y + 1, z)


def _motif_antenna_cluster(
    grid: np.ndarray,
    rng: np.random.Generator,
    px: int,
    pw: int,
    pz: int,
    pz1: int,
    y: int,
) -> None:
    """Masts (height 2-4) at two opposite patch corners."""
    H = grid.shape[1]
    for x, z in ((px, pz), (px + pw - 1, pz1 - 1)):
        height = int(rng.integers(2, 5))
        for dy in range(height):
            if y + dy < H:
                _put(grid, x, y + dy, z)


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
