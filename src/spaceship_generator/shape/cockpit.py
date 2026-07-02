"""Cockpit placement — framed glass set into (or raised from) the deck.

Every variant works the same way: the plan hands us a deck rectangle
(``plan.cockpit``: z-range + half-width), we find the hull's top surface
inside that rectangle, and we place COCKPIT_GLASS such that every glass
voxel touches HULL — recessed strips keep a hull frame around them, raised
bridges sit on the deck they grew from. No more floating glass blobs.

Variants:

* ``BUBBLE`` — recessed rounded canopy: glass replaces the deck's top hull
  cells inside an elliptical footprint, hull frame all around.
* ``POINTED`` — narrow glass strip tapering toward the nose.
* ``INTEGRATED`` — full-rect recessed glass strip with a hull border.
* ``CANOPY_DOME`` — raised one-voxel dome of glass on the deck with a hull
  collar ring.
* ``WRAP_BRIDGE`` — raised 2-high hull bridge block whose top front/side
  faces carry a wrap-around glass band.
* ``OFFSET_TURRET`` — small raised hull turret offset to one side with a
  glass cap (the final mirror pass restores symmetry).
"""

from __future__ import annotations

import numpy as np

from ..palette import Role
from ..structure_styles import default_cockpit_for
from .blueprint import ShipPlan
from .core import CockpitStyle, ShapeParams


def _place_cockpit(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    plan: ShipPlan,
) -> None:
    """Place the planned cockpit. ``rng`` unused (kept for placer symmetry)."""
    style = default_cockpit_for(params.structure_style, plan.cockpit.style)
    if style == CockpitStyle.POINTED:
        _place_pointed(grid, plan)
    elif style == CockpitStyle.INTEGRATED:
        _place_integrated(grid, plan)
    elif style == CockpitStyle.CANOPY_DOME:
        _place_canopy_dome(grid, plan)
    elif style == CockpitStyle.WRAP_BRIDGE:
        _place_wrap_bridge(grid, plan)
    elif style == CockpitStyle.OFFSET_TURRET:
        _place_offset_turret(grid, plan)
    else:
        _place_bubble(grid, plan)


def _deck_top(grid: np.ndarray, x: int, z: int) -> int:
    """Y of the topmost HULL voxel in column ``(x, z)``; -1 if none."""
    H = grid.shape[1]
    for y in range(H - 1, -1, -1):
        if grid[x, y, z] == Role.HULL:
            return y
    return -1


def _rect_columns(grid: np.ndarray, plan: ShipPlan, *, inset: int = 0):
    """Yield ``(x, z, deck_y)`` for every column of the cockpit rect.

    ``inset > 0`` shrinks the rect on all four sides — used to leave a hull
    frame around recessed glass.
    """
    W, H, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    z0 = max(0, cp.z0 + inset)
    z1 = min(L, cp.z1 - inset)
    half_w = max(0.0, cp.half_w - inset)
    for z in range(z0, z1):
        for x in range(W):
            if abs(x - cx) > half_w:
                continue
            top = _deck_top(grid, x, z)
            if top >= 0:
                yield x, z, top


def _place_integrated(grid: np.ndarray, plan: ShipPlan) -> None:
    """Recessed glass strip: replace deck-top hull inside the inset rect.

    On cramped rects (half-width <= 1 or z-span <= 2) the inset would leave
    zero columns, so it is dropped there — a cockpit must always exist.
    """
    cp = plan.cockpit
    inset = 1 if (cp.half_w > 1 and (cp.z1 - cp.z0) > 2) else 0
    for x, z, top in _rect_columns(grid, plan, inset=inset):
        grid[x, top, z] = Role.COCKPIT_GLASS


def _place_bubble(grid: np.ndarray, plan: ShipPlan) -> None:
    """Recessed rounded canopy: elliptical footprint inside the rect."""
    W, _, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    cz = (cp.z0 + cp.z1 - 1) / 2.0
    rz = max(1.0, (cp.z1 - cp.z0) / 2.0 - 0.5)
    rx = max(1.0, cp.half_w - 0.25)
    for x, z, top in _rect_columns(grid, plan):
        dx = (x - cx) / rx
        dz = (z - cz) / rz
        if dx * dx + dz * dz <= 1.0:
            grid[x, top, z] = Role.COCKPIT_GLASS


def _place_pointed(grid: np.ndarray, plan: ShipPlan) -> None:
    """Narrow strip that tapers toward the nose, reaching 2 slices past the
    planned rect so the canopy visibly runs out onto the nose taper.

    The 0.51 floor keeps the centerline pair of columns included on
    even-width grids (where the closest |x - cx| is 0.5)."""
    W, _, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    z0 = cp.z0
    z1 = min(L, cp.z1 + 2)
    denom = max(1, z1 - 1 - z0)
    for z in range(z0, z1):
        t = (z - z0) / denom  # 0 at rear of strip → 1 at nose end
        local_half = max(0.51, cp.half_w * (1.0 - t))
        for x in range(W):
            if abs(x - cx) > local_half:
                continue
            top = _deck_top(grid, x, z)
            if top >= 0:
                grid[x, top, z] = Role.COCKPIT_GLASS


def _place_canopy_dome(grid: np.ndarray, plan: ShipPlan) -> None:
    """Raised glass dome one voxel above the deck, hull collar around it."""
    W, H, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    cz = (cp.z0 + cp.z1 - 1) / 2.0
    rz = max(1.0, (cp.z1 - cp.z0) / 2.0 - 0.5)
    rx = max(1.0, cp.half_w - 0.25)
    for x, z, top in _rect_columns(grid, plan):
        dx = (x - cx) / rx
        dz = (z - cz) / rz
        r2 = dx * dx + dz * dz
        y_up = top + 1
        if y_up >= H:
            continue
        if r2 <= 0.55:
            # Dome core: raised glass.
            if grid[x, y_up, z] == Role.EMPTY:
                grid[x, y_up, z] = Role.COCKPIT_GLASS
        elif r2 <= 1.0:
            # Collar: raised hull ring framing the dome.
            if grid[x, y_up, z] == Role.EMPTY:
                grid[x, y_up, z] = Role.HULL


def _place_wrap_bridge(grid: np.ndarray, plan: ShipPlan) -> None:
    """Raised 2-high hull bridge with a wrap-around glass band on top.

    The bridge rect is extended forward to the nose (panoramic bridge), so
    the glass band reaches close to ``z = L - 1``.
    """
    W, H, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    z_end = L  # panoramic: run the strip out to the nose tip
    for z in range(cp.z0, z_end):
        for x in range(W):
            if abs(x - cx) > cp.half_w:
                continue
            top = _deck_top(grid, x, z)
            if top < 0:
                continue
            y1 = top + 1
            y2 = top + 2
            if y1 >= H:
                continue
            on_edge = (
                abs(abs(x - cx) - cp.half_w) < 1.0
                or z == cp.z0
                or z == z_end - 1
            )
            # Level 1: solid hull block everywhere in the rect.
            if grid[x, y1, z] == Role.EMPTY:
                grid[x, y1, z] = Role.HULL
            # Level 2: glass band on the rect's perimeter, hull core inside.
            if y2 < H and grid[x, y2, z] == Role.EMPTY:
                grid[x, y2, z] = Role.COCKPIT_GLASS if on_edge else Role.HULL


def _place_offset_turret(grid: np.ndarray, plan: ShipPlan) -> None:
    """Small raised hull turret offset to one side, glass cap on top.

    Deliberately breaks X-symmetry here; the assembly mirror pass restores
    it, producing twin turrets.
    """
    W, H, L = grid.shape
    cp = plan.cockpit
    cx = (W - 1) / 2.0
    t_cx = max(1, int(round(cx - max(1.0, cp.half_w))))
    half = max(1, cp.half_w // 2 + 1)
    z_mid = (cp.z0 + cp.z1) // 2
    half_z = max(1, (cp.z1 - cp.z0) // 3)
    for z in range(max(0, z_mid - half_z), min(L, z_mid + half_z + 1)):
        for x in range(max(0, t_cx - half), min(W, t_cx + half + 1)):
            top = _deck_top(grid, x, z)
            if top < 0:
                continue
            y1 = top + 1
            y2 = top + 2
            if y1 < H and grid[x, y1, z] == Role.EMPTY:
                grid[x, y1, z] = Role.HULL
            if y2 < H and grid[x, y2, z] == Role.EMPTY:
                grid[x, y2, z] = Role.COCKPIT_GLASS
