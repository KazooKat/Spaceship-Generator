"""Cockpit placement — BUBBLE, POINTED, and INTEGRATED variants."""

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
    """
    style = default_cockpit_for(params.structure_style, params.cockpit_style)
    if style == CockpitStyle.POINTED:
        _place_cockpit_pointed(grid)
    elif style == CockpitStyle.INTEGRATED:
        _place_cockpit_integrated(grid)
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
