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

    Returns ``(labels, n_components)``. Labels are assigned in a deterministic
    order: the first component encountered in x-then-y-then-z scan order
    receives id 0, the next gets id 1, and so on — matching the original
    pure-Python DFS labeling up to equality of the *set* of label values.

    Implementation: a fully-vectorized label-propagation pass.

    * Pass 1 assigns every filled voxel a unique provisional id in scan
      order via ``cumsum`` on the boolean mask.
    * Pass 2 enumerates all (lo, hi) neighbor-pair equivalences along x,
      y, z with pure numpy slicing, then repeatedly lowers parent ids
      toward the smaller endpoint with ``np.minimum.at`` followed by a
      path-halving sweep ``parent = parent[parent]``. Every step is a
      numpy ufunc over the pair arrays — no Python loop walks individual
      voxels. Converges in O(diameter) iterations, which is ~log(n) for
      ship-shaped grids.
    * Pass 3 remaps the union-find roots to dense 0..k-1 labels in scan
      order so downstream callers that iterate ``for label in range(n)``
      continue to work.

    This replaces the original iterative DFS, which did per-cell
    ``ndarray.__getitem__`` plus per-neighbor bounds checks inside a pure
    Python loop.
    """
    W, H, L = grid.shape
    filled = grid != Role.EMPTY
    labels = np.full((W, H, L), -1, dtype=np.int32)

    if not filled.any():
        return labels, 0

    # --- Pass 1: provisional labeling ---
    filled_flat = filled.ravel()
    # ``prov[i]`` = 0-based provisional id for each filled voxel in scan
    # order. Empty cells get whatever cumsum produces there; we never read
    # those positions below, so masking is unnecessary.
    prov_flat = (np.cumsum(filled_flat) - 1).astype(np.int32)
    prov = prov_flat.reshape(W, H, L)
    # Highest provisional id + 1 == number of filled voxels.
    n_filled = int(prov_flat[-1]) + 1 if filled_flat[-1] else int(prov_flat.max()) + 1

    # --- Pass 2: enumerate all equivalence pairs along each axis ---
    lo_parts: list[np.ndarray] = []
    hi_parts: list[np.ndarray] = []
    both = filled[:-1, :, :] & filled[1:, :, :]
    if both.any():
        a = prov[:-1, :, :][both]
        b = prov[1:, :, :][both]
        lo_parts.append(np.minimum(a, b))
        hi_parts.append(np.maximum(a, b))
    both = filled[:, :-1, :] & filled[:, 1:, :]
    if both.any():
        a = prov[:, :-1, :][both]
        b = prov[:, 1:, :][both]
        lo_parts.append(np.minimum(a, b))
        hi_parts.append(np.maximum(a, b))
    both = filled[:, :, :-1] & filled[:, :, 1:]
    if both.any():
        a = prov[:, :, :-1][both]
        b = prov[:, :, 1:][both]
        lo_parts.append(np.minimum(a, b))
        hi_parts.append(np.maximum(a, b))

    parent = np.arange(n_filled, dtype=np.int32)

    if lo_parts:
        lo = np.concatenate(lo_parts)
        hi = np.concatenate(hi_parts)

        # Iterative propagation. Each round:
        #   1. Scatter ``min(parent[lo], parent[hi])`` onto both endpoints
        #      using np.minimum.at (handles duplicate indices correctly).
        #   2. Path-halving: parent = parent[parent] until fixed point.
        # Terminates when parent[lo] == parent[hi] for every pair.
        #
        # All operations are single numpy calls over arrays of size
        # ``n_pairs`` or ``n_filled`` — no Python per-voxel loop.
        for _ in range(64):  # hard cap; ship grids converge in ~3-6 rounds
            pa = parent[lo]
            pb = parent[hi]
            m = np.minimum(pa, pb)
            np.minimum.at(parent, lo, m)
            np.minimum.at(parent, hi, m)
            # Path-halving sweep until parent is a fixed point.
            while True:
                nxt = parent[parent]
                if np.array_equal(nxt, parent):
                    break
                parent = nxt
            if np.array_equal(parent[lo], parent[hi]):
                break

    # --- Pass 3: dense renumbering in scan order ---
    # Because every union lowered parent values toward the smaller
    # endpoint, each component's root is the smallest provisional id in
    # it — i.e. the component's first voxel in scan order. np.unique
    # returns unique values ascending, which therefore matches scan order.
    _roots, dense = np.unique(parent, return_inverse=True)
    dense_scan = dense.astype(np.int32, copy=False)

    labels_flat = labels.ravel()
    filled_idx = np.flatnonzero(filled_flat)
    labels_flat[filled_idx] = dense_scan

    return labels, int(_roots.size)


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
