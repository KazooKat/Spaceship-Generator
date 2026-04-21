"""Tests for EngineStyle builders.

These cover library-level contract only — no generator/web/CLI plumbing
yet, since :mod:`engine_styles` is not wired into
:func:`generate_shape` at the time this module was authored.

Contract under test:

* Every style emits at least one placement for a reasonably sized grid.
* Every placement is in-bounds for the input grid.
* Every placement's role is an engine role (``ENGINE`` or
  ``ENGINE_GLOW``) — no wing / hull bleed.
* Determinism: same seed → byte-identical placement list.
* Each style produces a silhouette distinguishable from the others.
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.engine_styles import (
    EngineStyle,
    build_engines,
    build_ion_array,
    build_quad_cluster,
    build_ring,
    build_single_core,
    build_twin_nacelle,
)
from spaceship_generator.palette import Role

# --- Enum ------------------------------------------------------------------


def test_engine_style_values_stable():
    """Wire-format values ship in future form posts / /api/meta. Renaming
    any of them is a breaking change."""
    assert {e.value for e in EngineStyle} == {
        "single_core",
        "twin_nacelle",
        "quad_cluster",
        "ring",
        "ion_array",
    }


def test_engine_style_has_at_least_five_members():
    assert len(list(EngineStyle)) >= 5


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def grid() -> np.ndarray:
    """A comfortably sized empty grid so every style fits."""
    return np.zeros((20, 14, 30), dtype=np.int16)


@pytest.fixture
def small_grid() -> np.ndarray:
    """A tight grid that stresses the bounds-clipping logic."""
    return np.zeros((8, 6, 10), dtype=np.int16)


def _rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


# --- Per-style smoke tests -------------------------------------------------


@pytest.mark.parametrize("style", list(EngineStyle))
def test_each_style_builds_without_error(grid, style):
    placements = build_engines(
        grid,
        style,
        position=(grid.shape[0] // 2, grid.shape[1] // 2, 0),
        size=(2, 4, 4),
        rng=_rng(1),
    )
    assert isinstance(placements, list)
    assert len(placements) > 0, f"style {style.value} produced no placements"


@pytest.mark.parametrize("style", list(EngineStyle))
def test_each_style_stays_in_bounds(grid, style):
    W, H, L = grid.shape
    placements = build_engines(
        grid,
        style,
        position=(W // 2, H // 2, 0),
        size=(2, 4, 4),
        rng=_rng(2),
    )
    for x, y, z, _role in placements:
        assert 0 <= x < W, f"x={x} out of bounds [0, {W}) for style {style.value}"
        assert 0 <= y < H, f"y={y} out of bounds [0, {H}) for style {style.value}"
        assert 0 <= z < L, f"z={z} out of bounds [0, {L}) for style {style.value}"


@pytest.mark.parametrize("style", list(EngineStyle))
def test_each_style_uses_only_engine_roles(grid, style):
    placements = build_engines(
        grid,
        style,
        position=(grid.shape[0] // 2, grid.shape[1] // 2, 0),
        size=(2, 4, 4),
        rng=_rng(3),
    )
    allowed = {Role.ENGINE, Role.ENGINE_GLOW}
    for _x, _y, _z, role in placements:
        assert role in allowed, (
            f"style {style.value} emitted non-engine role {role!r}"
        )


@pytest.mark.parametrize("style", list(EngineStyle))
def test_each_style_respects_small_grid_bounds(small_grid, style):
    """Tight grids + bigger requested size must not overflow."""
    W, H, L = small_grid.shape
    placements = build_engines(
        small_grid,
        style,
        position=(W // 2, H // 2, 0),
        size=(3, 5, 4),  # intentionally roomy vs. the grid
        rng=_rng(4),
    )
    for x, y, z, _role in placements:
        assert 0 <= x < W and 0 <= y < H and 0 <= z < L, (
            f"style {style.value} wrote {(x, y, z)} outside grid {small_grid.shape}"
        )


# --- Determinism -----------------------------------------------------------


@pytest.mark.parametrize("style", list(EngineStyle))
def test_each_style_is_deterministic(grid, style):
    """Same inputs → same output, byte-for-byte. This is load-bearing for
    reproducible ship seeds down the line."""
    pos = (grid.shape[0] // 2, grid.shape[1] // 2, 0)
    sz = (2, 4, 4)
    a = build_engines(grid, style, position=pos, size=sz, rng=_rng(42))
    b = build_engines(grid, style, position=pos, size=sz, rng=_rng(42))
    assert a == b, f"style {style.value} is non-deterministic under fixed seed"


def test_ion_array_uses_rng(grid):
    """ION_ARRAY is the only style that consumes rng for per-block jitter.
    Different seeds should (usually) produce different placements."""
    pos = (grid.shape[0] // 2, grid.shape[1] // 2, 0)
    sz = (2, 5, 6)
    a = build_engines(grid, EngineStyle.ION_ARRAY, position=pos, size=sz, rng=_rng(1))
    b = build_engines(grid, EngineStyle.ION_ARRAY, position=pos, size=sz, rng=_rng(999))
    # Very small chance of collision; over many seeds this would diverge.
    # If this test is flaky on a new jitter rule, widen the seed space
    # rather than weakening the assertion.
    assert a != b, "ION_ARRAY ignored rng or collided across two very different seeds"


# --- Cross-style distinctness ----------------------------------------------


def test_styles_produce_distinct_placements(grid):
    """Each style must produce a silhouette different from every other,
    otherwise two enum members collapse into the same visual."""
    pos = (grid.shape[0] // 2, grid.shape[1] // 2, 0)
    sz = (2, 4, 4)
    out = {
        style: frozenset(
            build_engines(grid, style, position=pos, size=sz, rng=_rng(7))
        )
        for style in EngineStyle
    }
    styles = list(EngineStyle)
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            a, b = styles[i], styles[j]
            assert out[a] != out[b], (
                f"{a.value} and {b.value} produced identical placements"
            )


# --- Per-style structural sanity -------------------------------------------


def test_single_core_is_centered(grid):
    placements = build_single_core(
        grid, (grid.shape[0] // 2, grid.shape[1] // 2, 0), (2, 3, 0), _rng(0)
    )
    cx = grid.shape[0] // 2
    # Every emitted X must be within the radius+1 window around center.
    for x, _y, _z, _role in placements:
        assert abs(x - cx) <= 3, f"single_core cell at x={x} not near center {cx}"


def test_twin_nacelle_has_two_x_lobes(grid):
    placements = build_twin_nacelle(
        grid, (grid.shape[0] // 2, grid.shape[1] // 2, 0), (2, 3, 4), _rng(0)
    )
    cx = grid.shape[0] // 2
    left = [p for p in placements if p[0] < cx]
    right = [p for p in placements if p[0] > cx]
    assert left and right, "twin_nacelle must populate both sides of center"


def test_quad_cluster_has_four_quadrants(grid):
    placements = build_quad_cluster(
        grid, (grid.shape[0] // 2, grid.shape[1] // 2, 0), (2, 3, 4), _rng(0)
    )
    cx, cy = grid.shape[0] // 2, grid.shape[1] // 2
    quads = {
        (int(x > cx), int(y > cy))
        for x, y, _z, _r in placements
        if x != cx and y != cy
    }
    # All four sign combinations should appear.
    assert quads == {(0, 0), (0, 1), (1, 0), (1, 1)}, (
        f"quad_cluster missing quadrants: {quads}"
    )


def test_ring_has_empty_center(grid):
    """RING's defining feature is that cells on the centerline are NOT
    part of the engine — the center should have no placements from the
    annular fill."""
    placements = build_ring(
        grid, (grid.shape[0] // 2, grid.shape[1] // 2, 0), (2, 3, 0), _rng(0)
    )
    cx, cy = grid.shape[0] // 2, grid.shape[1] // 2
    engine_cells_at_center = [
        p for p in placements
        if p[0] == cx and p[1] == cy and p[3] == Role.ENGINE
    ]
    assert not engine_cells_at_center, (
        "ring style filled its own center with ENGINE — it should be hollow"
    )


def test_ion_array_spans_horizontally(grid):
    placements = build_ion_array(
        grid, (grid.shape[0] // 2, grid.shape[1] // 2, 0), (1, 3, 5), _rng(0)
    )
    xs = {p[0] for p in placements}
    # Expect multiple distinct X values across the row.
    assert len(xs) >= 3, f"ion_array produced only {len(xs)} distinct X positions"


# --- build_engines dispatch ------------------------------------------------


def test_build_engines_rejects_unknown_style(grid):
    """The dispatch falls through to a ValueError if someone passes a
    value the dispatch map doesn't know about. The enum validation at
    call sites prevents this in normal use, so we synthesize a fake."""

    class FakeStyle:
        value = "not-a-style"

        def __repr__(self) -> str:  # pragma: no cover - cosmetic
            return "<FakeStyle not-a-style>"

    with pytest.raises(ValueError, match="unknown EngineStyle"):
        build_engines(
            grid,
            FakeStyle(),  # type: ignore[arg-type]
            position=(5, 5, 0),
            size=(2, 3, 4),
            rng=_rng(0),
        )
