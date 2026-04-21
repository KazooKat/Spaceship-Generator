"""Correctness regression tests for the vectorized ``_label_components``.

These tests pin down the semantics the original pure-Python DFS guaranteed,
so the numpy/union-find rewrite cannot silently break downstream callers.
They exercise three structural cases that are easy to reason about by hand:

1. a single connected component
2. several disjoint components of different sizes
3. a hollow shell whose exterior and interior are not connected

All grids are built from fixed-shape numpy arrays (no generator output) so
the tests are fully deterministic and fast.
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.shape import _label_components


def _check_labels_valid(grid: np.ndarray, labels: np.ndarray, n: int) -> None:
    """Invariants every valid labeling must satisfy, regardless of id order."""
    filled = grid != Role.EMPTY
    # Shape + dtype contract.
    assert labels.shape == grid.shape
    assert labels.dtype == np.int32
    # Empty cells are always -1.
    assert np.all(labels[~filled] == -1)
    # Filled cells never carry -1.
    assert np.all(labels[filled] != -1)
    # Label ids are a contiguous 0..n-1 range.
    if n == 0:
        assert not filled.any()
    else:
        unique = np.unique(labels[filled])
        assert unique.tolist() == list(range(n))


def test_label_components_single_component():
    """A solid 3x3x3 block is a single 6-connected component."""
    grid = np.full((3, 3, 3), Role.HULL, dtype=np.int8)
    labels, n = _label_components(grid)

    assert n == 1
    _check_labels_valid(grid, labels, n)
    # All 27 filled cells share the same label.
    assert np.all(labels == 0)


def test_label_components_many_disjoint_components():
    """Three non-touching blocks produce three components."""
    grid = np.zeros((10, 5, 5), dtype=np.int8)
    # Block A: 2x2x2 at the origin corner.
    grid[0:2, 0:2, 0:2] = Role.HULL
    # Block B: single voxel in the middle, separated by empty cells.
    grid[5, 2, 2] = Role.HULL
    # Block C: a 1x1x3 line near the far corner, no overlap/touching.
    grid[8:9, 4:5, 0:3] = Role.HULL

    labels, n = _label_components(grid)
    assert n == 3
    _check_labels_valid(grid, labels, n)

    # Each block must be internally homogeneous.
    block_a = labels[0:2, 0:2, 0:2]
    block_b = labels[5, 2, 2]
    block_c = labels[8:9, 4:5, 0:3]
    assert np.unique(block_a).size == 1
    assert np.unique(block_c).size == 1
    # And all three blocks must have *different* labels.
    labels_seen = {int(block_a[0, 0, 0]), int(block_b), int(block_c[0, 0, 0])}
    assert len(labels_seen) == 3


def test_label_components_hollow_shell_exterior_and_interior():
    """A hollow 5^3 cube with a 1-voxel interior cavity produces 2 components.

    The shell (6-connected) is one component; the single interior voxel is
    surrounded on all 6 sides by hull (so it is empty, not part of the shell)
    — but if we instead leave a hollow centre of empty cells and add one
    *filled* voxel inside, that interior voxel is its own component with no
    6-connected path to the shell.
    """
    grid = np.full((5, 5, 5), Role.HULL, dtype=np.int8)
    # Hollow out the 3x3x3 core so the 5^3 cube becomes a shell.
    grid[1:4, 1:4, 1:4] = Role.EMPTY
    # Drop a single filled voxel back into the dead-centre of the cavity.
    grid[2, 2, 2] = Role.HULL

    labels, n = _label_components(grid)
    assert n == 2
    _check_labels_valid(grid, labels, n)

    # The interior voxel must have a different label from any shell voxel.
    interior_label = int(labels[2, 2, 2])
    shell_label = int(labels[0, 0, 0])
    assert interior_label != shell_label
    # Sanity: the shell (5^3 - 3^3 = 98 voxels) is a single component.
    assert int((labels == shell_label).sum()) == 98
    # Sanity: the interior is exactly one voxel.
    assert int((labels == interior_label).sum()) == 1


# ---- Additional edge cases that catch common rewrite bugs ----

def test_label_components_empty_grid():
    """An all-empty grid labels as zero components and -1 everywhere."""
    grid = np.zeros((4, 4, 4), dtype=np.int8)
    labels, n = _label_components(grid)
    assert n == 0
    assert labels.shape == grid.shape
    assert labels.dtype == np.int32
    assert np.all(labels == -1)


def test_label_components_diagonal_neighbors_are_not_connected():
    """Face-adjacent only: diagonal neighbors must be two separate components.

    This pins 6-connectivity (vs 18- or 26-connectivity). Two voxels that
    share only an edge or a corner are NOT in the same component.
    """
    grid = np.zeros((3, 3, 3), dtype=np.int8)
    grid[0, 0, 0] = Role.HULL
    grid[1, 1, 1] = Role.HULL  # diagonal corner-neighbor only
    labels, n = _label_components(grid)
    assert n == 2
    _check_labels_valid(grid, labels, n)
    assert int(labels[0, 0, 0]) != int(labels[1, 1, 1])


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_label_components_line_along_each_axis_is_one_component(axis):
    """A straight line of filled voxels along x, y or z is one component."""
    shape = [3, 3, 3]
    shape[axis] = 5
    grid = np.zeros(tuple(shape), dtype=np.int8)
    sl: list[slice | int] = [0, 0, 0]
    sl[axis] = slice(0, shape[axis])
    # Put the line at a non-corner "row" so we also probe interior coords.
    if axis != 0:
        sl[0] = 1
    if axis != 1:
        sl[1] = 1
    if axis != 2:
        sl[2] = 1
    grid[tuple(sl)] = Role.HULL
    labels, n = _label_components(grid)
    assert n == 1
    _check_labels_valid(grid, labels, n)
