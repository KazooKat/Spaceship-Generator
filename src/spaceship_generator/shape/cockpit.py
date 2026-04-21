"""Cockpit placement — BUBBLE, POINTED, INTEGRATED, CANOPY_DOME, WRAP_BRIDGE,
and OFFSET_TURRET variants."""

from __future__ import annotations

import math

import numpy as np

from ..palette import Role
from ..structure_styles import default_cockpit_for
from .core import CockpitStyle, ShapeParams


def _place_cockpit(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Attach a cockpit to the nose of the ship.

    Shape is controlled by ``params.cockpit_style``:

    * :attr:`CockpitStyle.BUBBLE` — small ellipsoidal bulge above the nose.
    * :attr:`CockpitStyle.POINTED` — tapered cone narrowing toward the nose.
    * :attr:`CockpitStyle.INTEGRATED` — flat strip along the upper-forward hull
      (no protrusion; just converts hull voxels to cockpit glass).
    * :attr:`CockpitStyle.CANOPY_DOME` — low rounded dome ringed with hull,
      sitting atop the forward upper hull.
    * :attr:`CockpitStyle.WRAP_BRIDGE` — elongated transparent strip running
      most of the forward-upper hull, framed by hull voxels above and below.
    * :attr:`CockpitStyle.OFFSET_TURRET` — asymmetric raised cockpit tower
      offset to one side (cockpit breaks bilateral symmetry; hull does not).
    """
    style = default_cockpit_for(params.structure_style, params.cockpit_style)
    if style == CockpitStyle.POINTED:
        _place_cockpit_pointed(grid)
    elif style == CockpitStyle.INTEGRATED:
        _place_cockpit_integrated(grid)
    elif style == CockpitStyle.CANOPY_DOME:
        _place_canopy_dome(grid)
    elif style == CockpitStyle.WRAP_BRIDGE:
        _place_wrap_bridge(grid)
    elif style == CockpitStyle.OFFSET_TURRET:
        _place_offset_turret(grid)
    else:
        _place_cockpit_bubble(grid)


def _place_cockpit_bubble(grid: np.ndarray) -> None:
    """Small ellipsoidal bulge sitting slightly above center on the nose."""
    W, H, L = grid.shape
    cx = (W - 1) / 2.0
    cy = min(H - 2, (H - 1) / 2.0 + 1.0)
    cz = L - max(3, L // 8)

    rx = max(1.2, W / 10.0)
    ry = max(1.0, H / 9.0)
    rz = max(1.5, L / 14.0)

    for x in range(W):
        for y in range(H):
            for z in range(max(0, int(cz - rz - 1)), L):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                dz = (z - cz) / rz
                if dx * dx + dy * dy + dz * dz <= 1.1:
                    grid[x, y, z] = Role.COCKPIT_GLASS


def _place_cockpit_pointed(grid: np.ndarray) -> None:
    """A tapered cone/pyramid of COCKPIT_GLASS narrowing toward the nose.

    Narrower and longer than the bubble, sitting flush with the upper hull
    (fighter-jet canopy). Built by sweeping a shrinking circular cap from
    ``z_start`` up to the nose, which keeps the shape symmetric in X on its own.
    """
    W, H, L = grid.shape
    cx = (W - 1) / 2.0
    # Sit flush with hull top instead of floating above.
    cy = (H - 1) / 2.0 + 0.5

    # Longer than bubble: covers roughly last third of the ship.
    cone_length = max(4, L // 3)
    z_start = max(0, L - cone_length)

    # Maximum half-width at the base of the canopy; narrower than bubble.
    base_rx = max(1.0, W / 14.0)
    base_ry = max(0.8, H / 12.0)

    for z in range(z_start, L):
        # t: 0 at base of canopy, 1 at the very nose.
        t = (z - z_start) / max(cone_length - 1, 1)
        # Quadratic taper so the nose becomes a sharp point.
        taper = max(0.0, 1.0 - t * t)
        rx = base_rx * taper
        ry = base_ry * taper
        if rx < 0.5 and ry < 0.5:
            # Still lay down a single voxel ridge along the centerline so the
            # canopy visibly touches the nose.
            xi = int(round(cx))
            yi = int(round(cy))
            if 0 <= xi < W and 0 <= yi < H:
                grid[xi, yi, z] = Role.COCKPIT_GLASS
            # Mirror for even widths (keeps X-symmetry for the half-voxel center).
            xi_m = W - 1 - xi
            if 0 <= xi_m < W and 0 <= yi < H:
                grid[xi_m, yi, z] = Role.COCKPIT_GLASS
            continue

        rx_eff = max(rx, 0.5)
        ry_eff = max(ry, 0.5)

        x_lo = max(0, int(math.floor(cx - rx_eff)))
        x_hi = min(W - 1, int(math.ceil(cx + rx_eff)))
        y_lo = max(0, int(math.floor(cy - ry_eff)))
        y_hi = min(H - 1, int(math.ceil(cy + ry_eff)))

        for x in range(x_lo, x_hi + 1):
            for y in range(y_lo, y_hi + 1):
                dx = (x - cx) / rx_eff
                dy = (y - cy) / ry_eff
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.COCKPIT_GLASS


def _place_cockpit_integrated(grid: np.ndarray) -> None:
    """A flat, recessed cockpit — a strip along the upper-forward hull.

    Walks every (x, z) column in the forward portion of the ship, finds the
    topmost HULL voxel, and converts it to COCKPIT_GLASS if it is on the upper
    half. Does not add voxels outside the hull envelope.
    """
    W, H, L = grid.shape
    strip_length = max(3, L // 4)
    z_start = max(0, L - strip_length)

    cx = (W - 1) / 2.0
    # Half-width of the glass strip across X: narrower than the hull so it
    # reads as a cockpit rather than a deck.
    strip_rx = max(1.0, W / 4.0)

    upper_cutoff = H // 2  # topmost voxel must be at or above this to qualify

    for z in range(z_start, L):
        for x in range(W):
            if abs(x - cx) > strip_rx:
                continue
            # Find the topmost HULL voxel in this column.
            top_y = -1
            for y in range(H - 1, -1, -1):
                if grid[x, y, z] == Role.HULL:
                    top_y = y
                    break
            if top_y >= upper_cutoff:
                grid[x, top_y, z] = Role.COCKPIT_GLASS


def _place_canopy_dome(grid: np.ndarray) -> None:
    """Low rounded dome above the forward upper hull.

    A half-ellipsoidal shell of ``COCKPIT_GLASS`` sits atop the hull, with a
    ring of ``HULL`` voxels one row below the dome equator to read as a
    structural collar. Fully X-symmetric.
    """
    W, H, L = grid.shape
    cx = (W - 1) / 2.0
    # Dome rests on the hull top (slightly below the upper edge) and is low.
    cy = min(H - 2, (H - 1) / 2.0 + 1.5)
    cz = L - max(3, L // 7)

    # Wider than a bubble, but flatter in Y (dome, not sphere).
    rx = max(1.5, W / 7.0)
    ry = max(0.8, H / 14.0)
    rz = max(1.5, L / 10.0)

    y_collar = max(0, int(math.floor(cy)))  # collar sits at dome equator row
    for x in range(W):
        for y in range(int(math.floor(cy)), H):
            for z in range(max(0, int(cz - rz - 1)), L):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                dz = (z - cz) / rz
                r2 = dx * dx + dy * dy + dz * dz
                if r2 <= 1.1 and y >= y_collar:
                    # Upper-half ellipsoid → glass dome; never overwrite HULL.
                    if grid[x, y, z] != Role.HULL:
                        grid[x, y, z] = Role.COCKPIT_GLASS

    # Hull collar: thin ring of HULL one row below the dome equator, only on
    # EMPTY cells so existing hull is never erased.
    ring_y = max(0, y_collar - 1)
    for x in range(W):
        for z in range(max(0, int(cz - rz - 1)), L):
            dx = (x - cx) / rx
            dz = (z - cz) / rz
            r2 = dx * dx + dz * dz
            # Annulus: between ~0.75r and ~1.1r so the collar is a ring.
            if 0.75 <= r2 <= 1.1 and grid[x, ring_y, z] == Role.EMPTY:
                grid[x, ring_y, z] = Role.HULL


def _place_wrap_bridge(grid: np.ndarray) -> None:
    """An elongated transparent strip along the forward-top hull.

    Sweeps a horizontal band of ``COCKPIT_GLASS`` across the upper surface
    and frames it with a thin ``HULL`` roof one row above, producing a long
    panoramic bridge window. Fully X-symmetric.
    """
    W, H, L = grid.shape
    strip_length = max(4, L // 3)
    z_start = max(0, L - strip_length)

    cx = (W - 1) / 2.0
    # Wider than INTEGRATED so the window feels panoramic but still narrower
    # than the hull so the frame reads as a bridge rather than the whole deck.
    strip_rx = max(1.0, W / 3.5)

    upper_cutoff = H // 2

    for z in range(z_start, L):
        for x in range(W):
            if abs(x - cx) > strip_rx:
                continue
            # Find the topmost HULL voxel in this column.
            top_y = -1
            for y in range(H - 1, -1, -1):
                if grid[x, y, z] == Role.HULL:
                    top_y = y
                    break
            if top_y < upper_cutoff:
                continue
            # Glass band sits ONE ROW ABOVE the hull top (no HULL erasure).
            glass_y = top_y + 1
            if glass_y >= H:
                continue
            if grid[x, glass_y, z] == Role.EMPTY:
                grid[x, glass_y, z] = Role.COCKPIT_GLASS
            # Hull roof above the glass, only on the frame edges.
            roof_y = glass_y + 1
            if roof_y >= H:
                continue
            on_z_cap = (z == z_start) or (z == L - 1)
            on_x_edge = abs(abs(x - cx) - strip_rx) < 1.0
            if (on_z_cap or on_x_edge) and grid[x, roof_y, z] == Role.EMPTY:
                grid[x, roof_y, z] = Role.HULL


def _place_offset_turret(grid: np.ndarray) -> None:
    """Asymmetric raised cockpit tower offset to one side.

    A small rectangular turret (``HULL`` walls + ``COCKPIT_GLASS`` cap) sits
    on the upper-forward hull, shifted off the centerline. This deliberately
    breaks X-symmetry on the cockpit itself; the assembly pipeline's
    ``_enforce_x_symmetry`` re-mirrors the final grid.
    """
    W, H, L = grid.shape
    cx = (W - 1) / 2.0
    # Shift the turret toward x=0; mirroring restores symmetry downstream.
    turret_cx = max(1, int(round(cx - max(1.0, W / 8.0))))

    # Turret footprint: small rectangle on the upper hull.
    half_x = max(1, W // 10)
    half_z = max(1, L // 12)
    # Anchor Z a bit behind the nose so the turret sits forward-of-center
    # without reaching the point of the ship.
    turret_cz = L - max(3, L // 5)

    # Find the hull top along the turret's central column; turret rises from
    # one voxel above that.
    base_top = -1
    for y in range(H - 1, -1, -1):
        if grid[turret_cx, y, turret_cz] == Role.HULL:
            base_top = y
            break
    if base_top < 0:
        # Fall back to mid-height if the column is empty (pathological shape).
        base_top = H // 2

    wall_bottom = base_top + 1
    wall_top = min(H - 1, wall_bottom + max(1, H // 6))
    if wall_top <= wall_bottom:
        wall_top = min(H - 1, wall_bottom + 1)

    x_lo = max(0, turret_cx - half_x)
    x_hi = min(W - 1, turret_cx + half_x)
    z_lo = max(0, turret_cz - half_z)
    z_hi = min(L - 1, turret_cz + half_z)

    # Walls: hull voxels forming the turret sides, only overwriting EMPTY.
    for y in range(wall_bottom, wall_top):
        for x in range(x_lo, x_hi + 1):
            for z in range(z_lo, z_hi + 1):
                on_edge = (x == x_lo or x == x_hi or z == z_lo or z == z_hi)
                if on_edge and grid[x, y, z] == Role.EMPTY:
                    grid[x, y, z] = Role.HULL

    # Glass cap: solid rectangle of cockpit glass at the top of the turret.
    cap_y = wall_top
    if 0 <= cap_y < H:
        for x in range(x_lo, x_hi + 1):
            for z in range(z_lo, z_hi + 1):
                grid[x, cap_y, z] = Role.COCKPIT_GLASS
