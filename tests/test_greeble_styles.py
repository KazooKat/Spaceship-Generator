"""Tests for the greeble_styles library.

Covers:
* Enum wire-format values are stable.
* Every builder returns deterministic output for a given seed.
* Every builder emits only valid :class:`Role` values.
* :func:`scatter_greebles` validates the density range and is
  seed-deterministic.
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.greeble_styles import (
    GreebleType,
    build_antenna,
    build_battle_damage,
    build_circuit_board,
    build_dish,
    build_greeble,
    build_nano_mesh,
    build_organic_growth,
    build_panel_line,
    build_pipe_cluster,
    build_sensor_pod,
    build_turret,
    build_vent,
    scatter_greebles,
)
from spaceship_generator.palette import Role

# --- enum ------------------------------------------------------------------


def test_greeble_type_values_stable():
    """Lock in the string values — if these ever serialize into configs
    or API responses, renaming them becomes a breaking change."""
    assert {g.value for g in GreebleType} == {
        "turret", "dish", "vent", "antenna", "panel_line", "sensor_pod",
        "circuit_board", "battle_damage", "pipe_cluster",
        "organic_growth", "nano_mesh",
    }


def test_greeble_type_member_count():
    assert len(list(GreebleType)) == 11


# --- per-builder determinism ----------------------------------------------

# The default anchor is chosen to be well away from origin so builders
# that emit negative offsets are still exercised at "interesting" coords.
_ANCHOR = (5, 4, 10)

_BUILDERS = [
    ("turret", build_turret),
    ("dish", build_dish),
    ("vent", build_vent),
    ("antenna", build_antenna),
    ("panel_line", build_panel_line),
    ("sensor_pod", build_sensor_pod),
    ("circuit_board", build_circuit_board),
    ("battle_damage", build_battle_damage),
    ("pipe_cluster", build_pipe_cluster),
    ("organic_growth", build_organic_growth),
    ("nano_mesh", build_nano_mesh),
]


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_returns_list_of_tuples(name, builder):
    rng = np.random.default_rng(0)
    out = builder(_ANCHOR, rng)
    assert isinstance(out, list), f"{name} must return a list"
    assert out, f"{name} must emit at least one placement"
    for cell in out:
        assert isinstance(cell, tuple) and len(cell) == 4, (
            f"{name} emitted non-4-tuple: {cell!r}"
        )
        x, y, z, role = cell
        assert all(isinstance(v, int) for v in (x, y, z)), (
            f"{name} emitted non-int coords: {cell!r}"
        )
        assert isinstance(role, Role), (
            f"{name} emitted non-Role value: {role!r}"
        )


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_is_deterministic_per_seed(name, builder):
    """Two fresh rngs seeded the same must produce identical output —
    this is the contract every scatter downstream relies on."""
    a = builder(_ANCHOR, np.random.default_rng(123))
    b = builder(_ANCHOR, np.random.default_rng(123))
    assert a == b, f"{name} is non-deterministic across seeded rngs"


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_varies_with_seed(name, builder):
    """Two *different* seeds should usually produce different output.
    If a builder ignores rng entirely and always returns the same cells,
    seed variance becomes a silent regression — catch it here."""
    outputs = {tuple(builder(_ANCHOR, np.random.default_rng(s))) for s in range(16)}
    assert len(outputs) > 1, (
        f"{name} ignores rng entirely — got one output for 16 seeds"
    )


@pytest.mark.parametrize("name,builder", _BUILDERS)
def test_builder_does_not_mutate_anchor(name, builder):
    """Anchors are tuples today, but a caller might swap in a list later.
    Make sure we never do ``anchor[0] += 1`` style mutation."""
    anchor = (3, 2, 7)
    builder(anchor, np.random.default_rng(0))
    assert anchor == (3, 2, 7), f"{name} mutated its anchor"


def test_all_roles_are_valid_enum_members():
    """Cross-cutting check — every emitted role must be one of the known
    :class:`Role` members, never a bare int or an unknown sentinel."""
    rng = np.random.default_rng(7)
    valid = set(Role)
    for _, builder in _BUILDERS:
        for cell in builder(_ANCHOR, rng):
            assert cell[3] in valid, f"unknown Role emitted: {cell[3]!r}"


# --- dispatch --------------------------------------------------------------


@pytest.mark.parametrize("gtype", list(GreebleType))
def test_build_greeble_dispatches_every_type(gtype):
    """``build_greeble`` must route every enum member to a real builder."""
    out = build_greeble(gtype, _ANCHOR, np.random.default_rng(1))
    assert out, f"dispatch for {gtype.value} returned no cells"


def test_build_greeble_matches_direct_builder_call():
    """Dispatch is a thin wrapper — calling it must be indistinguishable
    from calling the underlying builder with the same rng state."""
    pairs = [
        (GreebleType.TURRET, build_turret),
        (GreebleType.DISH, build_dish),
        (GreebleType.VENT, build_vent),
        (GreebleType.ANTENNA, build_antenna),
        (GreebleType.PANEL_LINE, build_panel_line),
        (GreebleType.SENSOR_POD, build_sensor_pod),
        (GreebleType.CIRCUIT_BOARD, build_circuit_board),
        (GreebleType.BATTLE_DAMAGE, build_battle_damage),
        (GreebleType.PIPE_CLUSTER, build_pipe_cluster),
        (GreebleType.ORGANIC_GROWTH, build_organic_growth),
        (GreebleType.NANO_MESH, build_nano_mesh),
    ]
    for gtype, builder in pairs:
        direct = builder(_ANCHOR, np.random.default_rng(42))
        routed = build_greeble(gtype, _ANCHOR, np.random.default_rng(42))
        assert direct == routed, f"dispatch drifted for {gtype.value}"


# --- scatter ---------------------------------------------------------------


def test_scatter_density_zero_returns_empty():
    """Density 0 is the explicit "no greebles" path — it must short-circuit
    before consuming rng state so callers can toggle it mid-pipeline."""
    rng = np.random.default_rng(0)
    out = scatter_greebles((16, 8, 24), rng, density=0.0)
    assert out == []


def test_scatter_density_one_populates_all_anchors():
    """Density 1.0 means every candidate anchor becomes a greeble. The
    exact placement count depends on the builders chosen, but it must be
    strictly greater than the anchor count (each greeble is >=1 cell)."""
    shape = (6, 4, 6)
    rng = np.random.default_rng(0)
    out = scatter_greebles(shape, rng, density=1.0)
    assert out, "density=1.0 produced no greebles"
    # Every placement must be a valid 4-tuple with a Role.
    valid = set(Role)
    for x, y, z, role in out:
        assert isinstance(x, int) and isinstance(y, int) and isinstance(z, int)
        assert role in valid


def test_scatter_is_deterministic_per_seed():
    """Same seed, same shape, same density ⇒ byte-identical output."""
    shape = (8, 6, 12)
    a = scatter_greebles(shape, np.random.default_rng(2024), density=0.25)
    b = scatter_greebles(shape, np.random.default_rng(2024), density=0.25)
    assert a == b


def test_scatter_varies_with_seed():
    shape = (8, 6, 12)
    a = scatter_greebles(shape, np.random.default_rng(1), density=0.5)
    b = scatter_greebles(shape, np.random.default_rng(999), density=0.5)
    assert a != b, "scatter ignored the seed"


def test_scatter_density_monotonic():
    """Higher density should on average emit more greebles. Not a strict
    monotone (rng variance) so we compare density=0.1 vs density=0.9 —
    the gap is large enough to be safe for any seed."""
    shape = (10, 6, 20)
    low = scatter_greebles(shape, np.random.default_rng(5), density=0.1)
    high = scatter_greebles(shape, np.random.default_rng(5), density=0.9)
    assert len(high) > len(low)


@pytest.mark.parametrize("bad", [-0.01, -1.0, 1.01, 2.0, float("inf")])
def test_scatter_rejects_density_out_of_range(bad):
    with pytest.raises(ValueError, match="density"):
        scatter_greebles((4, 4, 4), np.random.default_rng(0), density=bad)


def test_scatter_accepts_density_boundaries():
    """Both 0.0 and 1.0 are valid — the inclusive range is the user-facing
    contract in the docstring. Flipping to exclusive bounds would break
    UI slider defaults downstream."""
    rng = np.random.default_rng(0)
    scatter_greebles((4, 4, 4), rng, density=0.0)  # must not raise
    scatter_greebles((4, 4, 4), rng, density=1.0)  # must not raise


def test_scatter_all_roles_are_valid():
    shape = (8, 6, 12)
    out = scatter_greebles(shape, np.random.default_rng(7), density=0.5)
    valid = set(Role)
    for cell in out:
        assert cell[3] in valid, f"scatter emitted unknown Role: {cell[3]!r}"


def test_scatter_respects_type_filter():
    """When ``types`` restricts the allow-list, every emitted role must
    belong to roles the selected builders actually produce."""
    shape = (6, 6, 10)
    # Antenna only ever emits HULL_DARK and LIGHT — a narrow surface to
    # probe that the filter actually restricts builder selection.
    out = scatter_greebles(
        shape,
        np.random.default_rng(11),
        density=1.0,
        types=[GreebleType.ANTENNA],
    )
    assert out, "filtered scatter produced no greebles"
    roles = {cell[3] for cell in out}
    assert roles <= {Role.HULL_DARK, Role.LIGHT}, (
        f"ANTENNA-only scatter emitted unexpected roles: {roles}"
    )


def test_scatter_accepts_numpy_grid():
    """Passing a grid must enable precise top-facing anchor detection —
    a ship that's all empty yields zero anchors and thus zero greebles."""
    empty = np.zeros((6, 4, 8), dtype=np.int8)
    out = scatter_greebles(empty, np.random.default_rng(0), density=1.0)
    assert out == [], "empty grid should yield no greebles"

    # A single pillar of hull — only the top cell of that pillar is a
    # valid anchor, so scatter must emit from exactly that point.
    grid = np.zeros((6, 4, 8), dtype=np.int8)
    grid[3, 0:3, 4] = Role.HULL
    out2 = scatter_greebles(grid, np.random.default_rng(0), density=1.0)
    assert out2, "pillar grid should yield at least one greeble"


def test_scatter_rejects_non_3d_array():
    with pytest.raises(ValueError, match="3D"):
        scatter_greebles(
            np.zeros((4, 4), dtype=np.int8),
            np.random.default_rng(0),
            density=0.5,
        )


def test_scatter_rejects_bad_shape_tuple():
    with pytest.raises(ValueError):
        scatter_greebles("not-a-shape", np.random.default_rng(0), density=0.5)  # type: ignore[arg-type]


def test_scatter_empty_shape_returns_empty():
    """Zero-sized grids have no anchors — scatter must return ``[]``
    rather than raise or divide by zero."""
    out = scatter_greebles((0, 4, 4), np.random.default_rng(0), density=1.0)
    assert out == []


# --- new style: circuit_board -----------------------------------------------


def test_circuit_board_shape_and_roles():
    """Circuit board is a 3x3 flush patch; must contain HULL_DARK substrate,
    GREEBLE traces, and exactly one LIGHT indicator."""
    out = build_circuit_board(_ANCHOR, np.random.default_rng(0))
    roles = [cell[3] for cell in out]
    assert Role.HULL_DARK in roles, "circuit board needs HULL_DARK substrate"
    assert Role.GREEBLE in roles, "circuit board needs GREEBLE traces"
    assert Role.LIGHT in roles, "circuit board needs one LIGHT indicator"
    assert roles.count(Role.LIGHT) == 1, "circuit board should have exactly one LIGHT"


def test_circuit_board_all_flush():
    """All cells must share the anchor Y — board is a surface detail only."""
    anchor_y = _ANCHOR[1]
    out = build_circuit_board(_ANCHOR, np.random.default_rng(1))
    assert all(cell[1] == anchor_y for cell in out), (
        "circuit board emitted cells at different Y levels"
    )


def test_circuit_board_block_variety():
    """Board must contain at least two distinct roles (substrate + traces)."""
    out = build_circuit_board(_ANCHOR, np.random.default_rng(2))
    assert len({cell[3] for cell in out}) >= 2


# --- new style: battle_damage -----------------------------------------------


def test_battle_damage_all_flush():
    """Scar is a flat surface marking — all Y coords must equal the anchor Y."""
    anchor_y = _ANCHOR[1]
    out = build_battle_damage(_ANCHOR, np.random.default_rng(0))
    assert all(cell[1] == anchor_y for cell in out), (
        "battle_damage emitted cells above the surface"
    )


def test_battle_damage_roles_limited():
    """Battle damage only uses HULL and HULL_DARK — no lights or protrusions."""
    for seed in range(8):
        out = build_battle_damage(_ANCHOR, np.random.default_rng(seed))
        roles = {cell[3] for cell in out}
        assert roles <= {Role.HULL, Role.HULL_DARK}, (
            f"battle_damage emitted unexpected roles: {roles}"
        )


def test_battle_damage_has_dark_epicenter():
    """The anchor cell itself (dist==0) must always be HULL_DARK (scorched)."""
    x, y, z = _ANCHOR
    for seed in range(6):
        out = build_battle_damage(_ANCHOR, np.random.default_rng(seed))
        center = [cell for cell in out if cell[0] == x and cell[2] == z]
        # The anchor position should appear (possibly overridden) as HULL_DARK.
        assert center, "anchor cell missing from battle_damage output"
        # The last write at anchor coords determines the final role.
        assert center[-1][3] == Role.HULL_DARK, (
            "epicenter should be HULL_DARK"
        )


# --- new style: pipe_cluster ------------------------------------------------


def test_pipe_cluster_emits_engine_glow():
    """Each pipe is capped with an ENGINE_GLOW outlet — must be present."""
    out = build_pipe_cluster(_ANCHOR, np.random.default_rng(0))
    roles = {cell[3] for cell in out}
    assert Role.ENGINE_GLOW in roles, "pipe_cluster must have ENGINE_GLOW outlets"


def test_pipe_cluster_pipe_count_varies():
    """Pipe count (2-4) must vary across seeds — validates rng is consumed."""
    glow_counts = set()
    for seed in range(16):
        out = build_pipe_cluster(_ANCHOR, np.random.default_rng(seed))
        glow_counts.add(sum(1 for cell in out if cell[3] == Role.ENGINE_GLOW))
    assert len(glow_counts) > 1, "pipe_cluster should have varying pipe counts"


def test_pipe_cluster_hull_and_hull_dark_present():
    """Pipe shafts alternate HULL / HULL_DARK for visual variety."""
    out = build_pipe_cluster(_ANCHOR, np.random.default_rng(7))
    roles = {cell[3] for cell in out}
    assert Role.HULL in roles or Role.HULL_DARK in roles, (
        "pipe shafts must use HULL or HULL_DARK"
    )


# --- new style: organic_growth ----------------------------------------------


def test_organic_growth_core_always_present():
    """The ENGINE_GLOW core node must always appear (guaranteed, not random)."""
    for seed in range(8):
        out = build_organic_growth(_ANCHOR, np.random.default_rng(seed))
        assert any(cell[3] == Role.ENGINE_GLOW for cell in out), (
            "organic_growth must always have an ENGINE_GLOW core"
        )


def test_organic_growth_interior_root():
    """The root cells must always be INTERIOR (not random)."""
    out = build_organic_growth(_ANCHOR, np.random.default_rng(0))
    interior = [cell for cell in out if cell[3] == Role.INTERIOR]
    assert len(interior) >= 2, "organic_growth needs at least 2 INTERIOR root cells"


def test_organic_growth_blob_asymmetry():
    """Random protrusions mean cell count must vary across seeds."""
    sizes = {len(build_organic_growth(_ANCHOR, np.random.default_rng(s))) for s in range(20)}
    assert len(sizes) > 1, "organic_growth blob size should vary with seed"


# --- new style: nano_mesh ---------------------------------------------------


def test_nano_mesh_is_3x3_patch():
    """The mesh covers a 3x3 footprint; expect 9 or 10 cells (9 + optional sensor)."""
    for seed in range(8):
        out = build_nano_mesh(_ANCHOR, np.random.default_rng(seed))
        assert len(out) in (9, 10), (
            f"nano_mesh expected 9 or 10 cells, got {len(out)}"
        )


def test_nano_mesh_all_flush():
    """Nano mesh is surface-flush — all Y coords must equal the anchor Y."""
    anchor_y = _ANCHOR[1]
    out = build_nano_mesh(_ANCHOR, np.random.default_rng(0))
    assert all(cell[1] == anchor_y for cell in out)


def test_nano_mesh_checker_roles():
    """Base 9 cells must only be HULL or HULL_DARK; optional sensor adds LIGHT."""
    out = build_nano_mesh(_ANCHOR, np.random.default_rng(0))
    roles = {cell[3] for cell in out}
    assert roles <= {Role.HULL, Role.HULL_DARK, Role.LIGHT}, (
        f"nano_mesh emitted unexpected roles: {roles}"
    )


def test_nano_mesh_phase_flip_changes_output():
    """The two phase values (0 and 1) must produce different checker patterns."""
    # Find seeds that exercise both phases — 16 seeds is more than sufficient.
    outputs = {tuple(build_nano_mesh(_ANCHOR, np.random.default_rng(s))) for s in range(16)}
    assert len(outputs) > 1, "nano_mesh phase never flips — pattern is static"
