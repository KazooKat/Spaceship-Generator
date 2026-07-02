"""Tests for v2 greebles — clustered patches, no single-voxel scatter."""

from __future__ import annotations

import numpy as np

from spaceship_generator.palette import Role
from spaceship_generator.shape.blueprint import build_plan
from spaceship_generator.shape.core import ShapeParams
from spaceship_generator.shape.greebles import _place_greebles
from spaceship_generator.shape.hull import _place_hull

_NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _grid_with_greebles(seed: int = 42, density: float = 0.15):
    params = ShapeParams(greeble_density=density, wing_prob=0.0, engine_count=0)
    rng = np.random.default_rng(seed)
    plan = build_plan(rng, params, None)
    grid = np.zeros((params.width_max, params.height_max, params.length), dtype=np.int8)
    _place_hull(grid, rng, params, plan)
    _place_greebles(grid, rng, params, plan)
    return grid


def test_zero_density_places_no_greebles():
    grid = _grid_with_greebles(42, density=0.0)
    assert not (grid == Role.GREEBLE).any()


def test_greebles_exist_at_default_density():
    grid = _grid_with_greebles(42, density=0.15)
    assert (grid == Role.GREEBLE).any()


def test_no_isolated_greeble_voxels():
    """Every GREEBLE voxel is part of a cluster: it has a GREEBLE neighbor
    or sits in a structured motif (>= 2 filled 6-neighbors)."""
    grid = _grid_with_greebles(42, density=0.2)
    W, H, L = grid.shape
    for x, y, z in np.argwhere(grid == Role.GREEBLE):
        greeble_neighbors = 0
        filled_neighbors = 0
        for dx, dy, dz in _NEIGHBORS:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < W and 0 <= ny < H and 0 <= nz < L:
                v = grid[nx, ny, nz]
                if v == Role.GREEBLE:
                    greeble_neighbors += 1
                if v != Role.EMPTY:
                    filled_neighbors += 1
        assert greeble_neighbors >= 1 or filled_neighbors >= 2, (
            f"isolated greeble voxel at {(int(x), int(y), int(z))}"
        )


def test_greebles_touch_hull():
    """No floating greebles: every greeble cluster touches the hull."""
    grid = _grid_with_greebles(42, density=0.2)
    W, H, L = grid.shape
    # BFS from hull through greebles: every greeble must be reachable.
    from collections import deque

    hull_adjacent = set()
    q = deque()
    for x, y, z in np.argwhere(grid == Role.GREEBLE):
        for dx, dy, dz in _NEIGHBORS:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < W and 0 <= ny < H and 0 <= nz < L:
                if grid[nx, ny, nz] == Role.HULL:
                    hull_adjacent.add((int(x), int(y), int(z)))
                    q.append((int(x), int(y), int(z)))
                    break
    seen = set(hull_adjacent)
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in _NEIGHBORS:
            n = (x + dx, y + dy, z + dz)
            if n in seen:
                continue
            if 0 <= n[0] < W and 0 <= n[1] < H and 0 <= n[2] < L:
                if grid[n[0], n[1], n[2]] == Role.GREEBLE:
                    seen.add(n)
                    q.append(n)
    total = int((grid == Role.GREEBLE).sum())
    assert len(seen) == total, "some greeble voxels are unreachable from hull"


def test_greebles_deterministic():
    a = _grid_with_greebles(7)
    b = _grid_with_greebles(7)
    assert np.array_equal(a, b)
