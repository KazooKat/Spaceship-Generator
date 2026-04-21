"""Engine archetype styles for ship shape generation.

Each :class:`EngineStyle` produces a distinct rear-engine silhouette while
reusing the same placement box (``shape``, ``position``, ``size``, ``rng``)
supplied by the generator.

Unlike :mod:`wing_styles`, builder functions here are **pure** — they do
not mutate the grid. Each ``build_<style>`` returns a list of voxel
placements ``(x, y, z, role)`` that the caller applies to the grid in
whatever order is appropriate (this lets the generator de-duplicate,
clip, or animate placements without re-running layout logic).

Adding a new style is a two-step change:

1. Add an enum member below.
2. Add a ``build_<style>`` implementation and hook it into the dispatch
   in :func:`build_engines`.

Contract
--------
* Builders MUST respect the ``(W, H, L)`` bounds implied by ``shape``.
  Out-of-bounds cells must be dropped, not clamped to an edge.
* Builders MUST be deterministic given the same ``(position, size,
  rng-state)``. The caller seeds ``rng``.
* Builders MUST only emit ``Role.ENGINE`` or ``Role.ENGINE_GLOW`` cells.
  Hull / greeble / wing placements belong to other modules.
* Every cell tuple is ``(x: int, y: int, z: int, role: Role)``. The
  generator treats later tuples as overwriting earlier ones, so place
  glow cores *after* engine cylinders for the expected visual.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np

from .palette import Role

#: One voxel placement: integer grid coords plus semantic role.
Placement = tuple[int, int, int, Role]


class EngineStyle(StrEnum):
    """Engine-block archetype.

    * :attr:`SINGLE_CORE` — one large central thruster (shuttles, fighters).
    * :attr:`TWIN_NACELLE` — two side nacelles, classic sci-fi silhouette.
    * :attr:`QUAD_CLUSTER` — four small engines in a 2x2 pattern.
    * :attr:`RING` — hollow annular thruster (torus cross-section).
    * :attr:`ION_ARRAY` — horizontal row of small glow blocks (ion drive).
    """

    SINGLE_CORE = "single_core"
    TWIN_NACELLE = "twin_nacelle"
    QUAD_CLUSTER = "quad_cluster"
    RING = "ring"
    ION_ARRAY = "ion_array"


def build_engines(
    shape: np.ndarray,
    engine_style: EngineStyle,
    *,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Return voxel placements for the chosen ``engine_style``.

    Parameters
    ----------
    shape:
        The (W, H, L) grid. Used for its shape only; never mutated.
    engine_style:
        The archetype to build.
    position:
        ``(cx, cy, cz)`` anchor. ``cx`` is X center, ``cy`` is Y center,
        ``cz`` is the rear Z slab (typically ``0``). Engines extend
        forward from ``cz``.
    size:
        ``(radius, length, spread)``. ``radius`` controls per-engine
        thickness, ``length`` is how far forward the engine extends,
        ``spread`` controls X-distance between multi-engine layouts.
    rng:
        Numpy random generator. Seeded by the caller for determinism.

    Returns
    -------
    list[Placement]
        One entry per voxel to write. May be empty if the requested
        geometry cannot fit inside ``shape``.
    """
    if engine_style == EngineStyle.SINGLE_CORE:
        return build_single_core(shape, position, size, rng)
    if engine_style == EngineStyle.TWIN_NACELLE:
        return build_twin_nacelle(shape, position, size, rng)
    if engine_style == EngineStyle.QUAD_CLUSTER:
        return build_quad_cluster(shape, position, size, rng)
    if engine_style == EngineStyle.RING:
        return build_ring(shape, position, size, rng)
    if engine_style == EngineStyle.ION_ARRAY:
        return build_ion_array(shape, position, size, rng)
    # pragma: no cover — unreachable given enum validation upstream.
    raise ValueError(f"unknown EngineStyle: {engine_style!r}")


# --- helpers ---------------------------------------------------------------


def _in_bounds(x: int, y: int, z: int, shape: np.ndarray) -> bool:
    """True iff ``(x, y, z)`` is a valid index into ``shape``."""
    W, H, L = shape.shape
    return 0 <= x < W and 0 <= y < H and 0 <= z < L


def _emit_disk(
    placements: list[Placement],
    shape: np.ndarray,
    cx: int,
    cy: int,
    z: int,
    radius: int,
    role: Role,
) -> None:
    """Fill a filled disk in the X-Y plane at depth ``z``, role ``role``.

    Out-of-bounds cells are silently dropped so pathologically small
    grids don't raise.
    """
    r2 = radius * radius
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx * dx + dy * dy <= r2:
                x, y = cx + dx, cy + dy
                if _in_bounds(x, y, z, shape):
                    placements.append((x, y, z, role))


def _emit_annulus(
    placements: list[Placement],
    shape: np.ndarray,
    cx: int,
    cy: int,
    z: int,
    outer: int,
    inner: int,
    role: Role,
) -> None:
    """Fill a ring (annulus) in the X-Y plane at depth ``z``, role ``role``."""
    out2 = outer * outer
    in2 = inner * inner
    for dx in range(-outer, outer + 1):
        for dy in range(-outer, outer + 1):
            d2 = dx * dx + dy * dy
            if in2 < d2 <= out2:
                x, y = cx + dx, cy + dy
                if _in_bounds(x, y, z, shape):
                    placements.append((x, y, z, role))


# --- per-style builders ----------------------------------------------------


def build_single_core(
    shape: np.ndarray,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """One large central engine — shuttles and dagger-fighters use this."""
    cx, cy, cz = position
    radius, length, _spread = size
    radius = max(1, radius)
    length = max(1, length)
    placements: list[Placement] = []
    for z_off in range(length):
        z = cz + z_off
        _emit_disk(placements, shape, cx, cy, z, radius, Role.ENGINE)
    # Glow core at the rear cap.
    _emit_disk(placements, shape, cx, cy, cz, max(1, radius - 1), Role.ENGINE_GLOW)
    return placements


def build_twin_nacelle(
    shape: np.ndarray,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Two side nacelles offset ``spread`` away from center on X."""
    cx, cy, cz = position
    radius, length, spread = size
    radius = max(1, radius)
    length = max(1, length)
    offset = max(radius + 1, spread)
    placements: list[Placement] = []
    for sign in (-1, +1):
        ex = cx + sign * offset
        for z_off in range(length):
            z = cz + z_off
            _emit_disk(placements, shape, ex, cy, z, radius, Role.ENGINE)
        _emit_disk(
            placements, shape, ex, cy, cz, max(1, radius - 1), Role.ENGINE_GLOW
        )
    return placements


def build_quad_cluster(
    shape: np.ndarray,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Four small engines in a 2x2 square — heavy cruiser look."""
    cx, cy, cz = position
    radius, length, spread = size
    # Each engine is smaller than a single-core but positioned in a grid.
    small_radius = max(1, radius - 1)
    length = max(1, length)
    offset = max(small_radius + 1, spread // 2 if spread > 0 else small_radius + 1)
    placements: list[Placement] = []
    for sx in (-1, +1):
        for sy in (-1, +1):
            ex = cx + sx * offset
            ey = cy + sy * offset
            for z_off in range(length):
                z = cz + z_off
                _emit_disk(placements, shape, ex, ey, z, small_radius, Role.ENGINE)
            _emit_disk(
                placements, shape, ex, ey, cz, max(1, small_radius - 1), Role.ENGINE_GLOW
            )
    return placements


def build_ring(
    shape: np.ndarray,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Hollow annular thruster — big outer ring with empty center, glow
    on the inner rim so the ring reads as a torus, not a disk."""
    cx, cy, cz = position
    radius, length, _spread = size
    outer = max(2, radius + 1)
    inner = max(1, outer - 2)
    length = max(1, length)
    placements: list[Placement] = []
    for z_off in range(length):
        z = cz + z_off
        _emit_annulus(placements, shape, cx, cy, z, outer, inner, Role.ENGINE)
    # Glow on the inner lip of the rear cap.
    _emit_annulus(
        placements, shape, cx, cy, cz, inner, max(0, inner - 1), Role.ENGINE_GLOW
    )
    return placements


def build_ion_array(
    shape: np.ndarray,
    position: tuple[int, int, int],
    size: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Horizontal row of small glow blocks — ion-drive aesthetic.

    Uses ``rng`` to jitter the per-block forward extent so the row reads
    as individually powered thrusters rather than a single strip. The
    jitter is deterministic given the caller's seed.
    """
    cx, cy, cz = position
    radius, length, spread = size
    radius = max(1, radius)
    length = max(1, length)
    spread = max(2, spread)
    # Fit as many blocks as will span ``2 * spread`` without overlap.
    block_size = max(1, radius)
    stride = block_size * 2 + 1
    W, _H, _L = shape.shape
    # Room on either side of center.
    half_span = min(spread, (W // 2) - block_size)
    if half_span < block_size:
        half_span = block_size
    placements: list[Placement] = []
    ex = cx - half_span
    while ex <= cx + half_span:
        jitter = int(rng.integers(0, 2))  # 0 or 1 extra cell of depth
        this_length = max(1, length - jitter)
        for z_off in range(this_length):
            z = cz + z_off
            for dx in range(-block_size // 2, block_size // 2 + 1):
                for dy in range(-block_size // 2, block_size // 2 + 1):
                    x, y = ex + dx, cy + dy
                    if _in_bounds(x, y, z, shape):
                        placements.append((x, y, z, Role.ENGINE))
        # Glow dot at the rear cap of each block.
        if _in_bounds(ex, cy, cz, shape):
            placements.append((ex, cy, cz, Role.ENGINE_GLOW))
        ex += stride
    return placements
