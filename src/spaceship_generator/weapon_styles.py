"""Weapon archetype styles for ship armament placement.

This is a pure library of **placement builders** in the same style as
:mod:`greeble_styles`. Every builder takes an anchor cell and a seeded
:class:`numpy.random.Generator` and returns a fresh list of
``(x, y, z, Role)`` tuples. Builders never mutate their anchor nor the
caller's grid; the caller decides how and where to paint the cells.

Design contract
---------------
* **Pure**. Same seed + same anchor ⇒ byte-identical output. Builders
  must not touch global state or read any rng other than the one passed
  in.
* **Role-driven**. Every emitted cell carries a :class:`Role` so a
  painter can map it to blocks without reclassifying.
* **Top-facing**. :func:`scatter_weapons` samples anchors that are on a
  top-facing hull surface — weapons are not meant to be bolted to the
  underside.

Adding a new weapon type is a two-step change:

1. Add an enum member to :class:`WeaponType`.
2. Add a ``build_<type>`` pure builder and register it in the
   ``_BUILDERS`` dispatch table.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Sequence

import numpy as np

from .palette import Role


# Output type alias — a single voxel placement.
Placement = tuple[int, int, int, Role]


class WeaponType(str, Enum):
    """A weapon-emplacement archetype.

    * :attr:`TURRET_LARGE` — heavy gun: wide base + tall twin barrels + tip glow.
    * :attr:`MISSILE_POD` — 2x3 rack of missile tubes with glowing heads.
    * :attr:`LASER_LANCE` — long horizontal spire along the Z-axis.
    * :attr:`POINT_DEFENSE` — compact CIWS stub: 2x2 base + short barrel.
    * :attr:`PLASMA_CORE` — bulbous glowing emitter on a short pedestal.
    """

    TURRET_LARGE = "turret_large"
    MISSILE_POD = "missile_pod"
    LASER_LANCE = "laser_lance"
    POINT_DEFENSE = "point_defense"
    PLASMA_CORE = "plasma_core"


# --- builders ---------------------------------------------------------------
# Each builder returns a fresh list; callers own the result entirely.
# Coordinates are integer voxel space and may include out-of-bounds
# values — the caller is responsible for clipping before writing.


def build_turret_large(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Heavy turret: 3x3 base + two parallel barrels + glowing tips.

    Barrel length is rng-driven so a row of turrets looks individually
    tuned rather than stamped from one mold."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    barrel = int(rng.integers(2, 5))  # 2..4

    cells: list[Placement] = []
    # 3x3 dark base pad centered on anchor.
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            cells.append((x + dx, y, z + dz, Role.HULL_DARK))
    # Central mount cube one cell up.
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            cells.append((x + dx, y + 1, z + dz, Role.HULL))
    # Two barrels on either side of centerline along X.
    for side in (-1, +1):
        bx = x + side
        for i in range(1, barrel + 1):
            cells.append((bx, y + 1 + i, z, Role.HULL_DARK))
        cells.append((bx, y + 1 + barrel + 1, z, Role.LIGHT))
    return cells


def build_missile_pod(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Missile rack: 2x3 tubes with glowing warhead tips.

    rng chooses whether rows are 2 or 3 tubes long so neighbouring pods
    don't read as copy-paste."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    rows = int(rng.integers(2, 4))  # 2..3 tubes along Z
    cols = 2  # always two tubes along X for the "pod" read

    cells: list[Placement] = []
    # Dark frame 1 cell wider than the tube bed.
    for dx in range(-1, cols + 1):
        for dz in range(-1, rows + 1):
            cells.append((x + dx, y, z + dz, Role.HULL_DARK))
    # Missile tubes rise one cell above the frame with a glowing tip.
    for cx in range(cols):
        for cz in range(rows):
            cells.append((x + cx, y + 1, z + cz, Role.HULL))
            cells.append((x + cx, y + 2, z + cz, Role.ENGINE_GLOW))
    return cells


def build_laser_lance(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Long forward-facing spire along Z with a glowing muzzle.

    Length is the only rng-driven parameter — the silhouette stays stable
    while the reach varies from ship to ship."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    length = int(rng.integers(5, 9))  # 5..8 cells long

    cells: list[Placement] = []
    # Short pedestal: 1-cell dark base + 1-cell hull riser.
    cells.append((x, y, z, Role.HULL_DARK))
    cells.append((x, y + 1, z, Role.HULL))
    # Horizontal spire along +Z at the riser height.
    for i in range(1, length + 1):
        cells.append((x, y + 1, z + i, Role.HULL))
    # Glowing muzzle cap at the far end.
    cells.append((x, y + 1, z + length + 1, Role.LIGHT))
    return cells


def build_point_defense(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Compact CIWS stub: 2x2 base + short barrel + tip light.

    Only the barrel length varies so the overall footprint stays tight —
    point-defense turrets are supposed to look repeated."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    barrel = int(rng.integers(1, 3))  # 1..2

    cells: list[Placement] = []
    # 2x2 dark base.
    for dx in (0, 1):
        for dz in (0, 1):
            cells.append((x + dx, y, z + dz, Role.HULL_DARK))
    # Single central column on top of the base.
    for i in range(1, barrel + 1):
        cells.append((x, y + i, z, Role.HULL))
    cells.append((x, y + barrel + 1, z, Role.LIGHT))
    return cells


def build_plasma_core(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Bulbous glowing emitter: short pedestal + 3x3 glow ring + core.

    rng picks a pedestal height so arrays of cores have visual variety."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    pedestal = int(rng.integers(1, 3))  # 1..2

    cells: list[Placement] = []
    # Pedestal column.
    for i in range(pedestal):
        cells.append((x, y + i, z, Role.HULL))
    cy = y + pedestal
    # 3x3 glow ring around the core (center reserved).
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx == 0 and dz == 0:
                continue
            cells.append((x + dx, cy, z + dz, Role.ENGINE_GLOW))
    # Central plasma core one cell higher for dome effect.
    cells.append((x, cy, z, Role.LIGHT))
    cells.append((x, cy + 1, z, Role.ENGINE_GLOW))
    return cells


# Dispatch table — kept alongside the builders so ``build_weapon`` and
# ``scatter_weapons`` share one authoritative mapping.
_BUILDERS = {
    WeaponType.TURRET_LARGE: build_turret_large,
    WeaponType.MISSILE_POD: build_missile_pod,
    WeaponType.LASER_LANCE: build_laser_lance,
    WeaponType.POINT_DEFENSE: build_point_defense,
    WeaponType.PLASMA_CORE: build_plasma_core,
}


def build_weapon(
    weapon_type: WeaponType,
    anchor_xyz: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Dispatch to the right builder for ``weapon_type``.

    Raises :class:`ValueError` for an unknown enum — a safety net if a
    member is added without a matching builder."""
    builder = _BUILDERS.get(weapon_type)
    if builder is None:  # pragma: no cover - defensive
        raise ValueError(f"unknown WeaponType: {weapon_type!r}")
    return builder(anchor_xyz, rng)


# --- scatter ----------------------------------------------------------------


def _top_facing_anchors_from_grid(grid: np.ndarray) -> list[tuple[int, int, int]]:
    """Return non-empty cells whose +Y neighbor is empty (top-facing skin).

    Mirrors the greeble_styles private helper but lives here to keep this
    module a clean, standalone library — no cross-imports of private names.
    """
    W, H, L = grid.shape
    anchors: list[tuple[int, int, int]] = []
    for x in range(W):
        for z in range(L):
            for y in range(H - 1, -1, -1):
                if grid[x, y, z] != Role.EMPTY:
                    above_empty = (y + 1 >= H) or (grid[x, y + 1, z] == Role.EMPTY)
                    if above_empty:
                        anchors.append((x, y, z))
                    break
    return anchors


def _top_face_anchors_from_shape(
    shape: tuple[int, int, int],
) -> list[tuple[int, int, int]]:
    """Enumerate the top face of a bounding box as deterministic anchors.

    Used when the caller passes a ``(W, H, L)`` tuple rather than a
    populated grid."""
    W, H, L = (int(shape[0]), int(shape[1]), int(shape[2]))
    if W <= 0 or H <= 0 or L <= 0:
        return []
    y_top = max(0, H - 1)
    anchors: list[tuple[int, int, int]] = []
    for z in range(L):
        for x in range(W):
            anchors.append((x, y_top, z))
    return anchors


def _coerce_shape(shape: "np.ndarray | Sequence[int]") -> tuple[int, int, int]:
    """Accept either a numpy grid or a ``(W, H, L)`` tuple."""
    if isinstance(shape, np.ndarray):
        if shape.ndim != 3:
            raise ValueError(
                f"grid must be 3D (W, H, L); got {shape.ndim}D array"
            )
        return (int(shape.shape[0]), int(shape.shape[1]), int(shape.shape[2]))
    try:
        w, h, length = shape  # type: ignore[misc]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "shape must be a 3D numpy array or a (W, H, L) tuple"
        ) from exc
    return (int(w), int(h), int(length))


def scatter_weapons(
    shape: "np.ndarray | Sequence[int]",
    rng: np.random.Generator,
    count: int,
    *,
    types: Iterable[WeaponType] | None = None,
) -> list[Placement]:
    """Pick ``count`` top-facing anchors and build weapons on them.

    Parameters
    ----------
    shape:
        Either a 3-D :class:`numpy.ndarray` grid (anchors come from the
        top-facing hull cells) or a ``(W, H, L)`` bounding-box tuple
        (anchors come from the top face of the box).
    rng:
        Seeded :class:`numpy.random.Generator`. Same rng state + inputs
        ⇒ byte-identical output.
    count:
        Number of weapons to place. ``0`` returns ``[]`` without touching
        rng. If ``count`` exceeds the available anchors, every anchor is
        used exactly once.
    types:
        Optional allow-list of :class:`WeaponType` members. Defaults to
        every type.

    Returns
    -------
    list of ``(x, y, z, Role)``:
        All placements concatenated in deterministic order. May include
        out-of-bounds cells when the caller passed a bounding-box tuple.
    """
    if count < 0:
        raise ValueError(f"count must be >= 0; got {count!r}")
    if count == 0:
        return []

    if isinstance(shape, np.ndarray):
        if shape.ndim != 3:
            raise ValueError(
                f"grid must be 3D (W, H, L); got {shape.ndim}D array"
            )
        anchors = _top_facing_anchors_from_grid(shape)
    else:
        anchors = _top_face_anchors_from_shape(_coerce_shape(shape))

    if not anchors:
        return []

    allowed = list(types) if types is not None else list(WeaponType)
    if not allowed:
        return []
    # Dedupe while keeping caller order so the scatter is reproducible
    # regardless of whether the caller passed a set or a list.
    seen: set[WeaponType] = set()
    allowed = [t for t in allowed if not (t in seen or seen.add(t))]

    # Sample without replacement so the same anchor is never reused.
    take = min(int(count), len(anchors))
    anchor_indices = rng.choice(len(anchors), size=take, replace=False)
    # ``rng.choice`` returns a numpy array; iterate as ints.
    anchor_indices = [int(i) for i in anchor_indices]
    type_indices = rng.integers(0, len(allowed), size=take)

    out: list[Placement] = []
    for n, a_idx in enumerate(anchor_indices):
        weapon_type = allowed[int(type_indices[n])]
        out.extend(build_weapon(weapon_type, anchors[a_idx], rng))
    return out
