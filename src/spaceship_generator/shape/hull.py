"""Hull placement — superellipse segmented massing driven by a ShipPlan.

The v2 hull is a stack of superellipse cross-sections::

    |dx / half_w| ** n  +  |dy / half_h| ** n  <=  1

with per-segment half-sizes linearly interpolated inside each
:class:`~spaceship_generator.shape.blueprint.HullSegment`. Exponent ``n = 2``
is an ellipse; ``n = 4`` a rounded rectangle with flat side panels and a
flat deck; ``n >= 8`` reads as a chamfered box. Flat faces are the point:
they give windows, greeble patches, and cockpits something to sit on.

The hull starts at the plan's rear wall (``plan.engine.wall_z``) so engine
nozzles can protrude behind it into ``[0, wall_z)``.
"""

from __future__ import annotations

import math

import numpy as np

from ..palette import Role
from ..structure_styles import HullStyle
from .blueprint import ShipPlan, build_plan
from .core import ShapeParams

# Maximum hull-noise displacement, in cells, at amplitude == 1.0.
_HULL_NOISE_MAX_DISPLACEMENT = 2


def _fill_superellipse_slice(
    grid: np.ndarray,
    z: int,
    half_w: float,
    half_h: float,
    exponent: float,
    y_center: float,
) -> None:
    """Stamp HULL into the ``z`` slice inside the superellipse."""
    W, H, _ = grid.shape
    cx = (W - 1) / 2.0
    xs = np.arange(W, dtype=np.float64).reshape(W, 1)
    ys = np.arange(H, dtype=np.float64).reshape(1, H)
    dx = np.abs((xs - cx) / max(half_w, 1e-6))
    dy = np.abs((ys - y_center) / max(half_h, 1e-6))
    inside = dx**exponent + dy**exponent <= 1.0
    view = grid[:, :, z]
    view[inside & (view == Role.EMPTY)] = Role.HULL


def _place_hull(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    plan: ShipPlan,
) -> None:
    """Fill the planned hull segments with HULL voxels.

    ``rng`` is accepted for signature symmetry with the other placers but is
    not consumed — all per-seed variation already lives in the plan.
    """
    _, _, L = grid.shape
    for z in range(plan.engine.wall_z, L):
        half_w, half_h, exponent, y_center = plan.hull_half_at(z)
        _fill_superellipse_slice(grid, z, half_w, half_h, exponent, y_center)


def _place_hull_blend(
    grid: np.ndarray,
    rng: np.random.Generator,
    params: ShapeParams,
    front: HullStyle,
    rear: HullStyle,
    *,
    midband: float = 0.25,
) -> ShipPlan:
    """Stamp HULL by blending two hull styles' planned cross-sections along Z.

    Both styles are planned from the same derived sub-seed so their jitters
    match; per-Z the half-sizes and exponent are cosine-blended across a
    ``midband`` fraction of the length centred at ``z = L/2``. Returns the
    *rear* style's plan so downstream part placement anchors to the engine
    end's geometry (the blend only affects hull cross-sections).
    """
    if not isinstance(front, HullStyle):
        raise ValueError(
            f"_place_hull_blend expects HullStyle for front; got "
            f"{type(front).__name__}"
        )
    if not isinstance(rear, HullStyle):
        raise ValueError(
            f"_place_hull_blend expects HullStyle for rear; got "
            f"{type(rear).__name__}"
        )

    sub_seed = int(rng.integers(0, 2**63 - 1, dtype=np.int64))
    plan_front = build_plan(np.random.default_rng(sub_seed), params, front)
    plan_rear = build_plan(np.random.default_rng(sub_seed), params, rear)

    _, _, L = grid.shape
    mid = (L - 1) / 2.0
    band = max(1.0, L * max(0.0, min(1.0, midband)))

    for z in range(plan_rear.engine.wall_z, L):
        # Blend weight: 0 → pure rear at the engine end, 1 → pure front at
        # the nose, cosine ramp across the midband.
        u = (z - (mid - band / 2.0)) / band
        u = max(0.0, min(1.0, u))
        w = 0.5 - 0.5 * math.cos(u * math.pi)

        rw, rh, rn, ry = plan_rear.hull_half_at(z)
        fw, fh, fn, fy = plan_front.hull_half_at(z)
        half_w = rw + (fw - rw) * w
        half_h = rh + (fh - rh) * w
        exponent = rn + (fn - rn) * w
        y_center = ry + (fy - ry) * w
        _fill_superellipse_slice(grid, z, half_w, half_h, exponent, y_center)

    return plan_rear


def _dilate6(mask: np.ndarray) -> np.ndarray:
    """Return ``mask`` dilated by one cell in 6-connectivity (in-bounds only)."""
    out = mask.copy()
    out[1:, :, :] |= mask[:-1, :, :]
    out[:-1, :, :] |= mask[1:, :, :]
    out[:, 1:, :] |= mask[:, :-1, :]
    out[:, :-1, :] |= mask[:, 1:, :]
    out[:, :, 1:] |= mask[:, :, :-1]
    out[:, :, :-1] |= mask[:, :, 1:]
    return out


def _hash_noise_field(W: int, H: int, L: int, sub_seed: int) -> np.ndarray:
    """Return a ``(W, H, L)`` ``float32`` noise field in ``[-1, 1]``.

    Cheap deterministic per-cell hash noise — byte-stable across NumPy
    versions (integer arithmetic only).
    """
    xs = np.arange(W, dtype=np.int64).reshape(W, 1, 1)
    ys = np.arange(H, dtype=np.int64).reshape(1, H, 1)
    zs = np.arange(L, dtype=np.int64).reshape(1, 1, L)
    h = (
        xs * np.int64(73856093)
        + ys * np.int64(19349663)
        + zs * np.int64(83492791)
        + np.int64(sub_seed)
    )
    h ^= (h >> np.int64(33))
    h = h * np.int64(2246822519)  # 0x85EBCA77
    h ^= (h >> np.int64(29))
    h = h * np.int64(3266489917)  # 0xC2B2AE3D
    h ^= (h >> np.int64(32))
    u = (h & np.int64(0xFFFFFF)).astype(np.float32) / np.float32(0xFFFFFF)
    return (u * np.float32(2.0) - np.float32(1.0))


def _apply_hull_noise(
    grid: np.ndarray, rng: np.random.Generator, params: ShapeParams
) -> None:
    """Distort the hull membrane with deterministic procedural noise.

    Erodes a noise-selected subset of the hull's surface shell and grows a
    subset of the adjacent empty band, bounded to ±2 cells of displacement.
    No-op at zero amplitude. One ``rng`` draw is consumed when active.
    """
    amplitude = float(params.hull_noise)
    if amplitude <= 0.0:
        return

    iters = max(1, int(round(amplitude * _HULL_NOISE_MAX_DISPLACEMENT)))
    iters = min(iters, _HULL_NOISE_MAX_DISPLACEMENT)
    threshold = float(np.float32(1.0 - amplitude))

    sub_seed = int(rng.integers(0, 2**63 - 1, dtype=np.int64))

    W, H, L = grid.shape
    noise = _hash_noise_field(W, H, L, sub_seed)

    for it in range(iters):
        hull_mask = grid == Role.HULL
        if not hull_mask.any():
            return

        empty_mask = grid == Role.EMPTY
        inner_shell = hull_mask & _dilate6(empty_mask)
        outer_band = empty_mask & _dilate6(hull_mask)

        field = noise if it == 0 else -noise

        erode = inner_shell & (field < -threshold)
        grow = outer_band & (field > threshold)

        if erode.any():
            grid[erode] = Role.EMPTY
        if grow.any():
            grid[grow] = Role.HULL
