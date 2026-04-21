"""Engine cylinder placement at the rear of the ship."""

from __future__ import annotations

import numpy as np

from ..palette import Role
from ..structure_styles import engine_count_override, engine_radius_scale
from .core import ShapeParams


def _place_engines(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Add N engine cylinders at the rear of the ship.

    Engine count and nozzle size are modulated by :attr:`ShapeParams.structure_style`.
    """
    style = params.structure_style
    n = engine_count_override(style, params.engine_count)
    if n == 0:
        return
    W, H, L = grid.shape

    engine_length = max(2, L // 8)
    base_radius = max(1, min(W, H) // 10)
    engine_radius = max(
        1, int(round(base_radius * engine_radius_scale(style)))
    )

    xs = _engine_x_positions(n, W, engine_radius)
    cy_engine = max(engine_radius + 1, H // 2 - 1)

    for ex in xs:
        for x in range(ex - engine_radius - 1, ex + engine_radius + 2):
            for y in range(cy_engine - engine_radius - 1, cy_engine + engine_radius + 2):
                for z in range(0, engine_length):
                    if not (0 <= x < W and 0 <= y < H and 0 <= z < L):
                        continue
                    dx = x - ex
                    dy = y - cy_engine
                    if dx * dx + dy * dy <= engine_radius * engine_radius:
                        grid[x, y, z] = Role.ENGINE


def _engine_x_positions(n: int, width: int, radius: int) -> list[int]:
    """Return engine X positions spread symmetrically across the ship width.

    Positions are clamped to ``[radius, width - 1 - radius]`` so that the
    engine cylinder stays in-bounds. If the width is too narrow to hold
    ``n`` distinct clamped positions (for example the pathological
    ``n=4, width=4, radius=2`` case where ``usable`` would be negative),
    all engines collapse to the ship's X center.
    """
    if n <= 0:
        return []
    if n == 1:
        return [width // 2]
    cx = (width - 1) / 2.0
    half = n // 2
    # Space from center to the outermost valid engine x. Clamp to >= 0 so a
    # negative ``usable`` (cramped grid) does not flip offsets and create
    # duplicates.
    usable = max(0.0, (width - 2 * radius - 2) / 2.0)
    spacing = usable / max(half, 1)

    # Valid in-bounds range for an engine of this radius.
    lo = max(0, radius)
    hi = min(width - 1, width - 1 - radius)

    xs: list[int] = []
    for i in range(1, half + 1):
        offset = spacing * i
        xs.append(int(round(cx - offset)))
        xs.append(int(round(cx + offset)))
    if n % 2 == 1:
        xs.append(int(round(cx)))

    # Clamp all positions into the valid in-bounds window.
    if hi >= lo:
        xs = [max(lo, min(hi, x)) for x in xs]
    else:
        # No valid window: fall back to ship center for every engine.
        return [width // 2] * n

    # Detect collisions introduced by cramped widths. If any duplicates
    # remain we cannot cleanly separate the engines, so collapse them all
    # to the ship center (matches the n == 1 behavior and keeps the shape
    # symmetric and deterministic).
    if len(set(xs)) != n:
        return [width // 2] * n

    return xs
