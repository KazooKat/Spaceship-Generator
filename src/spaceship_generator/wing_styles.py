"""Wing archetype styles for ship shape generation.

Each :class:`WingStyle` produces a distinct silhouette while reusing the
same placement box (``span``, ``thickness``, ``length``, ``cy``, ``cz``,
``y_lo``, ``y_hi``) supplied by :func:`spaceship_generator.shape._place_wings`.

Adding a new style is a two-step change:

1. Add an enum member below.
2. Add a private ``_place_<style>`` implementation and hook it into the
   dispatch in :func:`place_wings`.

Back-compat contract
--------------------
``WingStyle.STRAIGHT`` MUST reproduce the pre-WingStyle wing placement
byte-for-byte. Tests lock this in; changing ``_place_straight`` will
break determinism for every existing seed.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np

from .palette import Role


class WingStyle(StrEnum):
    """Planform / cross-section archetype for the ship's wings.

    * :attr:`STRAIGHT` — rectangular slab. Legacy default; byte-compat.
    * :attr:`SWEPT` — parallelogram; tip shifted rearward.
    * :attr:`DELTA` — triangular planform; wide root, narrow nose-ward.
    * :attr:`TAPERED` — straight leading edge, chord shrinks toward tip.
    * :attr:`GULL` — stepped dihedral; outer section rises outboard.
    * :attr:`SPLIT` — two thinner wings stacked with a vertical gap.
    """

    STRAIGHT = "straight"
    SWEPT = "swept"
    DELTA = "delta"
    TAPERED = "tapered"
    GULL = "gull"
    SPLIT = "split"


def place_wings(
    grid: np.ndarray,
    wing_style: WingStyle,
    *,
    span: int,
    thickness: int,
    length: int,
    cy: int,
    cz: int,
    y_lo: int,
    y_hi: int,
) -> None:
    """Fill left-side wing cells on ``grid`` for the chosen ``wing_style``.

    The caller is responsible for running the final mirror pass on X so
    the right-hand wing appears — this function only writes ``x < W / 2``.

    All styles are clipped to the grid bounds so pathologically small
    ``(span, thickness, length)`` inputs can't write out-of-bounds.
    """
    if wing_style == WingStyle.STRAIGHT:
        _place_straight(grid, span, length, y_lo, y_hi, cz)
    elif wing_style == WingStyle.SWEPT:
        _place_swept(grid, span, length, y_lo, y_hi, cz)
    elif wing_style == WingStyle.DELTA:
        _place_delta(grid, span, length, y_lo, y_hi, cz)
    elif wing_style == WingStyle.TAPERED:
        _place_tapered(grid, span, length, y_lo, y_hi, cz)
    elif wing_style == WingStyle.GULL:
        _place_gull(grid, span, thickness, length, y_lo, y_hi, cz)
    elif wing_style == WingStyle.SPLIT:
        _place_split(grid, span, thickness, length, cy, cz, length)
    else:  # pragma: no cover - unreachable given enum validation upstream
        raise ValueError(f"unknown WingStyle: {wing_style!r}")


# --- per-style placements ---------------------------------------------------


def _place_straight(
    grid: np.ndarray, span: int, length: int, y_lo: int, y_hi: int, cz: int,
) -> None:
    """Rectangular slab — pre-WingStyle behavior. DO NOT refactor without
    also regenerating byte-compat fixtures; every historical seed assumes
    exactly this cell write pattern."""
    W, H, L = grid.shape
    for x in range(0, span):
        for y in range(max(0, y_lo), min(H, y_hi + 1)):
            for z in range(cz, min(L, cz + length)):
                grid[x, y, z] = Role.WING


def _place_swept(
    grid: np.ndarray, span: int, length: int, y_lo: int, y_hi: int, cz: int,
) -> None:
    """Parallelogram; tip shifted rearward (toward z=0) by ~60% of span.

    Each x-slice is the same length as the root, just slid toward the
    engine end so the wing sweeps back as it extends outboard."""
    W, H, L = grid.shape
    sweep_back = max(1, int(round(span * 0.6)))
    denom = max(1, span - 1)
    for x in range(0, span):
        dz = int(round(x * sweep_back / denom))
        z_start = max(0, cz - dz)
        z_end = min(L, z_start + length)
        for y in range(max(0, y_lo), min(H, y_hi + 1)):
            for z in range(z_start, z_end):
                grid[x, y, z] = Role.WING


def _place_delta(
    grid: np.ndarray, span: int, length: int, y_lo: int, y_hi: int, cz: int,
) -> None:
    """Triangle in plan view. Width = ``span`` at rear (z=cz), shrinking to
    1 at the nose-side tip (z=cz+length). Produces the classic delta-wing
    silhouette when viewed from above."""
    W, H, L = grid.shape
    denom = max(1, length - 1)
    for z_off in range(length):
        z = cz + z_off
        if z >= L:
            break
        t = z_off / denom
        local_span = max(1, int(round(span * (1 - t))))
        for x in range(0, local_span):
            for y in range(max(0, y_lo), min(H, y_hi + 1)):
                grid[x, y, z] = Role.WING


def _place_tapered(
    grid: np.ndarray, span: int, length: int, y_lo: int, y_hi: int, cz: int,
) -> None:
    """Straight leading edge, chord shrinks with x. Root has full
    ``length``; tip has ~40% ``length``. Stays rooted at ``z=cz`` so the
    trailing edge slopes while the leading edge is straight."""
    W, H, L = grid.shape
    denom = max(1, span - 1)
    for x in range(0, span):
        t = x / denom
        local_length = max(2, int(round(length * (1 - 0.6 * t))))
        for y in range(max(0, y_lo), min(H, y_hi + 1)):
            for z in range(cz, min(L, cz + local_length)):
                grid[x, y, z] = Role.WING


def _place_gull(
    grid: np.ndarray,
    span: int,
    thickness: int,
    length: int,
    y_lo: int,
    y_hi: int,
    cz: int,
) -> None:
    """Inner half is flat; outer half rises one Y per X past the knee.
    Mimics a gull-wing silhouette when viewed head-on. ``thickness`` is
    absorbed into the rise step so gull reads as one thicker structure
    rather than a thin line."""
    W, H, L = grid.shape
    knee = span // 2
    for x in range(0, span):
        y_shift = 0 if x <= knee else (x - knee)
        for y in range(max(0, y_lo + y_shift), min(H, y_hi + y_shift + 1)):
            for z in range(cz, min(L, cz + length)):
                grid[x, y, z] = Role.WING


def _place_split(
    grid: np.ndarray,
    span: int,
    thickness: int,
    length: int,
    cy: int,
    cz: int,
    _length_ignored: int,
) -> None:
    """Two thinner wings stacked vertically with a gap — biplane-style.
    Each wing is ``max(1, thickness // 2)`` tall, centered ``thickness``
    above and below ``cy``. The mirror pass still produces the right
    side of both stacked wings."""
    W, H, L = grid.shape
    thin = max(1, thickness // 2)
    gap = max(2, thickness)
    for dy_center in (-gap, +gap):
        y_center = cy + dy_center
        t_lo = y_center - thin // 2
        t_hi = t_lo + thin - 1
        for x in range(0, span):
            for y in range(max(0, t_lo), min(H, t_hi + 1)):
                for z in range(cz, min(L, cz + length)):
                    grid[x, y, z] = Role.WING
