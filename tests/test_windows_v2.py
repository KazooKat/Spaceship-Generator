"""Tests for v2 window painting — single-row runs, no speckle."""

from __future__ import annotations

import numpy as np

from spaceship_generator.palette import Role
from spaceship_generator.texture import TextureParams, assign_roles


def _slab_grid(W: int = 10, H: int = 10, L: int = 20) -> np.ndarray:
    grid = np.full((W, H, L), Role.EMPTY, dtype=np.int8)
    grid[2:8, 2:8, 2:18] = Role.HULL
    return grid


def test_windows_share_single_row():
    out = assign_roles(_slab_grid(), TextureParams())
    windows = np.argwhere(out == Role.WINDOW)
    assert len(windows) > 0
    ys = {int(y) for y in windows[:, 1]}
    assert len(ys) == 1, f"windows must sit in one row, got rows {sorted(ys)}"


def test_window_runs_at_least_two_long():
    out = assign_roles(_slab_grid(), TextureParams())
    windows = np.argwhere(out == Role.WINDOW)
    assert len(windows) > 0
    # Group by (x, y); z values in each group must form runs of length >= 2.
    by_col: dict[tuple[int, int], list[int]] = {}
    for x, y, z in windows:
        by_col.setdefault((int(x), int(y)), []).append(int(z))
    for (x, _y), zs in by_col.items():
        zs = sorted(zs)
        run = 1
        runs: list[int] = []
        for a, b in zip(zs, zs[1:], strict=False):
            if b == a + 1:
                run += 1
            else:
                runs.append(run)
                run = 1
        runs.append(run)
        assert all(r >= 2 for r in runs), f"isolated window at x={x}: z-runs {runs}"


def test_windows_only_on_side_faces():
    out = assign_roles(_slab_grid(), TextureParams())
    windows = np.argwhere(out == Role.WINDOW)
    xs = {int(x) for x in windows[:, 0]}
    # Slab spans x in [2, 8); side faces are x == 2 and x == 7.
    assert xs <= {2, 7}, f"windows must be side-facing only, got x={sorted(xs)}"
