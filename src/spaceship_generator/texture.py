"""Refine a coarse shape grid into a fully-roled grid.

The input grid from :mod:`shape` only uses the coarse roles
``HULL``, ``COCKPIT_GLASS``, ``ENGINE``, ``WING``, ``GREEBLE``.
``assign_roles`` adds fine detail:

* Interior ``HULL`` voxels become ``INTERIOR``.
* Side-facing upper-band ``HULL`` surface cells become ``WINDOW`` at regular spacing.
* ``HULL`` surface cells at the mid-height line become a ``HULL_DARK`` accent stripe.
* The rear-most faces of engine cylinders become ``ENGINE_GLOW``.
* Wing-tip leading-edge cells become ``LIGHT``.

All rules are deterministic in the cell's coordinates so bilateral symmetry
of the input is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .palette import Role
from .shape import _surface_mask


@dataclass
class TextureParams:
    """User-tunable parameters for role refinement."""

    window_period_cells: int = 4   # window every N cells along Z on upper hull
    accent_stripe_period: int = 8  # HULL_DARK stripe every N cells along Z
    engine_glow_depth: int = 1     # thickness (in Z) of engine-glow core at the rear


def assign_roles(
    shape_grid: np.ndarray,
    params: TextureParams | None = None,
) -> np.ndarray:
    """Return a copy of ``shape_grid`` with refined role assignments."""
    params = params or TextureParams()
    if shape_grid.ndim != 3:
        raise ValueError(f"shape_grid must be 3D, got shape {shape_grid.shape}")
    out = shape_grid.copy()

    surface = _surface_mask(out)

    _fill_interior(out, surface)
    _paint_accent_stripe(out, surface, params)
    _paint_windows(out, surface, params)
    _paint_engine_glow(out, params)
    _paint_wing_lights(out)

    return out


# ---------------------------------------------------------------------------


def _fill_interior(grid: np.ndarray, surface: np.ndarray) -> None:
    """Convert non-surface HULL cells to INTERIOR."""
    interior = (grid == Role.HULL) & (~surface)
    grid[interior] = Role.INTERIOR


def _paint_windows(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """Place windows on side-facing HULL surface cells in the upper hull band."""
    W, H, L = grid.shape
    cy = (H - 1) / 2.0
    period = max(2, params.window_period_cells)
    phase = period // 2

    # Cells that are HULL and on the surface.
    hull_surf = (grid == Role.HULL) & surface
    # Only upper band (above mid-height).
    upper_band = np.zeros_like(hull_surf)
    y_indices = np.arange(H).reshape(1, H, 1)
    upper_band = np.broadcast_to(y_indices > cy, grid.shape)

    # Side-facing: at least one ±X neighbor is empty (or out of bounds).
    left_empty = np.ones_like(hull_surf)
    right_empty = np.ones_like(hull_surf)
    left_empty[1:, :, :] = grid[:-1, :, :] == Role.EMPTY
    right_empty[:-1, :, :] = grid[1:, :, :] == Role.EMPTY
    side_facing = left_empty | right_empty

    # Z-phase mask — fully vectorised.
    z_indices = np.arange(L).reshape(1, 1, L)
    z_phase = (z_indices % period) == phase
    z_phase = np.broadcast_to(z_phase, grid.shape)

    mask = hull_surf & upper_band & side_facing & z_phase
    grid[mask] = Role.WINDOW


def _paint_accent_stripe(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """HULL_DARK stripe around mid-height at regular Z intervals."""
    W, H, L = grid.shape
    cy = (H - 1) // 2
    period = max(2, params.accent_stripe_period)

    hull_surf = (grid == Role.HULL) & surface
    y_band = np.zeros_like(hull_surf)
    # One-voxel-thick band at mid-height.
    y_band[:, cy:cy + 1, :] = True

    z_indices = np.arange(L).reshape(1, 1, L)
    z_phase = np.broadcast_to((z_indices % period) == 0, grid.shape)

    grid[hull_surf & y_band & z_phase] = Role.HULL_DARK


def _paint_engine_glow(grid: np.ndarray, params: TextureParams) -> None:
    """Mark the rear-most layers of engine cylinders as ENGINE_GLOW."""
    depth = max(1, params.engine_glow_depth)
    L = grid.shape[2]
    rear_depth = min(depth, L)
    rear_slice = grid[:, :, :rear_depth]
    rear_slice[rear_slice == Role.ENGINE] = Role.ENGINE_GLOW


def _paint_wing_lights(grid: np.ndarray) -> None:
    """Running lights at the outermost-X leading-edge cells of each wing."""
    wing_cells = np.argwhere(grid == Role.WING)
    if wing_cells.size == 0:
        return

    # Group wing cells by X; within each X column, the leading-edge cell is
    # the one with the largest Z (toward the nose).
    W = grid.shape[0]
    min_x = int(wing_cells[:, 0].min())
    max_x = int(wing_cells[:, 0].max())

    for x in (min_x, max_x):
        # Leading-edge cell for this x-column.
        col = wing_cells[wing_cells[:, 0] == x]
        if col.size == 0:
            continue
        max_z = col[:, 2].max()
        for row in col[col[:, 2] == max_z]:
            _, y, z = row
            grid[x, y, z] = Role.LIGHT

    # Mirror: ensure the mirrored X also gets a light if it wasn't picked up.
    for x in (min_x, max_x):
        mx = W - 1 - x
        if mx != x:
            col = wing_cells[wing_cells[:, 0] == mx]
            if col.size == 0:
                continue
            max_z = col[:, 2].max()
            for row in col[col[:, 2] == max_z]:
                _, y, z = row
                if grid[mx, y, z] == Role.WING:
                    grid[mx, y, z] = Role.LIGHT
