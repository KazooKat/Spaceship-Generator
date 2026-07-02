"""Engine placement — nozzles protruding behind the hull's rear wall.

The hull starts at ``plan.engine.wall_z``; nozzles are stamped into the
empty protrusion zone ``[0, wall_z)`` plus one slice of overlap into the
wall so they weld to the hull. Each nozzle gets a HULL rim ring on the wall
face so it reads as a mounted thruster, not a floating cylinder. Optional
side nacelle pods (HULL) hang off the rear hull on thick pylons, each with
its own small nozzle.
"""

from __future__ import annotations

import numpy as np

from ..palette import Role
from .blueprint import ShipPlan
from .core import ShapeParams


def _stamp_disc(
    grid: np.ndarray,
    cx: float,
    cy: float,
    z0: int,
    z1: int,
    radius: float,
    role: Role,
    *,
    only_empty: bool = True,
) -> None:
    """Stamp a filled circle of ``role`` into every slice ``z in [z0, z1)``."""
    W, H, L = grid.shape
    z0 = max(0, z0)
    z1 = min(L, z1)
    if z1 <= z0:
        return
    xs = np.arange(W, dtype=np.float64).reshape(W, 1)
    ys = np.arange(H, dtype=np.float64).reshape(1, H)
    inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= radius * radius
    for z in range(z0, z1):
        view = grid[:, :, z]
        if only_empty:
            view[inside & (view == Role.EMPTY)] = role
        else:
            view[inside] = role


def _place_engines(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    plan: ShipPlan,
) -> None:
    """Place planned nozzles and (optionally) nacelle pods.

    ``rng`` is unused — all variation is in the plan — but kept so every
    placer shares one signature.
    """
    eng = plan.engine
    if not eng.nozzle_xs:
        return
    W, H, L = grid.shape
    wall_z = eng.wall_z
    r = eng.radius
    cy = eng.nozzle_y

    for ex in eng.nozzle_xs:
        # Nozzle body: protrusion zone plus one slice into the wall (weld).
        _stamp_disc(grid, ex, cy, 0, wall_z + 1, r, Role.ENGINE)
        # Rim ring on the wall face: annulus of HULL one voxel wider than
        # the nozzle, only where empty, so the mount reads as structure.
        _stamp_ring(grid, ex, cy, wall_z, r + 1.4, r, Role.HULL)

    if eng.nacelles:
        _place_nacelles(grid, plan)


def _stamp_ring(
    grid: np.ndarray,
    cx: float,
    cy: float,
    z: int,
    r_outer: float,
    r_inner: float,
    role: Role,
) -> None:
    """Stamp an annulus of ``role`` into slice ``z`` (empty cells only)."""
    W, H, L = grid.shape
    if not (0 <= z < L):
        return
    xs = np.arange(W, dtype=np.float64).reshape(W, 1)
    ys = np.arange(H, dtype=np.float64).reshape(1, H)
    d2 = (xs - cx) ** 2 + (ys - cy) ** 2
    ring = (d2 <= r_outer * r_outer) & (d2 > r_inner * r_inner)
    view = grid[:, :, z]
    view[ring & (view == Role.EMPTY)] = role


def _place_nacelles(grid: np.ndarray, plan: ShipPlan) -> None:
    """Two side pods on thick pylons, each with a small rear nozzle."""
    W, H, L = grid.shape
    eng = plan.engine
    cx = (W - 1) / 2.0
    y_center = eng.nozzle_y
    hw = eng.nacelle_half_w
    hh = eng.nacelle_half_h
    z0 = max(eng.wall_z, eng.nacelle_z0)
    z1 = min(L, eng.nacelle_z1)
    if z1 <= z0:
        return

    pod_r = max(1.0, min(hw, hh) + 0.4)
    # Left pod center; right pod comes from the mirror pass but we stamp
    # both anyway so the pre-mirror grid is already symmetric.
    for side in (-1, 1):
        pcx = cx + side * eng.nacelle_cx_off
        if not (0 <= pcx - hw and pcx + hw < W):
            continue
        # Pod body: rounded box (disc per slice).
        _stamp_disc(grid, pcx, y_center, z0, z1, pod_r, Role.HULL)
        # Pod nozzle: small ENGINE disc protruding behind the pod.
        noz_r = max(1.0, pod_r * 0.7)
        _stamp_disc(grid, pcx, y_center, max(0, z0 - (eng.wall_z - 0)), z0 + 1,
                    noz_r, Role.ENGINE)
        # Pylon: 2-voxel-thick horizontal slab welding pod to hull, placed
        # mid-pod in Z with a 3-slice depth.
        pz0 = min(z1 - 1, z0 + (z1 - z0) // 2 - 1)
        pz1 = min(z1, pz0 + 3)
        half_w_hull, _, _, _ = plan.hull_half_at(pz0)
        x_inner = cx + side * max(0.0, half_w_hull - 2.0)
        x_outer = pcx
        x_lo = int(round(min(x_inner, x_outer)))
        x_hi = int(round(max(x_inner, x_outer)))
        y_lo = max(0, int(round(y_center)) )
        y_hi = min(H - 1, y_lo + 1)
        for z in range(pz0, pz1):
            for x in range(max(0, x_lo), min(W - 1, x_hi) + 1):
                for y in (y_lo, y_hi):
                    if grid[x, y, z] == Role.EMPTY:
                        grid[x, y, z] = Role.HULL
