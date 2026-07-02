"""Blueprint stage — build an explicit :class:`ShipPlan` before any voxels.

Every placement module (hull, cockpit, engines, wings, greebles) reads the
plan instead of re-deriving geometry from the raw grid, so parts align by
construction: the cockpit knows which deck rectangle it owns, engines know
where the rear wall is, wings know the hull half-width at their root.

Grid conventions (same as :mod:`spaceship_generator.shape.core`):
``grid[x, y, z]``, x = width (mirror axis), y = height, z = length with
``z = 0`` the engine end and ``z = L - 1`` the nose.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..structure_styles import (
    HullStyle,
    StructureStyle,
    engine_count_override,
    engine_radius_scale,
    wing_prob_override,
    wing_size_scale,
)
from ..wing_styles import WingStyle
from .core import CockpitStyle, ShapeParams


@dataclass(frozen=True)
class MassingConfig:
    """Per-style hull massing parameters.

    ``width_frac``/``height_frac`` are fractions of grid W/H used as the
    mid-segment cross-section half-sizes. ``exponent`` is the superellipse
    exponent (2 = ellipse, 4 = rounded rectangle, 8+ = near-box).
    ``nose_frac``/``tail_frac`` are fractions of L given to the nose taper
    and engine segments. ``nose_tip_frac`` is the fraction of the mid
    cross-section remaining at the very tip. ``wing_bias`` scales wing
    probability; ``nacelle_prob`` is the chance of side nacelle pods.
    """

    width_frac: float
    height_frac: float
    exponent: float
    nose_frac: float
    tail_frac: float
    nose_tip_frac: float
    wing_bias: float
    nacelle_prob: float


MASSING: dict[HullStyle, MassingConfig] = {
    HullStyle.ARROW: MassingConfig(0.32, 0.38, 3.0, 0.34, 0.18, 0.12, 1.0, 0.25),
    HullStyle.SAUCER: MassingConfig(0.40, 0.28, 2.0, 0.22, 0.16, 0.30, 0.4, 0.15),
    HullStyle.WHALE: MassingConfig(0.40, 0.44, 2.4, 0.24, 0.18, 0.25, 0.7, 0.20),
    HullStyle.DAGGER: MassingConfig(0.26, 0.34, 3.2, 0.38, 0.16, 0.10, 1.0, 0.30),
    HullStyle.BLOCKY_FREIGHTER: MassingConfig(0.36, 0.42, 8.0, 0.12, 0.16, 0.55, 0.5, 0.35),
    HullStyle.ORGANIC_BIO: MassingConfig(0.38, 0.42, 2.0, 0.26, 0.20, 0.20, 0.6, 0.10),
    HullStyle.HEXAGONAL_LATTICE: MassingConfig(0.34, 0.38, 3.5, 0.24, 0.18, 0.28, 0.7, 0.25),
    HullStyle.ASYMMETRIC_SCAVENGER: MassingConfig(0.34, 0.40, 6.0, 0.18, 0.20, 0.40, 0.8, 0.45),
    HullStyle.MODULAR_BLOCK: MassingConfig(0.34, 0.40, 10.0, 0.10, 0.18, 0.60, 0.4, 0.40),
    HullStyle.SLEEK_RACING: MassingConfig(0.24, 0.30, 2.6, 0.40, 0.16, 0.08, 1.0, 0.35),
}

# Default massing per StructureStyle when no HullStyle is given.
_STRUCTURE_MASSING: dict[StructureStyle, MassingConfig] = {
    StructureStyle.FRIGATE: MassingConfig(0.32, 0.38, 3.4, 0.28, 0.18, 0.14, 1.0, 0.30),
    StructureStyle.FIGHTER: MassingConfig(0.24, 0.32, 3.0, 0.38, 0.16, 0.10, 1.0, 0.35),
    StructureStyle.DREADNOUGHT: MassingConfig(0.38, 0.44, 7.0, 0.14, 0.18, 0.45, 0.5, 0.40),
    StructureStyle.SHUTTLE: MassingConfig(0.36, 0.42, 2.4, 0.24, 0.18, 0.30, 0.3, 0.05),
    StructureStyle.HAMMERHEAD: MassingConfig(0.34, 0.38, 4.0, 0.20, 0.24, 0.50, 0.8, 0.25),
    StructureStyle.CARRIER: MassingConfig(0.40, 0.30, 6.0, 0.14, 0.16, 0.40, 0.4, 0.30),
}


@dataclass(frozen=True)
class HullSegment:
    """One Z-slice of the hull with linearly-interpolated cross-section."""

    z0: int          # inclusive
    z1: int          # exclusive
    half_w0: float
    half_h0: float
    half_w1: float
    half_h1: float
    exponent: float
    y_center: float


@dataclass(frozen=True)
class CockpitPlan:
    style: CockpitStyle
    z0: int
    z1: int
    half_w: int


@dataclass(frozen=True)
class EnginePlan:
    wall_z: int
    nozzle_xs: tuple[int, ...]
    nozzle_y: int
    radius: int
    nacelles: bool
    nacelle_half_w: int
    nacelle_half_h: int
    nacelle_z0: int
    nacelle_z1: int
    nacelle_cx_off: int


@dataclass(frozen=True)
class WingPlan:
    present: bool
    style: WingStyle
    root_z: int
    root_chord: int
    span: int
    thickness: int
    y_anchor: int


@dataclass(frozen=True)
class ShipPlan:
    segments: tuple[HullSegment, ...]
    cockpit: CockpitPlan
    engine: EnginePlan
    wing: WingPlan

    def hull_half_at(self, z: int) -> tuple[float, float, float, float]:
        """Return ``(half_w, half_h, exponent, y_center)`` at slice ``z``.

        Z before the rear wall clamps to the first segment's start; Z past
        the nose clamps to the last segment's end.
        """
        segs = self.segments
        if z < segs[0].z0:
            s = segs[0]
            return s.half_w0, s.half_h0, s.exponent, s.y_center
        for s in segs:
            if s.z0 <= z < s.z1:
                span = max(s.z1 - 1 - s.z0, 1)
                t = (z - s.z0) / span
                half_w = s.half_w0 + (s.half_w1 - s.half_w0) * t
                half_h = s.half_h0 + (s.half_h1 - s.half_h0) * t
                return half_w, half_h, s.exponent, s.y_center
        s = segs[-1]
        return s.half_w1, s.half_h1, s.exponent, s.y_center


def _pick_config(params: ShapeParams, hull_style: HullStyle | None) -> MassingConfig:
    if hull_style is not None:
        # Accept enum members or their string values; anything else is a
        # caller error and must raise ValueError (the documented contract —
        # web/CLI layers catch ValueError, not KeyError).
        if not isinstance(hull_style, HullStyle):
            try:
                hull_style = HullStyle(hull_style)
            except ValueError as exc:
                raise ValueError(
                    f"hull_style must be a HullStyle or one of "
                    f"{[s.value for s in HullStyle]}; got {hull_style!r}"
                ) from exc
        return MASSING[hull_style]
    return _STRUCTURE_MASSING[params.structure_style]


def build_plan(
    rng: np.random.Generator,
    params: ShapeParams,
    hull_style: HullStyle | None = None,
) -> ShipPlan:
    """Draw the ship's blueprint from ``rng``.

    Consumes a fixed number of rng draws regardless of outcome so downstream
    placement stays deterministic per (seed, params, hull_style).
    """
    cfg = _pick_config(params, hull_style)
    W, H, L = params.width_max, params.height_max, params.length
    cx = (W - 1) / 2.0
    y_center = (H - 1) / 2.0

    # Per-seed jitter draws (fixed count).
    jw = 0.92 + rng.random() * 0.16       # width jitter ±8%
    jh = 0.92 + rng.random() * 0.16       # height jitter ±8%
    j_nose = 0.85 + rng.random() * 0.30   # nose length jitter
    wing_roll = rng.random()
    nacelle_roll = rng.random()
    wing_z_jitter = rng.random()

    half_w_mid = min(W * cfg.width_frac * jw, W * 0.44)
    half_h_mid = min(H * cfg.height_frac * jh, H * 0.48)
    # Keep the hull inside the grid vertically.
    half_h_mid = min(half_h_mid, y_center, (H - 1) - y_center)
    half_w_mid = max(1.5, half_w_mid)
    half_h_mid = max(1.5, half_h_mid)

    wall_z = max(2, L // 12)
    nose_len = max(3, int(round(L * cfg.nose_frac * j_nose)))
    tail_len = max(3, int(round(L * cfg.tail_frac)))
    body_len = L - wall_z - nose_len - tail_len
    if body_len < 6:
        # Cramped ship: shrink nose/tail (down to a floor of 3 each) until
        # the body has room. On minimum-size ships this may still leave a
        # small or zero body — the clamps below keep every segment
        # non-negative so the z-ranges stay monotone (an inverted segment
        # would be silently skipped by hull_half_at, kinking the hull).
        deficit = 6 - body_len
        take_nose = min(deficit, max(0, nose_len - 3))
        nose_len -= take_nose
        deficit -= take_nose
        take_tail = min(deficit, max(0, tail_len - 3))
        tail_len -= take_tail
        body_len = L - wall_z - nose_len - tail_len
    body_len = max(0, body_len)
    fore_len = max(2, int(round(body_len * 0.38)))
    fore_len = min(fore_len, body_len)  # never exceed the body budget
    mid_len = body_len - fore_len

    z_engine0 = wall_z
    z_engine1 = z_engine0 + tail_len
    z_mid1 = z_engine1 + mid_len
    z_fore1 = z_mid1 + fore_len
    z_nose1 = L

    tip_w = max(0.8, half_w_mid * cfg.nose_tip_frac)
    tip_h = max(0.8, half_h_mid * max(cfg.nose_tip_frac, 0.25))

    segments = (
        HullSegment(z_engine0, z_engine1,
                    half_w_mid * 0.80, half_h_mid * 0.85,
                    half_w_mid, half_h_mid,
                    cfg.exponent, y_center),
        HullSegment(z_engine1, z_mid1,
                    half_w_mid, half_h_mid,
                    half_w_mid, half_h_mid,
                    cfg.exponent, y_center),
        HullSegment(z_mid1, z_fore1,
                    half_w_mid * 0.88, half_h_mid * 0.90,
                    half_w_mid * 0.80, half_h_mid * 0.85,
                    cfg.exponent, y_center),
        HullSegment(z_fore1, z_nose1,
                    half_w_mid * 0.78, half_h_mid * 0.82,
                    tip_w, tip_h,
                    cfg.exponent, y_center),
    )

    # --- Engines -----------------------------------------------------------
    n = engine_count_override(params.structure_style, params.engine_count)
    half_w_eng = segments[0].half_w0
    half_h_eng = segments[0].half_h0
    # Nozzle size scales with hull height *and* the structure style's
    # archetype multiplier (DREADNOUGHT 1.6x, SHUTTLE 0.6x, ...).
    r_scale = engine_radius_scale(params.structure_style)
    radius = max(2, int(round(half_h_eng * 0.55 * r_scale)))
    radius = min(radius, max(1, int(half_h_eng)))
    nozzle_xs = _nozzle_positions(n, cx, half_w_eng, radius)
    nozzle_y = int(round(y_center))

    nacelles = nacelle_roll < cfg.nacelle_prob
    nacelle_half_w = max(1, int(round(half_w_mid * 0.30)))
    nacelle_half_h = max(1, int(round(half_h_mid * 0.45)))
    nacelle_cx_off = int(round(half_w_mid + 1 + nacelle_half_w))
    # Pods hug the engine + rear-mid section.
    nacelle_z0 = z_engine0
    nacelle_z1 = min(z_mid1, z_engine1 + max(4, mid_len // 2))
    # Drop nacelles that would poke out of the grid.
    if cx - nacelle_cx_off - nacelle_half_w < 0:
        nacelles = False

    engine = EnginePlan(
        wall_z=wall_z,
        nozzle_xs=nozzle_xs,
        nozzle_y=nozzle_y,
        radius=radius,
        nacelles=nacelles,
        nacelle_half_w=nacelle_half_w,
        nacelle_half_h=nacelle_half_h,
        nacelle_z0=nacelle_z0,
        nacelle_z1=nacelle_z1,
        nacelle_cx_off=nacelle_cx_off,
    )

    # --- Wings --------------------------------------------------------------
    eff_prob = wing_prob_override(params.structure_style, params.wing_prob)
    eff_prob = min(1.0, eff_prob * cfg.wing_bias)
    present = wing_roll < eff_prob
    # Per-archetype wing proportions (FIGHTER long-span, DREADNOUGHT stubby
    # and thick, ...). Span is the outboard reach from the hull surface and
    # is clamped to the grid by the wing placer.
    span_s, thick_s, len_s = wing_size_scale(params.structure_style)
    root_chord = max(4, int(round((L // 4) * len_s)))
    lo = z_engine1
    hi = max(lo + 1, z_mid1 - root_chord)
    root_z = lo + int(wing_z_jitter * (hi - lo))
    root_z = max(0, min(L - root_chord - 1, root_z))
    span = max(2, int(round((W / 2.0 - half_w_mid - 1) * span_s)))
    thickness = max(2, int(round((H // 6) * thick_s)))
    wing = WingPlan(
        present=present,
        style=params.wing_style,
        root_z=root_z,
        root_chord=root_chord,
        span=span,
        thickness=thickness,
        y_anchor=int(round(y_center)),
    )

    # --- Cockpit --------------------------------------------------------------
    cp_z0 = z_mid1 + 1
    cp_z1 = min(z_fore1 + max(2, nose_len // 3), L - 2)
    cp_z1 = max(cp_z1, cp_z0 + 3)
    cp_z1 = min(cp_z1, L - 1)
    # Guarantee a rect wide/long enough for a framed recessed cockpit
    # whenever the fore hull can support one (half-width >= 2 needs hull
    # half-width >= ~3.5, z-span >= 4 needs the length). Without this,
    # INTEGRATED silently drops its hull border on small ships.
    cp_half_w = max(1, int(round(segments[2].half_w0 * 0.45)))
    if segments[2].half_w0 >= 3.5:
        cp_half_w = max(2, cp_half_w)
    if cp_z1 - cp_z0 < 4:
        cp_z0 = max(1, min(cp_z0, cp_z1 - 4))
    cockpit = CockpitPlan(
        style=params.cockpit_style,
        z0=cp_z0,
        z1=cp_z1,
        half_w=cp_half_w,
    )

    return ShipPlan(segments=segments, cockpit=cockpit, engine=engine, wing=wing)


def plan_for(
    seed: int,
    params: ShapeParams,
    *,
    hull_style: HullStyle | None = None,
    hull_style_front: HullStyle | None = None,
    hull_style_rear: HullStyle | None = None,
) -> ShipPlan:
    """Reproduce the exact :class:`ShipPlan` that ``generate_shape`` uses.

    ``generate_shape`` derives its plan from ``default_rng(seed)`` — for the
    single-style path directly, and for the blend path from a sub-seed drawn
    as that rng's first ``integers`` call. This helper mirrors both draws so
    post-pipeline callers (e.g. the ``engine_style`` override in
    ``generator.generate``) can anchor to the same geometry (rear wall,
    nozzle radius, deck line) without re-running the pipeline.
    """
    rng = np.random.default_rng(seed)
    if hull_style_front is not None and hull_style_rear is not None:
        # Match _place_hull_blend: one integers draw → sub-seeded rear plan.
        sub_seed = int(rng.integers(0, 2**63 - 1, dtype=np.int64))
        return build_plan(np.random.default_rng(sub_seed), params, hull_style_rear)
    return build_plan(rng, params, hull_style)


def _nozzle_positions(n: int, cx: float, half_w: float, radius: int) -> tuple[int, ...]:
    """Symmetric nozzle X centers within the hull's rear-wall half-width."""
    if n <= 0:
        return ()
    if n == 1:
        return (int(round(cx)),)
    spread = max(0.0, half_w - radius * 0.5)
    half = n // 2
    xs: list[int] = []
    for i in range(1, half + 1):
        # Fractional offsets 0.5, 0.9 (2 or 4 engines), etc.
        frac = i / (half + 0.6)
        off = spread * frac
        xs.append(int(round(cx - off)))
        xs.append(int(round(cx + off)))
    if n % 2 == 1:
        xs.append(int(round(cx)))
    # De-duplicate while preserving symmetry: if rounding collided, collapse
    # to a single centered nozzle (deterministic, still symmetric).
    if len(set(xs)) != n:
        return (int(round(cx)),)
    return tuple(sorted(xs))
