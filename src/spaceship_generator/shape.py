"""Parts-based procedural ship shape generation.

Pipeline:

    hull  →  cockpit  →  engines  →  (maybe) wings  →  greebles  →  mirror on X

The grid is indexed ``grid[x, y, z]`` where:

* ``x`` = width (mirror axis — ship is bilaterally symmetric across ``x = W/2``)
* ``y`` = height (Minecraft Y-up)
* ``z`` = length — ``z = 0`` is the rear (engine end), ``z = L - 1`` is the nose

Values are integer :class:`Role` codes. Only coarse roles are set here
(``HULL``, ``COCKPIT_GLASS``, ``ENGINE``, ``WING``, ``GREEBLE``). Fine detailing
(windows, accent stripes, engine glow cores, running lights) is the job of
:mod:`spaceship_generator.texture`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from .palette import Role


class CockpitStyle(str, Enum):
    BUBBLE = "bubble"
    POINTED = "pointed"
    INTEGRATED = "integrated"


@dataclass
class ShapeParams:
    """User-tunable parameters for ship shape."""

    length: int = 40          # Z dimension (nose-to-tail)
    width_max: int = 20       # X dimension
    height_max: int = 12      # Y dimension
    engine_count: int = 2
    wing_prob: float = 0.75
    greeble_density: float = 0.05
    cockpit_style: CockpitStyle = CockpitStyle.BUBBLE

    def __post_init__(self) -> None:
        if self.length < 8:
            raise ValueError("length must be >= 8")
        if self.width_max < 4:
            raise ValueError("width_max must be >= 4")
        if self.height_max < 4:
            raise ValueError("height_max must be >= 4")
        if self.engine_count < 0 or self.engine_count > 6:
            raise ValueError("engine_count must be in [0, 6]")
        if not 0.0 <= self.wing_prob <= 1.0:
            raise ValueError("wing_prob must be in [0, 1]")
        if not 0.0 <= self.greeble_density <= 0.5:
            raise ValueError("greeble_density must be in [0, 0.5]")


def generate_shape(seed: int, params: ShapeParams | None = None) -> np.ndarray:
    """Return a ``(W, H, L)`` int8 array of :class:`Role` codes.

    Deterministic given ``seed`` and ``params``.
    """
    params = params or ShapeParams()
    rng = np.random.default_rng(seed)
    W, H, L = params.width_max, params.height_max, params.length
    grid = np.zeros((W, H, L), dtype=np.int8)

    _place_hull(grid, rng, params)
    _place_cockpit(grid, rng, params)
    _place_engines(grid, rng, params)
    if rng.random() < params.wing_prob:
        _place_wings(grid, rng, params)
    _place_greebles(grid, rng, params)
    _enforce_x_symmetry(grid)
    _connect_floaters(grid)
    _enforce_x_symmetry(grid)

    return grid


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def _place_hull(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Fill a tapered ellipsoid-of-revolution along Z with HULL voxels."""
    W, H, L = grid.shape
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0

    # Slight random thickness variation per axis so not every ship is identical.
    thickness = 0.9 + rng.random() * 0.1

    for z in range(L):
        t = z / max(L - 1, 1)          # 0 at rear, 1 at nose
        profile = _body_profile(t)     # [0..1] bell-ish
        rx = max(0.5, (W * 0.5 - 0.5) * profile * thickness)
        ry = max(0.5, (H * 0.5 - 0.5) * profile * thickness * 0.7)  # flatter than wide

        for x in range(W):
            for y in range(H):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.HULL


def _body_profile(t: float) -> float:
    """Taper profile along ship length.

    ``t = 0`` is the rear, ``t = 1`` is the nose. Peaks a little forward of
    the middle so the nose tapers more than the tail.
    """
    peak = 0.55
    sigma = 0.32
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    return max(0.0, min(1.0, f))


def _place_cockpit(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Attach a cockpit to the nose of the ship.

    Shape is controlled by ``params.cockpit_style``:

    * :attr:`CockpitStyle.BUBBLE` — small ellipsoidal bulge above the nose.
    * :attr:`CockpitStyle.POINTED` — tapered cone narrowing toward the nose.
    * :attr:`CockpitStyle.INTEGRATED` — flat strip along the upper-forward hull
      (no protrusion; just converts hull voxels to cockpit glass).
    """
    style = params.cockpit_style
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


def _place_engines(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Add N engine cylinders at the rear of the ship."""
    n = params.engine_count
    if n == 0:
        return
    W, H, L = grid.shape

    engine_length = max(2, L // 8)
    engine_radius = max(1, min(W, H) // 10)

    xs = _engine_x_positions(n, W, engine_radius)
    cy_engine = max(engine_radius + 1, H // 2 - 1)

    for ex in xs:
        for x in range(ex - engine_radius - 1, ex + engine_radius + 2):
            for y in range(cy_engine - engine_radius - 1, cy_engine + engine_radius + 2):
                for z in range(0, engine_length):
                    if not (0 <= x < W and 0 <= y < H and 0 <= z < L):
                        continue
                    dx = x - ex
                    dy = y - cy_engine
                    if dx * dx + dy * dy <= engine_radius * engine_radius:
                        grid[x, y, z] = Role.ENGINE


def _engine_x_positions(n: int, width: int, radius: int) -> list[int]:
    """Return engine X positions spread symmetrically across the ship width."""
    if n == 1:
        return [width // 2]
    cx = (width - 1) / 2.0
    half = n // 2
    usable = (width - 2 * radius - 2) / 2.0   # space to each side of center
    spacing = usable / max(half, 1)
    xs: list[int] = []
    for i in range(1, half + 1):
        offset = spacing * i
        xs.append(int(round(cx - offset)))
        xs.append(int(round(cx + offset)))
    if n % 2 == 1:
        xs.append(int(round(cx)))
    return xs


def _place_wings(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Flat slabs protruding from the hull on the X axis. Mirrored."""
    W, H, L = grid.shape
    wing_span = max(2, W // 5)
    wing_thickness = max(1, H // 10)
    wing_length = max(4, L // 3)
    # Guard: on very short ships ``L - wing_length`` may be <= 0, which would
    # collapse ``cz`` to 0 and truncate the wing. Clamp wing_length so the
    # wing still has a valid placement window.
    wing_length = max(2, min(wing_length, L - 1))
    cy = (H - 1) // 2
    cz = L // 3 + int(rng.integers(-L // 12, L // 12 + 1))
    cz = max(0, min(L - wing_length, cz))

    y_lo = cy - wing_thickness // 2
    y_hi = y_lo + wing_thickness

    # Left wing — right side is produced by the final mirror pass.
    for x in range(0, wing_span):
        for y in range(max(0, y_lo), min(H, y_hi + 1)):
            for z in range(cz, min(L, cz + wing_length)):
                grid[x, y, z] = Role.WING


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


def _enforce_x_symmetry(grid: np.ndarray) -> None:
    """Copy the left half onto the right half so the ship is X-symmetric."""
    W = grid.shape[0]
    half = W // 2
    for x in range(half):
        grid[W - 1 - x, :, :] = grid[x, :, :]


def _label_components(grid: np.ndarray) -> tuple[np.ndarray, int]:
    """Label each filled voxel with its 6-connected component id (-1 = empty).

    Returns ``(labels, n_components)``. Iteration order is fixed (x then y then
    z) so labeling is deterministic for a given input grid.
    """
    W, H, L = grid.shape
    filled = grid != Role.EMPTY
    labels = np.full((W, H, L), -1, dtype=np.int32)
    neigh = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    current = 0
    for x in range(W):
        for y in range(H):
            for z in range(L):
                if not filled[x, y, z] or labels[x, y, z] != -1:
                    continue
                labels[x, y, z] = current
                stack = [(x, y, z)]
                while stack:
                    cx, cy, cz = stack.pop()
                    for dx, dy, dz in neigh:
                        nx, ny, nz = cx + dx, cy + dy, cz + dz
                        if 0 <= nx < W and 0 <= ny < H and 0 <= nz < L:
                            if filled[nx, ny, nz] and labels[nx, ny, nz] == -1:
                                labels[nx, ny, nz] = current
                                stack.append((nx, ny, nz))
                current += 1
    return labels, current


def _draw_line_hull(grid: np.ndarray, a: tuple[int, int, int], b: tuple[int, int, int]) -> None:
    """Stamp :class:`Role.HULL` along a 6-connected path between ``a`` and ``b``.

    Empty voxels on the path are set to ``HULL``; already-filled voxels are left
    alone. The path moves axis-by-axis (x, then y, then z), guaranteeing
    6-connectivity.
    """
    x0, y0, z0 = a
    x1, y1, z1 = b
    x, y, z = x0, y0, z0
    W, H, L = grid.shape
    if 0 <= x < W and 0 <= y < H and 0 <= z < L and grid[x, y, z] == Role.EMPTY:
        grid[x, y, z] = Role.HULL
    sx = 1 if x1 >= x0 else -1
    while x != x1:
        x += sx
        if 0 <= x < W and grid[x, y, z] == Role.EMPTY:
            grid[x, y, z] = Role.HULL
    sy = 1 if y1 >= y0 else -1
    while y != y1:
        y += sy
        if 0 <= y < H and grid[x, y, z] == Role.EMPTY:
            grid[x, y, z] = Role.HULL
    sz = 1 if z1 >= z0 else -1
    while z != z1:
        z += sz
        if 0 <= z < L and grid[x, y, z] == Role.EMPTY:
            grid[x, y, z] = Role.HULL


def _connect_floaters(grid: np.ndarray) -> None:
    """Bridge disconnected voxel islands to the main component with HULL lines.

    After shape assembly, tapered-hull geometry can leave engines or wings
    floating free of the main body. This pass finds every 6-connected
    component, keeps the largest as the main body, and draws a straight HULL
    bridge from each floater to its nearest main-component voxel so the final
    ship is a single connected mass.
    """
    labels, n = _label_components(grid)
    if n <= 1:
        return

    sizes = np.zeros(n, dtype=np.int64)
    for label in range(n):
        sizes[label] = int((labels == label).sum())
    main_label = int(np.argmax(sizes))

    main_coords = np.argwhere(labels == main_label)
    if main_coords.size == 0:
        return

    for label in range(n):
        if label == main_label:
            continue
        float_coords = np.argwhere(labels == label)
        if float_coords.size == 0:
            continue

        order = np.lexsort((float_coords[:, 2], float_coords[:, 1], float_coords[:, 0]))
        seed_vox = tuple(int(v) for v in float_coords[order[0]])

        diffs = main_coords - np.array(seed_vox)
        dists = np.abs(diffs).sum(axis=1)
        min_d = int(dists.min())
        closest_mask = dists == min_d
        close_coords = main_coords[closest_mask]
        order2 = np.lexsort((close_coords[:, 2], close_coords[:, 1], close_coords[:, 0]))
        target_vox = tuple(int(v) for v in close_coords[order2[0]])

        _draw_line_hull(grid, seed_vox, target_vox)
