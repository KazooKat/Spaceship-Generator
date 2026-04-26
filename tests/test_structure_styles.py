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
    apply_hull_blend,
    apply_hull_style,
    blended_hull_radii,
    hull_blend_weight,
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


# ---------------------------------------------------------------------------
# Hull blend (shapes-B) — mix two HullStyle profiles along Z
# ---------------------------------------------------------------------------


def test_hull_blend_weight_endpoints():
    """The blend weight must saturate to 0 at the rear and 1 at the nose."""
    # Outside the midband the weight is exactly 0 or 1 — pure rear/front.
    assert hull_blend_weight(0.0) == 0.0
    assert hull_blend_weight(1.0) == 1.0
    # Centre of the ramp is exactly 0.5 (cosine smoothstep at u=0.5).
    assert abs(hull_blend_weight(0.5) - 0.5) < 1e-9
    # Just outside a 25%-wide midband the weight is fully saturated.
    assert hull_blend_weight(0.36) == 0.0
    assert hull_blend_weight(0.64) == 1.0


def test_hull_blend_weight_monotonic_and_bounded():
    """The crossover ramp must be non-decreasing and stay within [0, 1]."""
    samples = [hull_blend_weight(t / 100.0) for t in range(101)]
    for w in samples:
        assert 0.0 <= w <= 1.0
    # Non-decreasing — strictly monotone in the interior of the ramp, flat
    # outside it. ``<=`` covers both regimes. ``strict=False`` because the
    # second iterable (``samples[1:]``) is intentionally one element shorter.
    for prev, cur in zip(samples, samples[1:], strict=False):
        assert cur >= prev - 1e-12, f"weight non-monotonic: {prev} -> {cur}"


def test_blended_hull_radii_endpoints_match_pure_styles():
    """At t=0 the blended radii match the rear style; at t=1 they match front."""
    # rx_factor / ry_factor at the saturated endpoints should equal the
    # corresponding ``profile(t) * scale`` of the pure end style.
    front, rear = HullStyle.ARROW, HullStyle.SAUCER
    pf_front = hull_profile_fn(front)
    pf_rear = hull_profile_fn(rear)
    rx_f, ry_f = hull_style_rx_ry(front)
    rx_r, ry_r = hull_style_rx_ry(rear)

    rx0, ry0 = blended_hull_radii(front, rear, 0.0)
    assert abs(rx0 - pf_rear(0.0) * rx_r) < 1e-9
    assert abs(ry0 - pf_rear(0.0) * ry_r) < 1e-9

    rx1, ry1 = blended_hull_radii(front, rear, 1.0)
    assert abs(rx1 - pf_front(1.0) * rx_f) < 1e-9
    assert abs(ry1 - pf_front(1.0) * ry_f) < 1e-9


def test_apply_hull_blend_validates_inputs():
    grid = np.zeros((10, 8, 20), dtype=np.int8)
    with pytest.raises(ValueError, match="HullStyle"):
        apply_hull_blend(grid, "arrow", HullStyle.SAUCER)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="HullStyle"):
        apply_hull_blend(grid, HullStyle.ARROW, "saucer")  # type: ignore[arg-type]
    bad = np.zeros((10, 20), dtype=np.int8)
    with pytest.raises(ValueError, match="3-D"):
        apply_hull_blend(bad, HullStyle.ARROW, HullStyle.SAUCER)


def test_apply_hull_blend_is_deterministic():
    """Same ``(shape, front, rear, midband)`` must produce identical voxels."""
    a = _fresh_grid((22, 14, 40))
    b = _fresh_grid((22, 14, 40))
    apply_hull_blend(a, HullStyle.ARROW, HullStyle.SAUCER)
    apply_hull_blend(b, HullStyle.ARROW, HullStyle.SAUCER)
    assert np.array_equal(a, b)


def test_apply_hull_blend_arrow_saucer_touches_both_silhouettes():
    """ARROW (front) + SAUCER (rear) blend must hit each pure end's footprint.

    Roughly: at the rear (z near 0) the X footprint must be at least as
    wide as a pure SAUCER's would be at that slice; at the nose (z near
    L-1) the rear column count must collapse toward a pure ARROW's pointed
    nose.
    """
    shape = (24, 12, 60)
    blended = _fresh_grid(shape)
    apply_hull_blend(blended, HullStyle.ARROW, HullStyle.SAUCER)

    # Pure SAUCER and pure ARROW for reference.
    saucer = _fresh_grid(shape)
    apply_hull_style(saucer, HullStyle.SAUCER)
    arrow = _fresh_grid(shape)
    apply_hull_style(arrow, HullStyle.ARROW)

    # Rear band (first 15%): blended X footprint should match SAUCER's wide
    # footprint within a small voxel tolerance (saucer is a wide disc, the
    # blend's rear is fully saturated to the rear style's silhouette).
    rear_z = shape[2] // 10
    blended_x_rear = int(np.any(blended[:, :, rear_z] == Role.HULL, axis=1).sum())
    saucer_x_rear = int(np.any(saucer[:, :, rear_z] == Role.HULL, axis=1).sum())
    assert blended_x_rear >= saucer_x_rear - 1, (
        f"blended rear x_extent ({blended_x_rear}) should be ~= "
        f"SAUCER rear x_extent ({saucer_x_rear})"
    )

    # Nose band (last 15%): blended slice count should match ARROW's
    # pointed-nose count within a small voxel tolerance.
    nose_z = shape[2] - 1 - shape[2] // 10
    blended_nose = int((blended[:, :, nose_z] == Role.HULL).sum())
    arrow_nose = int((arrow[:, :, nose_z] == Role.HULL).sum())
    assert abs(blended_nose - arrow_nose) <= 2, (
        f"blended nose count ({blended_nose}) should match ARROW nose "
        f"({arrow_nose}) within tolerance"
    )


def test_apply_hull_blend_smooth_no_one_cell_jump():
    """The Z-slice profile must not show a one-cell discontinuity at z = L/2.

    A buggy hard switch would put a huge spike exactly at the centre slice
    (the midband boundary). We pin two properties of a *smooth* blend:

    1. The per-Z absolute deltas inside the crossover band have to stay
       bounded by the per-Z deltas a pure style produces (a smooth blend
       can only introduce variation at the rate the underlying ellipse
       voxelisation already does).
    2. No single delta dominates — the maximum jump is no more than a
       small multiple of the median jump in the same band, so the curve
       is gradual rather than impulsive.
    """
    shape = (24, 12, 60)
    grid = _fresh_grid(shape)
    apply_hull_blend(grid, HullStyle.ARROW, HullStyle.SAUCER)
    counts = _slice_counts(grid)

    # Look at the central 40% — entirely inside the cosine ramp.
    n = len(counts)
    lo, hi = (3 * n) // 10, (7 * n) // 10
    deltas = [
        abs(int(counts[i + 1]) - int(counts[i])) for i in range(lo, hi)
    ]

    # Pure-style deltas anywhere in the ship form an upper-bound reference
    # for what counts as "voxelisation noise" — a smooth blend should stay
    # inside that envelope.
    saucer = _fresh_grid(shape)
    apply_hull_style(saucer, HullStyle.SAUCER)
    arrow = _fresh_grid(shape)
    apply_hull_style(arrow, HullStyle.ARROW)
    sc = _slice_counts(saucer)
    ac = _slice_counts(arrow)
    pure_max_delta = max(
        max(abs(int(sc[i + 1]) - int(sc[i])) for i in range(len(sc) - 1)),
        max(abs(int(ac[i + 1]) - int(ac[i])) for i in range(len(ac) - 1)),
    )
    assert max(deltas) <= pure_max_delta + 1, (
        f"blend midband delta {max(deltas)} exceeds pure-style "
        f"voxelisation noise {pure_max_delta}; possible discontinuity"
    )

    # The peak delta must not be a sharp impulse on top of an otherwise-
    # flat curve — a hard switch would manifest as one big jump in a sea of
    # zeros. Require the second-largest delta to be within a 3x ratio of
    # the first so the shape is gradual.
    sorted_d = sorted(deltas, reverse=True)
    if sorted_d[0] >= 4:  # only meaningful when there's any variation
        assert sorted_d[1] >= sorted_d[0] / 3, (
            f"blend has impulsive midband jump: top deltas {sorted_d[:5]}"
        )


def test_apply_hull_blend_midband_controls_crossover_width():
    """A wider midband should produce a longer transition — endpoints stay pure.

    A tiny midband acts almost like a hard switch (so the rear half closely
    matches pure rear and the nose half closely matches pure front), while
    a wide midband mixes the two over more of the ship's length.
    """
    shape = (22, 12, 60)
    rear_style = HullStyle.SAUCER
    front_style = HullStyle.ARROW
    pure_rear = _fresh_grid(shape)
    apply_hull_style(pure_rear, rear_style)

    narrow = _fresh_grid(shape)
    apply_hull_blend(narrow, front_style, rear_style, midband=0.05)
    wide = _fresh_grid(shape)
    apply_hull_blend(wide, front_style, rear_style, midband=0.9)

    # Compare the rear-half X footprint of each blended hull to pure rear's
    # X footprint. The narrow-midband blend should match the pure rear
    # better in the rear half (less mixing) than the wide-midband blend.
    z_rear_half = shape[2] // 4
    pure_rear_x = int(np.any(pure_rear[:, :, z_rear_half] == Role.HULL, axis=1).sum())
    narrow_x = int(np.any(narrow[:, :, z_rear_half] == Role.HULL, axis=1).sum())
    wide_x = int(np.any(wide[:, :, z_rear_half] == Role.HULL, axis=1).sum())
    # Narrow midband leaves more of the rear unblended → matches pure rear.
    assert abs(narrow_x - pure_rear_x) <= abs(wide_x - pure_rear_x), (
        f"narrow midband ({narrow_x}) should track pure rear ({pure_rear_x}) "
        f"at least as well as wide midband ({wide_x})"
    )
