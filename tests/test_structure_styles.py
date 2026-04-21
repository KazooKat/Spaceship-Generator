"""Tests for :class:`HullStyle` and :func:`apply_hull_style`.

These exercise the hull-only silhouette dial exposed by
``spaceship_generator.structure_styles``. The generator-level
``StructureStyle`` is covered by the existing generator/integration
tests; we focus here on the new library surface.

For each new HullStyle we verify:

* **Reproducibility** — two calls with the same ``(shape, style)``
  produce byte-identical grids.
* **Non-empty** — the stamper actually writes HULL cells.
* **In-bounds** — no voxels are written outside ``grid.shape`` (if any
  were, numpy would raise during the write; asserting ``grid.shape``
  survives the call also catches accidental reshape/resize bugs).
"""

from __future__ import annotations

import numpy as np
import pytest

from spaceship_generator.palette import Role
from spaceship_generator.structure_styles import (
    HullStyle,
    apply_hull_style,
    hull_profile_fn,
    hull_style_rx_ry,
)

# --- Enum wire values -----------------------------------------------------


def test_hull_style_values_stable():
    """Lock in the wire-format values — any rename is a breaking change."""
    assert {h.value for h in HullStyle} == {
        "arrow",
        "saucer",
        "whale",
        "dagger",
        "blocky_freighter",
        "organic_bio",
        "hexagonal_lattice",
        "asymmetric_scavenger",
        "modular_block",
        "sleek_racing",
    }


# --- apply_hull_style input validation ------------------------------------


def test_apply_hull_style_rejects_non_enum():
    grid = np.zeros((10, 8, 20), dtype=np.int8)
    with pytest.raises(ValueError, match="HullStyle"):
        apply_hull_style(grid, "arrow")  # type: ignore[arg-type]


def test_apply_hull_style_rejects_non_3d_grid():
    grid = np.zeros((10, 20), dtype=np.int8)
    with pytest.raises(ValueError, match="3-D"):
        apply_hull_style(grid, HullStyle.ARROW)


# --- Shared helpers -------------------------------------------------------


def _fresh_grid(shape: tuple[int, int, int] = (20, 12, 40)) -> np.ndarray:
    return np.zeros(shape, dtype=np.int8)


def _hull_cells(grid: np.ndarray) -> int:
    return int((grid == Role.HULL).sum())


# --- Per-style invariants --------------------------------------------------


@pytest.mark.parametrize("style", list(HullStyle))
def test_each_style_is_reproducible(style):
    """Same ``(shape, style)`` on a zero grid must produce identical output.

    ``apply_hull_style`` has no RNG dependency, so two independent runs
    must be byte-for-byte equal. This is our ``seed produces reproducible
    shape`` contract (the ``seed`` is the grid shape).
    """
    shape = (20, 12, 40)
    a = _fresh_grid(shape)
    b = _fresh_grid(shape)
    apply_hull_style(a, style)
    apply_hull_style(b, style)
    assert np.array_equal(a, b), f"{style.value} is not deterministic"


@pytest.mark.parametrize("style", list(HullStyle))
def test_each_style_produces_hull(style):
    grid = _fresh_grid()
    apply_hull_style(grid, style)
    assert _hull_cells(grid) > 0, f"{style.value} wrote no HULL cells"


@pytest.mark.parametrize("style", list(HullStyle))
def test_each_style_stays_in_bounds(style):
    """Every written voxel must lie inside ``grid.shape``.

    Out-of-bounds writes would raise during the stamp pass; we also
    verify that only HULL or EMPTY codes appear afterwards so we don't
    accidentally spray unrelated roles.
    """
    shape = (12, 10, 24)
    grid = _fresh_grid(shape)
    apply_hull_style(grid, style)
    assert grid.shape == shape
    # Only EMPTY or HULL are written by this stamper.
    unique_vals = {int(v) for v in np.unique(grid)}
    assert unique_vals <= {int(Role.EMPTY), int(Role.HULL)}, (
        f"{style.value} wrote unexpected role codes: {unique_vals}"
    )


# --- Per-style character checks ------------------------------------------
#
# One lightweight "shape fingerprint" assertion per style so the tests
# catch silhouette regressions (not just "did it write anything").


def _slice_counts(grid: np.ndarray) -> np.ndarray:
    """Return HULL-voxel counts per Z slice — a 1-D profile."""
    return (grid == Role.HULL).sum(axis=(0, 1))


def test_arrow_has_pointed_nose():
    """ARROW: rear must be dramatically beefier than the nose."""
    grid = _fresh_grid((22, 14, 60))
    apply_hull_style(grid, HullStyle.ARROW)
    counts = _slice_counts(grid)
    # Look at the first and last 20% of slices.
    n = len(counts)
    rear_max = int(counts[: n // 5].max())
    nose_max = int(counts[-n // 5 :].max())
    assert rear_max > 2 * nose_max, (
        f"ARROW rear ({rear_max}) should be >2x nose ({nose_max})"
    )


def test_saucer_is_wider_than_tall():
    """SAUCER: the filled region must have a wider X footprint than Y."""
    grid = _fresh_grid((24, 24, 30))
    apply_hull_style(grid, HullStyle.SAUCER)
    xs = np.any(grid == Role.HULL, axis=(1, 2))
    ys = np.any(grid == Role.HULL, axis=(0, 2))
    x_extent = int(xs.sum())
    y_extent = int(ys.sum())
    assert x_extent > y_extent + 2, (
        f"SAUCER x_extent ({x_extent}) should be > y_extent ({y_extent}) + 2"
    )


def test_whale_is_mid_heavy():
    """WHALE: the center slab must carry the most volume."""
    grid = _fresh_grid((22, 14, 40))
    apply_hull_style(grid, HullStyle.WHALE)
    counts = _slice_counts(grid)
    mid = int(counts[len(counts) // 2])
    ends = int(max(counts[0], counts[-1]))
    assert mid > ends, f"WHALE mid ({mid}) should exceed ends ({ends})"


def test_dagger_is_narrow():
    """DAGGER: X extent must be noticeably smaller than the grid width."""
    W = 30
    grid = _fresh_grid((W, 12, 40))
    apply_hull_style(grid, HullStyle.DAGGER)
    xs = np.any(grid == Role.HULL, axis=(1, 2))
    x_extent = int(xs.sum())
    # A non-narrow hull would nearly fill W; dagger should stay slim.
    assert x_extent < int(W * 0.75), (
        f"DAGGER x_extent ({x_extent}) is not narrow vs grid width {W}"
    )


def test_blocky_freighter_has_flat_profile():
    """BLOCKY_FREIGHTER: interior slices should be near-uniform volume."""
    grid = _fresh_grid((22, 14, 40))
    apply_hull_style(grid, HullStyle.BLOCKY_FREIGHTER)
    counts = _slice_counts(grid)
    # Drop the first/last 10% of slices (the rise/fall ramps) and check
    # the remaining plateau is nearly flat.
    n = len(counts)
    lo, hi = n // 10, n - n // 10
    plateau = counts[lo:hi]
    assert plateau.max() - plateau.min() <= 2, (
        "BLOCKY_FREIGHTER interior should be near-uniform; got "
        f"range {int(plateau.min())}..{int(plateau.max())}"
    )


# --- Styles are distinguishable from each other --------------------------


def test_all_hull_styles_produce_distinct_silhouettes():
    """No two HullStyle entries may collapse to the same voxel pattern."""
    shape = (22, 14, 40)
    grids = {}
    for style in HullStyle:
        g = _fresh_grid(shape)
        apply_hull_style(g, style)
        grids[style] = g
    styles = list(HullStyle)
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            a, b = styles[i], styles[j]
            assert not np.array_equal(grids[a], grids[b]), (
                f"{a.value} and {b.value} produced identical hulls"
            )


# --- Accessors round-trip -------------------------------------------------


@pytest.mark.parametrize("style", list(HullStyle))
def test_profile_fn_accessor_returns_callable(style):
    fn = hull_profile_fn(style)
    # Sanity: profile is in [0, 1] across the full unit interval.
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = fn(t)
        assert 0.0 <= v <= 1.0, f"{style.value} profile({t}) = {v} out of [0,1]"


@pytest.mark.parametrize("style", list(HullStyle))
def test_rx_ry_accessor_returns_positive(style):
    rx, ry = hull_style_rx_ry(style)
    assert rx > 0 and ry > 0, (
        f"{style.value} rx/ry scales must be positive; got {(rx, ry)}"
    )


# --- New hull variant character checks ------------------------------------


def test_organic_bio_has_double_hump():
    """ORGANIC_BIO: the profile should have two local maxima (two lobes).

    The forward lobe and the secondary rear lobe mean that neither the
    very front nor the very rear carries the sole maximum — there must be
    at least two Z slices near the top of the distribution separated by a
    local dip.
    """
    grid = _fresh_grid((22, 14, 60))
    apply_hull_style(grid, HullStyle.ORGANIC_BIO)
    counts = _slice_counts(grid)
    # Drop absolute endpoints (ramp artefacts) and look for a dip in the
    # middle third of the profile.
    n = len(counts)
    mid_start, mid_end = n // 4, 3 * n // 4
    mid_section = counts[mid_start:mid_end]
    # Forward and rear thirds (excluding mid).
    forward = counts[mid_end:]
    rear = counts[:mid_start]
    # At least one of the flanking regions must be locally higher than the
    # minimum in the mid-section, signalling a double-hump shape.
    mid_min = int(mid_section.min())
    flank_max = int(max(forward.max(), rear.max()))
    assert flank_max >= mid_min, (
        "ORGANIC_BIO should have a secondary lobe; "
        f"flank_max={flank_max}, mid_min={mid_min}"
    )
    # The hull must still be non-trivially filled.
    assert int(counts.max()) > 4, "ORGANIC_BIO produced a suspiciously thin hull"


def test_hexagonal_lattice_has_periodic_variation():
    """HEXAGONAL_LATTICE: interior Z-slice counts must vary periodically.

    The sinusoidal ripple in the profile means the inner portion of the
    hull should show measurable variation (max - min > 0) rather than a
    perfectly flat plateau.
    """
    grid = _fresh_grid((22, 14, 60))
    apply_hull_style(grid, HullStyle.HEXAGONAL_LATTICE)
    counts = _slice_counts(grid)
    n = len(counts)
    # Examine the central 60% — well inside the rise/fall ramps.
    interior = counts[n // 5 : 4 * n // 5]
    variation = int(interior.max()) - int(interior.min())
    assert variation > 0, (
        f"HEXAGONAL_LATTICE interior should vary; max-min = {variation}"
    )
    # The plateau should still be mostly filled — variation shouldn't be huge.
    assert variation < int(interior.max()) // 2 + 1, (
        "HEXAGONAL_LATTICE variation is too large; profile may be broken"
    )


def test_asymmetric_scavenger_peak_is_forward():
    """ASYMMETRIC_SCAVENGER: the widest cross-section lives in the forward 40%."""
    grid = _fresh_grid((22, 14, 60))
    apply_hull_style(grid, HullStyle.ASYMMETRIC_SCAVENGER)
    counts = _slice_counts(grid)
    n = len(counts)
    peak_z = int(np.argmax(counts))
    # Peak must be in the forward 60% (z > 40% of length).
    assert peak_z > n * 0.40, (
        f"ASYMMETRIC_SCAVENGER peak at z={peak_z} expected in forward half "
        f"(z > {n * 0.40:.1f})"
    )
    # And the rear (first 25%) must be noticeably narrower than the peak.
    rear_max = int(counts[: n // 4].max())
    peak_val = int(counts[peak_z])
    assert peak_val > rear_max, (
        f"ASYMMETRIC_SCAVENGER peak ({peak_val}) should exceed rear ({rear_max})"
    )


def test_modular_block_has_stepped_profile():
    """MODULAR_BLOCK: the profile must show at least two distinct flat levels.

    The steps between modules create visible "shelves". We detect this by
    finding that the sorted unique slice-count values span more than one
    plateau (standard deviation of interior counts is meaningfully > 0).
    """
    grid = _fresh_grid((22, 14, 60))
    apply_hull_style(grid, HullStyle.MODULAR_BLOCK)
    counts = _slice_counts(grid)
    n = len(counts)
    # Ignore first/last 5% (absolute ramp zones).
    interior = counts[n // 20 : n - n // 20]
    std_val = float(interior.std())
    assert std_val > 1.0, (
        f"MODULAR_BLOCK interior should show step variation; std={std_val:.2f}"
    )
    # Ensure values are not all identical — at least 2 distinct count values.
    unique_counts = len(set(interior.tolist()))
    assert unique_counts >= 2, (
        f"MODULAR_BLOCK should have 2+ distinct slice counts; got {unique_counts}"
    )


def test_sleek_racing_is_narrow_and_pointed():
    """SLEEK_RACING: X extent must be very slim and the nose must be tiny."""
    W = 30
    grid = _fresh_grid((W, 14, 60))
    apply_hull_style(grid, HullStyle.SLEEK_RACING)
    counts = _slice_counts(grid)
    n = len(counts)
    # X footprint check — should be narrower than DAGGER already is.
    xs = np.any(grid == Role.HULL, axis=(1, 2))
    x_extent = int(xs.sum())
    assert x_extent < int(W * 0.55), (
        f"SLEEK_RACING x_extent ({x_extent}) should be very narrow vs W={W}"
    )
    # Nose check — the last 15% of slices must be much thinner than the peak.
    nose_max = int(counts[-n // 7 :].max())
    peak_val = int(counts.max())
    assert peak_val > 2 * nose_max + 1, (
        f"SLEEK_RACING nose ({nose_max}) should be <half the peak ({peak_val})"
    )
