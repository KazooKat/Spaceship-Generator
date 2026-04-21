"""Structure styles — silhouette archetypes for procedural ships.

Each :class:`StructureStyle` tweaks the body profile, engine placement,
and wing placement knobs so the same seed and other params produce a
visibly different ship archetype. The default :attr:`StructureStyle.FRIGATE`
preserves the original generator behavior exactly for backward compat.

:class:`HullStyle` is a separate, finer-grained dial that shapes only the
hull silhouette (profile along Z + X/Y scaling). It is a purely-geometric
dial: no engine, wing, or cockpit effects. Call :func:`apply_hull_style`
to stamp a style directly onto an empty grid — useful for previewing
hull silhouettes without running the full generator pipeline.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np

from .palette import Role

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids circular import
    from .shape import CockpitStyle


class StructureStyle(StrEnum):
    """Visual archetype for the overall ship silhouette.

    * :attr:`FRIGATE` — default, moderately tapered, original behavior.
    * :attr:`FIGHTER` — small, narrow, dagger silhouette tapered at both ends.
    * :attr:`DREADNOUGHT` — big/wide/blocky with a flat plateau profile.
    * :attr:`SHUTTLE` — small rounded ellipsoid; no wings; single engine.
    * :attr:`HAMMERHEAD` — wide forward nose, narrow rear.
    * :attr:`CARRIER` — long flat deck; multiple engines, bigger rx, squashed ry.
    """

    FRIGATE = "frigate"
    FIGHTER = "fighter"
    DREADNOUGHT = "dreadnought"
    SHUTTLE = "shuttle"
    HAMMERHEAD = "hammerhead"
    CARRIER = "carrier"


# ---------------------------------------------------------------------------
# Profile functions (taper along Z, t=0 rear → t=1 nose)
# ---------------------------------------------------------------------------


def _profile_frigate(t: float) -> float:
    """Original body profile — peaks slightly forward of the middle."""
    peak = 0.55
    sigma = 0.32
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    return max(0.0, min(1.0, f))


def _profile_fighter(t: float) -> float:
    """Dagger silhouette — sharp taper at both nose and rear."""
    peak = 0.5
    sigma = 0.22
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    # Extra squeeze at both endpoints so the silhouette reads as pointed.
    edge = min(t, 1.0 - t) * 2.0  # 0 at both ends, 1 at mid
    f *= 0.5 + 0.5 * edge
    return max(0.0, min(1.0, f))


def _profile_dreadnought(t: float) -> float:
    """Flat plateau — stays near-max for most of the length."""
    # Smooth plateau via a logistic-like clamp. The profile stays near 1
    # between t≈0.12 and t≈0.88 and falls off sharply at the ends.
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    rise = _clamp01((t - 0.05) / 0.15)
    fall = _clamp01((0.95 - t) / 0.12)
    return min(rise, fall) * 0.98 + 0.02


def _profile_shuttle(t: float) -> float:
    """Rounded ellipsoid — symmetrical loaf-of-bread."""
    # Half-ellipse centered at t=0.5.
    d = (t - 0.5) * 2.0  # -1 at rear, +1 at nose
    inside = max(0.0, 1.0 - d * d)
    return math.sqrt(inside)


def _profile_hammerhead(t: float) -> float:
    """Wide forward nose, narrow rear — profile peaks near t=0.85."""
    peak = 0.85
    sigma = 0.22
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    # Strong taper at the rear (t near 0) so the engine section is thin.
    rear_cut = max(0.0, min(1.0, t / 0.35))
    f *= 0.2 + 0.8 * rear_cut
    return max(0.0, min(1.0, f))


def _profile_carrier(t: float) -> float:
    """Long, flat deck-like profile — height cut in half, mostly-plateau."""
    # Similar to dreadnought but even flatter and longer.
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    rise = _clamp01((t - 0.02) / 0.08)
    fall = _clamp01((0.98 - t) / 0.08)
    return min(rise, fall) * 0.95 + 0.05


_PROFILE_FNS: dict[StructureStyle, Callable[[float], float]] = {
    StructureStyle.FRIGATE: _profile_frigate,
    StructureStyle.FIGHTER: _profile_fighter,
    StructureStyle.DREADNOUGHT: _profile_dreadnought,
    StructureStyle.SHUTTLE: _profile_shuttle,
    StructureStyle.HAMMERHEAD: _profile_hammerhead,
    StructureStyle.CARRIER: _profile_carrier,
}


def profile_fn(style: StructureStyle) -> Callable[[float], float]:
    """Return the taper profile function for ``style``."""
    return _PROFILE_FNS.get(style, _profile_frigate)


# ---------------------------------------------------------------------------
# Hull shaping knobs
# ---------------------------------------------------------------------------


def hull_rx_ry_scale(style: StructureStyle) -> tuple[float, float]:
    """Return ``(rx_scale, ry_scale)`` multipliers applied on top of the profile.

    ``rx`` is half-width (X), ``ry`` is half-height (Y). Scaling factors stack
    with the base profile: ``rx = (W*0.5 - 0.5) * profile * thickness * rx_scale``.
    Default (``FRIGATE``) is ``(1.0, 1.0)``.
    """
    if style == StructureStyle.DREADNOUGHT:
        return (1.05, 1.05)
    if style == StructureStyle.FIGHTER:
        # Narrower body so wings read more prominently.
        return (0.75, 0.85)
    if style == StructureStyle.CARRIER:
        # Wide deck, squashed height.
        return (1.15, 0.55)
    if style == StructureStyle.SHUTTLE:
        return (0.95, 1.0)
    if style == StructureStyle.HAMMERHEAD:
        return (1.1, 0.9)
    return (1.0, 1.0)


# ---------------------------------------------------------------------------
# Engine knobs
# ---------------------------------------------------------------------------


def engine_count_override(style: StructureStyle, n: int) -> int:
    """Return the engine count to actually use for ``style``.

    ``SHUTTLE`` collapses to a single central engine regardless of request.
    ``DREADNOUGHT`` and ``CARRIER`` floor at a larger count for visual bulk.
    """
    if style == StructureStyle.SHUTTLE:
        return 1
    if style == StructureStyle.DREADNOUGHT:
        return max(n, 4)
    if style == StructureStyle.CARRIER:
        return max(n, 4)
    if style == StructureStyle.FIGHTER:
        return max(1, min(n, 2))
    return n


def engine_radius_scale(style: StructureStyle) -> float:
    """Return the multiplier on base engine radius."""
    if style == StructureStyle.DREADNOUGHT:
        return 1.6
    if style == StructureStyle.SHUTTLE:
        return 0.6
    if style == StructureStyle.FIGHTER:
        return 0.8
    if style == StructureStyle.CARRIER:
        return 1.2
    return 1.0


# ---------------------------------------------------------------------------
# Wing / cockpit knobs
# ---------------------------------------------------------------------------


def wing_prob_override(style: StructureStyle, base: float) -> float:
    """Return the effective wing probability for ``style``.

    ``SHUTTLE`` disables wings. ``FIGHTER`` raises them. Others unchanged.
    """
    if style == StructureStyle.SHUTTLE:
        return 0.0
    if style == StructureStyle.FIGHTER:
        return max(base, 0.95)
    if style == StructureStyle.CARRIER:
        # Carriers traditionally don't sport wings.
        return min(base, 0.1)
    if style == StructureStyle.DREADNOUGHT:
        return min(base, 0.35)
    return base


def wing_size_scale(style: StructureStyle) -> tuple[float, float, float]:
    """Return ``(span_scale, thickness_scale, length_scale)``."""
    if style == StructureStyle.FIGHTER:
        return (1.5, 1.0, 1.2)
    if style == StructureStyle.DREADNOUGHT:
        return (0.8, 1.4, 0.9)
    return (1.0, 1.0, 1.0)


def default_cockpit_for(
    style: StructureStyle, requested: CockpitStyle
) -> CockpitStyle:
    """Some styles have a preferred cockpit when the user left the default.

    Currently a pass-through: ``requested`` is always honored. The hook is kept
    so future tweaks can steer defaults without changing call sites.
    """
    # The user's explicit choice always wins. No override.
    return requested


# ---------------------------------------------------------------------------
# HullStyle — hull-only silhouette archetypes
# ---------------------------------------------------------------------------


class HullStyle(StrEnum):
    """Silhouette archetype for the hull alone.

    Unlike :class:`StructureStyle`, this dial affects only the hull
    profile + X/Y scaling. It does not touch engines, wings, or cockpit
    hooks. Intended for preview and for a future generator-level opt-in.

    * :attr:`ARROW` — long pointed front; sharp nose, chunky rear.
    * :attr:`SAUCER` — flat disc; wide in X, squashed in Y.
    * :attr:`WHALE` — fat rounded body; maximum volume mid-ship.
    * :attr:`DAGGER` — narrow slim blade; tapered at both ends, thin X.
    * :attr:`BLOCKY_FREIGHTER` — boxy utility; near-constant X and Y.
    """

    ARROW = "arrow"
    SAUCER = "saucer"
    WHALE = "whale"
    DAGGER = "dagger"
    BLOCKY_FREIGHTER = "blocky_freighter"


def _profile_arrow(t: float) -> float:
    """Long pointed front. Chunky rear (t~0), sharp nose (t~1)."""
    # Linear ramp from ~0.95 at rear down to near-zero at the nose, then
    # a soft smooth-step at the very rear so the aft isn't a hard wall.
    rear = max(0.0, min(1.0, t / 0.15))
    body = 1.0 - 0.9 * t  # 1.0 at rear, 0.1 at nose
    return max(0.0, min(1.0, rear * body))


def _profile_saucer(t: float) -> float:
    """Flat disc. Circle in the XZ plane (Y handled by ry scale)."""
    # Half-ellipse centered at t=0.5; near-flat plateau with soft edges.
    d = (t - 0.5) * 2.0  # -1 rear, +1 nose
    inside = max(0.0, 1.0 - d * d)
    # Flatten the top so it reads as a disc rather than a rugby ball.
    return min(1.0, math.sqrt(inside) * 1.15)


def _profile_whale(t: float) -> float:
    """Fat rounded body. Peak volume at mid-ship, gently tapering ends."""
    # Wide gaussian so the middle 70% stays near-max.
    peak = 0.5
    sigma = 0.45
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    # Lift the floor so even the ends stay fairly thick.
    return max(0.0, min(1.0, 0.25 + 0.75 * f))


def _profile_dagger(t: float) -> float:
    """Narrow slim blade. Tapered at both ends, peak slightly forward."""
    peak = 0.55
    sigma = 0.18
    f = math.exp(-((t - peak) ** 2) / (2 * sigma * sigma))
    # Extra squeeze near both endpoints for a knife silhouette.
    edge = min(t, 1.0 - t) * 2.0  # 0 at ends, 1 at mid
    f *= 0.35 + 0.65 * edge
    return max(0.0, min(1.0, f))


def _profile_blocky_freighter(t: float) -> float:
    """Boxy utility. Near-constant 1.0 across nearly the full length."""
    # Sharper rise/fall than the dreadnought plateau so the silhouette
    # reads as a crate rather than a softly-rounded capital ship.
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    rise = _clamp01((t - 0.02) / 0.06)
    fall = _clamp01((0.98 - t) / 0.06)
    return min(rise, fall)


_HULL_PROFILE_FNS: dict[HullStyle, Callable[[float], float]] = {
    HullStyle.ARROW: _profile_arrow,
    HullStyle.SAUCER: _profile_saucer,
    HullStyle.WHALE: _profile_whale,
    HullStyle.DAGGER: _profile_dagger,
    HullStyle.BLOCKY_FREIGHTER: _profile_blocky_freighter,
}


_HULL_RX_RY_SCALES: dict[HullStyle, tuple[float, float]] = {
    # ARROW: chunky rear width, moderate height.
    HullStyle.ARROW: (1.1, 0.9),
    # SAUCER: wide disc, very squashed Y.
    HullStyle.SAUCER: (1.35, 0.35),
    # WHALE: fat both directions.
    HullStyle.WHALE: (1.2, 1.15),
    # DAGGER: narrow X, moderate Y so the blade reads as tall-ish.
    HullStyle.DAGGER: (0.55, 0.95),
    # BLOCKY_FREIGHTER: wide + tall for a crate silhouette.
    HullStyle.BLOCKY_FREIGHTER: (1.15, 1.1),
}


def hull_profile_fn(style: HullStyle) -> Callable[[float], float]:
    """Return the taper profile function for ``style``."""
    return _HULL_PROFILE_FNS[style]


def hull_style_rx_ry(style: HullStyle) -> tuple[float, float]:
    """Return ``(rx_scale, ry_scale)`` multipliers for ``style``."""
    return _HULL_RX_RY_SCALES[style]


def apply_hull_style(grid: np.ndarray, style: HullStyle) -> None:
    """Stamp :class:`Role.HULL` voxels onto ``grid`` for the chosen ``style``.

    ``grid`` must be a ``(W, H, L)`` integer array (typically int8 filled
    with :attr:`Role.EMPTY`). Writes happen in-place. This is deterministic
    given ``(grid.shape, style)`` — there is no RNG dependence.

    The generator owns the full pipeline (cockpit, engines, wings, etc.);
    this function is the minimal hull-only stamper the library exposes so
    callers can preview a hull silhouette without spinning up the rest.
    """
    if not isinstance(style, HullStyle):
        raise ValueError(
            f"apply_hull_style expects a HullStyle; got {type(style).__name__}"
        )
    if grid.ndim != 3:
        raise ValueError(
            f"apply_hull_style expects a 3-D grid; got ndim={grid.ndim}"
        )

    W, H, L = grid.shape
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0

    profile_f = hull_profile_fn(style)
    rx_scale, ry_scale = hull_style_rx_ry(style)

    for z in range(L):
        t = z / max(L - 1, 1)
        profile = profile_f(t)
        rx = max(0.5, (W * 0.5 - 0.5) * profile * rx_scale)
        # Match the 0.7 "flatter-than-wide" baseline used by `_place_hull`
        # in shape.py so silhouettes look consistent with the generator.
        ry = max(0.5, (H * 0.5 - 0.5) * profile * 0.7 * ry_scale)
        for x in range(W):
            for y in range(H):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.HULL
