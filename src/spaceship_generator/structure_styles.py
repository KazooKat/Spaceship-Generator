"""Structure styles — silhouette archetypes for procedural ships.

Each :class:`StructureStyle` tweaks the body profile, engine placement,
and wing placement knobs so the same seed and other params produce a
visibly different ship archetype. The default :attr:`StructureStyle.FRIGATE`
preserves the original generator behavior exactly for backward compat.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids circular import
    from .shape import CockpitStyle


class StructureStyle(str, Enum):
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
    style: StructureStyle, requested: "CockpitStyle"
) -> "CockpitStyle":
    """Some styles have a preferred cockpit when the user left the default.

    Currently a pass-through: ``requested`` is always honored. The hook is kept
    so future tweaks can steer defaults without changing call sites.
    """
    # The user's explicit choice always wins. No override.
    return requested
