"""Refine a coarse shape grid into a fully-roled grid.

The input grid from :mod:`shape` only uses the coarse roles
``HULL``, ``COCKPIT_GLASS``, ``ENGINE``, ``WING``, ``GREEBLE``.
``assign_roles`` adds fine detail:

* Interior ``HULL`` voxels become ``INTERIOR``.
* Side-facing upper-band ``HULL`` surface cells become ``WINDOW`` at regular spacing.
* ``HULL`` surface cells at the mid-height line become a ``HULL_DARK`` accent stripe.
* Additional ``HULL_DARK`` bands at ``cy ± H//4`` when ``panel_line_bands > 1``.
* Optional deterministic ``HULL_DARK`` coordinate-hashed noise speckle over hull.
* Optional ``HULL_DARK`` "rivet" dots on upper-hull surface at a fixed XZ period.
* The rear-most faces of engine cylinders become ``ENGINE_GLOW``.
* Optional ``HULL_DARK`` ring of dimmer pixels around every ``ENGINE_GLOW``.
* Wing-tip leading-edge cells become ``LIGHT``.
* Optional: regularly-spaced belly lights on downward-facing hull surface.
* Optional: a single nose-tip light at the forward-most centerline voxel.

All rules are deterministic in the cell's coordinates so bilateral symmetry
of the input is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .palette import Role
from .shape import _surface_mask

# Roles protected from overwrite by later lighting passes.
# INTERIOR is included so belly/nose-tip light passes don't carve into the
# hull's hidden interior; LIGHT so a previously-painted running light is not
# clobbered by a later pass.
_PROTECTED_ROLES: tuple[Role, ...] = (
    Role.COCKPIT_GLASS,
    Role.WINDOW,
    Role.ENGINE,
    Role.ENGINE_GLOW,
    Role.LIGHT,
    Role.INTERIOR,
)

# Roles new "hull noise / rivet / engine ring" passes must never overwrite.
# (Stripes are fine to be further decorated; WING/GREEBLE/LIGHT/INTERIOR are
# off-limits, as are all cockpit/window/engine roles.)
_HULL_NOISE_FORBIDDEN: tuple[Role, ...] = (
    Role.EMPTY,
    Role.COCKPIT_GLASS,
    Role.WINDOW,
    Role.ENGINE,
    Role.ENGINE_GLOW,
    Role.WING,
    Role.GREEBLE,
    Role.LIGHT,
    Role.INTERIOR,
)


@dataclass
class TextureParams:
    """User-tunable parameters for role refinement."""

    window_period_cells: int = 4   # window every N cells along Z on upper hull
    accent_stripe_period: int = 8  # HULL_DARK stripe every N cells along Z
    engine_glow_depth: int = 1     # thickness (in Z) of engine-glow core at the rear
    belly_light_period: int = 0    # LIGHT every N cells along Z on belly (0 disables)
    nose_tip_light: bool = True    # single LIGHT at forward-most centerline voxel
    # Minecraft-builder 60-30-10 / greeble extensions (all default to no-op).
    hull_noise_ratio: float = 0.0        # 0..1 fraction of side-hull cells → HULL_DARK
    panel_line_bands: int = 1            # 1=just mid stripe, 2=+upper, 3=+upper+lower
    rivet_period: int = 0                # XZ rivet dot period on upper hull (0 disables)
    engine_glow_ring: bool = False       # dim HULL_DARK ring around each ENGINE_GLOW


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
    _paint_panel_bands(out, surface, params)
    # Paint windows before hull noise / rivets so noise never displaces windows.
    _paint_windows(out, surface, params)
    _paint_hull_noise(out, surface, params)
    _paint_rivets(out, surface, params)
    _paint_engine_glow(out, params)
    _paint_engine_glow_ring(out, params)
    _paint_wing_lights(out)
    _paint_belly_lights(out, surface, params)
    _paint_nose_tip_light(out, params)

    return out


# ---------------------------------------------------------------------------


def _side_facing_mask(grid: np.ndarray) -> np.ndarray:
    """Cells with at least one ±X neighbor EMPTY (or out of bounds).

    Shared by windows, hull noise, and rivets — all "paint only where the
    hull faces sideways" passes.
    """
    left_empty = np.ones(grid.shape, dtype=bool)
    right_empty = np.ones(grid.shape, dtype=bool)
    left_empty[1:, :, :] = grid[:-1, :, :] == Role.EMPTY
    right_empty[:-1, :, :] = grid[1:, :, :] == Role.EMPTY
    return left_empty | right_empty


def _z_phase_mask(shape: tuple[int, int, int], period: int, phase: int = 0) -> np.ndarray:
    """Broadcasted ``(z % period) == phase`` boolean mask of shape ``shape``."""
    L = shape[2]
    z_indices = np.arange(L).reshape(1, 1, L)
    return np.broadcast_to((z_indices % period) == phase, shape)


def _y_band_mask(shape: tuple[int, int, int], y: int) -> np.ndarray:
    """Single-voxel-thick boolean band at the given ``y`` row."""
    band = np.zeros(shape, dtype=bool)
    band[:, y:y + 1, :] = True
    return band


def _forbidden_mask(grid: np.ndarray, roles: tuple[Role, ...]) -> np.ndarray:
    """Boolean mask of cells whose role is in ``roles``."""
    values = np.array([r.value for r in roles], dtype=grid.dtype)
    return np.isin(grid, values)


def _fill_interior(grid: np.ndarray, surface: np.ndarray) -> None:
    """Convert non-surface HULL cells to INTERIOR."""
    interior = (grid == Role.HULL) & (~surface)
    grid[interior] = Role.INTERIOR


def _paint_windows(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """Place windows on side-facing HULL surface cells in the upper hull band."""
    H = grid.shape[1]
    cy = (H - 1) / 2.0
    period = max(2, params.window_period_cells)
    # Offset so windows don't land exactly on the nose tip (z == 0 phase).
    phase = period // 2

    hull_surf = (grid == Role.HULL) & surface
    y_indices = np.arange(H).reshape(1, H, 1)
    upper_band = np.broadcast_to(y_indices > cy, grid.shape)
    side_facing = _side_facing_mask(grid)
    z_phase = _z_phase_mask(grid.shape, period, phase)

    mask = hull_surf & upper_band & side_facing & z_phase
    grid[mask] = Role.WINDOW


def _paint_accent_stripe(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """HULL_DARK stripe around mid-height at regular Z intervals."""
    H = grid.shape[1]
    cy = (H - 1) // 2
    period = max(2, params.accent_stripe_period)

    hull_surf = (grid == Role.HULL) & surface
    y_band = _y_band_mask(grid.shape, cy)
    z_phase = _z_phase_mask(grid.shape, period)

    grid[hull_surf & y_band & z_phase] = Role.HULL_DARK


def _paint_panel_bands(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """Extra HULL_DARK panel-line bands at cy+H//4 and cy-H//4.

    ``panel_line_bands`` = 1 → no extra bands (just the mid-height stripe above).
    2 → add a band at ``cy + H//4``.
    3 → add another band at ``cy - H//4``. Clamped to 3 upper bound.
    """
    bands = max(1, min(3, int(params.panel_line_bands)))
    if bands == 1:
        return

    H = grid.shape[1]
    cy = (H - 1) // 2
    period = max(2, params.accent_stripe_period)
    offset = max(1, H // 4)

    hull_surf = (grid == Role.HULL) & surface
    z_phase = _z_phase_mask(grid.shape, period)

    extra_ys: list[int] = []
    if bands >= 2:
        y_up = min(H - 1, cy + offset)
        if y_up != cy:
            extra_ys.append(y_up)
    if bands >= 3:
        y_dn = max(0, cy - offset)
        if y_dn != cy and y_dn not in extra_ys:
            extra_ys.append(y_dn)

    for y in extra_ys:
        grid[hull_surf & _y_band_mask(grid.shape, y) & z_phase] = Role.HULL_DARK


def _coord_hash_mod1000(W: int, H: int, L: int) -> np.ndarray:
    """Deterministic coordinate hash per (x,y,z), mirror-symmetric in X.

    Uses ``min(x, W-1-x)`` as the X term so mirrored cells share a hash.
    Returns an int array of shape ``(W, H, L)`` with values in [0, 1000).
    """
    xs = np.arange(W, dtype=np.int64).reshape(W, 1, 1)
    ys = np.arange(H, dtype=np.int64).reshape(1, H, 1)
    zs = np.arange(L, dtype=np.int64).reshape(1, 1, L)
    mx = np.minimum(xs, (W - 1) - xs)  # mirror-symmetric in X
    h = (mx * 73856093) ^ (ys * 19349663) ^ (zs * 83492791)
    return (h % 1000).astype(np.int64)


def _paint_hull_noise(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """Convert a fraction of side-facing HULL surface cells to HULL_DARK.

    Uses a coordinate hash so output is deterministic and X-symmetric, and
    never overwrites protected or non-hull roles. Stripes painted earlier
    stay HULL_DARK (no-op). HULL_DARK cells aren't re-hashed because they're
    already dark.
    """
    ratio = float(params.hull_noise_ratio)
    if ratio <= 0.0:
        return
    ratio = min(ratio, 1.0)

    W, H, L = grid.shape
    # Only HULL (not HULL_DARK) cells on the surface are eligible.
    hull_surf = (grid == Role.HULL) & surface
    side_facing = _side_facing_mask(grid)

    thr = int(ratio * 1000)
    hashes = _coord_hash_mod1000(W, H, L)
    hash_mask = hashes < thr

    # Never re-role INTERIOR / LIGHT / GREEBLE / WING / ENGINE(_GLOW) / WINDOW /
    # COCKPIT_GLASS / EMPTY cells (belt-and-braces; hull_surf already excludes
    # most of these but explicit makes the invariant testable).
    forbidden = _forbidden_mask(grid, _HULL_NOISE_FORBIDDEN)
    mask = hull_surf & side_facing & hash_mask & ~forbidden
    grid[mask] = Role.HULL_DARK


def _paint_rivets(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """HULL_DARK "rivet" dots on upper-hull side-facing surface at an XZ period.

    Symmetric because the X-period test uses ``min(x, W-1-x)``. Rivets are
    never placed over protected/forbidden roles; stripes/noise already
    HULL_DARK are left alone.
    """
    period = int(params.rivet_period)
    if period <= 0:
        return
    # Note: period == 1 means "rivets everywhere" (dense speckle), not
    # "disabled" — only period <= 0 disables. (Docstring says "0 disables".)

    W, H, _L = grid.shape
    cy = (H - 1) / 2.0

    hull_surf = (grid == Role.HULL) & surface
    y_indices = np.arange(H).reshape(1, H, 1)
    upper_band = np.broadcast_to(y_indices > cy, grid.shape)
    side_facing = _side_facing_mask(grid)

    # Symmetric X-period: the mirror index has the same period test.
    xs = np.arange(W).reshape(W, 1, 1)
    mx = np.minimum(xs, (W - 1) - xs)
    x_phase = np.broadcast_to((mx % period) == 0, grid.shape)
    z_phase = _z_phase_mask(grid.shape, period)

    forbidden = _forbidden_mask(grid, _HULL_NOISE_FORBIDDEN)
    mask = hull_surf & upper_band & side_facing & x_phase & z_phase & ~forbidden
    grid[mask] = Role.HULL_DARK


def _paint_engine_glow(grid: np.ndarray, params: TextureParams) -> None:
    """Mark the rear-most layers of engine cylinders as ENGINE_GLOW.

    ``engine_glow_depth <= 0`` disables the pass (useful for handcrafted
    tests that preset ENGINE_GLOW directly and want to isolate the ring pass).
    """
    depth = int(params.engine_glow_depth)
    if depth <= 0:
        return
    L = grid.shape[2]
    rear_depth = min(depth, L)
    rear_slice = grid[:, :, :rear_depth]
    rear_slice[rear_slice == Role.ENGINE] = Role.ENGINE_GLOW


def _paint_engine_glow_ring(grid: np.ndarray, params: TextureParams) -> None:
    """Wrap ENGINE cells orthogonally adjacent to an ENGINE_GLOW with HULL_DARK.

    Only ``Role.ENGINE`` neighbors (±X, ±Y) at the same Z are converted —
    EMPTY and non-engine cells are left untouched. Mirror-symmetric because
    ``ENGINE_GLOW`` placement is symmetric and the ±X shifts preserve symmetry.
    """
    if not params.engine_glow_ring:
        return

    W, H, L = grid.shape
    glow = grid == Role.ENGINE_GLOW
    if not glow.any():
        return

    engine = grid == Role.ENGINE

    # Neighbor-of-glow mask via in-plane shifts at the same z.
    neigh = np.zeros_like(glow)
    # +X neighbor of glow → cells at x+1 where (x,y,z) is glow.
    neigh[1:, :, :] |= glow[:-1, :, :]
    # −X neighbor of glow.
    neigh[:-1, :, :] |= glow[1:, :, :]
    # +Y neighbor of glow.
    neigh[:, 1:, :] |= glow[:, :-1, :]
    # −Y neighbor of glow.
    neigh[:, :-1, :] |= glow[:, 1:, :]

    mask = neigh & engine
    grid[mask] = Role.HULL_DARK


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


def _paint_belly_lights(
    grid: np.ndarray, surface: np.ndarray, params: TextureParams
) -> None:
    """LIGHT dots on the underside (−Y neighbor empty) of hull surface cells.

    Only HULL / HULL_DARK surface cells are eligible; protected roles
    (COCKPIT_GLASS, WINDOW, ENGINE, ENGINE_GLOW) are never overwritten.
    Lights are placed on a fully deterministic ``z % period == 0`` phase.
    """
    period = params.belly_light_period
    if period <= 0:
        return

    # Eligible: hull-like surface cell (HULL or HULL_DARK) on surface.
    eligible = surface & ((grid == Role.HULL) | (grid == Role.HULL_DARK))

    # Bottom-facing: the −Y neighbor is EMPTY or out of bounds.
    bottom_facing = np.ones_like(eligible)  # y == 0 → out of bounds → empty
    bottom_facing[:, 1:, :] = grid[:, :-1, :] == Role.EMPTY

    z_phase = _z_phase_mask(grid.shape, period)

    mask = eligible & bottom_facing & z_phase
    grid[mask] = Role.LIGHT


def _paint_nose_tip_light(grid: np.ndarray, params: TextureParams) -> None:
    """Place a LIGHT at the forward-most filled voxel on the nose centerline.

    If the width ``W`` is even there are two center columns (``W/2 - 1`` and
    ``W/2``); paint both to preserve bilateral symmetry. Protected roles
    (COCKPIT_GLASS, WINDOW, ENGINE, ENGINE_GLOW) are never overwritten.
    """
    if not params.nose_tip_light:
        return

    W, H, L = grid.shape
    if W == 0 or H == 0 or L == 0:
        return

    if W % 2 == 1:
        center_xs = (W // 2,)
    else:
        center_xs = (W // 2 - 1, W // 2)

    for x in center_xs:
        col = grid[x, :, :]  # shape (H, L)
        filled = col != Role.EMPTY
        if not filled.any():
            continue
        # Forward-most z with any filled voxel in this column.
        z_tip = int(np.argwhere(filled.any(axis=0))[:, 0].max())
        # Pick the topmost filled voxel at that z (arbitrary but deterministic).
        ys = np.argwhere(filled[:, z_tip])[:, 0]
        if ys.size == 0:
            continue
        y_tip = int(ys.max())
        if grid[x, y_tip, z_tip] in _PROTECTED_ROLES:
            continue
        grid[x, y_tip, z_tip] = Role.LIGHT
