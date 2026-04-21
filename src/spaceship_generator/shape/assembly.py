"""Post-placement passes: X-mirror symmetry, connected-component labeling,
and bridging floating voxel islands back to the main body.
"""

from __future__ import annotations

import numpy as np

from ..palette import Role


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
