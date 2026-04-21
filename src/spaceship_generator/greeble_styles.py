"""Greeble archetype styles for surface detailing.

"Greebles" are the small surface details that sell a spaceship as built
rather than sculpted: antennas, dishes, vents, panel lines, turrets,
sensor pods. This module is a pure library of **placement builders** —
every function returns a list of ``(x, y, z, Role)`` tuples and never
touches the caller's grid. The caller decides whether to paint those
cells onto a numpy voxel array, a mesh, a preview canvas, or any other
surface.

Design contract
---------------
* **Pure**. Builders take an anchor point and an RNG; they never mutate
  inputs. Running the same builder with the same seed and the same
  anchor must produce identical output.
* **Cheap**. A single builder emits at most a few dozen cells. The
  scatter function controls totals via ``density``.
* **Role-driven**. Every emitted cell carries a :class:`Role` so a
  downstream painter can decide colors/blocks without re-classifying.

Adding a new greeble is a two-step change:

1. Add an enum member to :class:`GreebleType`.
2. Add a ``build_<type>`` pure builder and hook it into the dispatch in
   :func:`build_greeble` and :func:`scatter_greebles`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum

import numpy as np

from .palette import Role

# Output type alias — a single voxel placement.
Placement = tuple[int, int, int, Role]


class GreebleType(StrEnum):
    """A surface-detail archetype.

    * :attr:`TURRET` — compact gun stub: base + barrel + light tip.
    * :attr:`DISH` — radar/comms dish: stem + saucer + glowing pip.
    * :attr:`VENT` — rectangular grill of dark hull + glowing slits.
    * :attr:`ANTENNA` — thin vertical mast with a blinking tip light.
    * :attr:`PANEL_LINE` — short dark seam along the surface (flush).
    * :attr:`SENSOR_POD` — small housing with a window facing outward.
    """

    TURRET = "turret"
    DISH = "dish"
    VENT = "vent"
    ANTENNA = "antenna"
    PANEL_LINE = "panel_line"
    SENSOR_POD = "sensor_pod"


# --- builders ---------------------------------------------------------------
# Each builder returns a fresh list; callers own the result entirely.
# Coordinates are emitted in integer voxel space and may include negative
# or out-of-bounds values — it is the caller's job to clip before writing.


def build_turret(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Small turret: 3-cell base pad + a 1-3 cell barrel + glowing tip.

    The barrel grows straight up from the anchor; rng controls only the
    barrel length so the silhouette is stable while details vary."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    barrel = int(rng.integers(1, 4))  # 1..3

    cells: list[Placement] = []
    # Base pad (3x1x3) centered on anchor — darker hull for contrast.
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            cells.append((x + dx, y, z + dz, Role.HULL_DARK))
    # Barrel extending straight up.
    for i in range(1, barrel + 1):
        cells.append((x, y + i, z, Role.HULL))
    # Glowing tip.
    cells.append((x, y + barrel + 1, z, Role.LIGHT))
    return cells


def build_dish(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Comms dish: 1-cell stem + 3x3 saucer ring + center glow pip.

    rng only chooses stem height so the saucer shape is deterministic."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    stem = int(rng.integers(1, 3))  # 1..2

    cells: list[Placement] = []
    # Stem.
    for i in range(stem):
        cells.append((x, y + i, z, Role.HULL))
    # Saucer ring: 3x3 with center as glowing pip.
    sy = y + stem
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx == 0 and dz == 0:
                continue  # center reserved for the pip
            cells.append((x + dx, sy, z + dz, Role.HULL))
    cells.append((x, sy, z, Role.ENGINE_GLOW))
    return cells


def build_vent(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Vent grill: 3 or 5 slits on a dark panel, all flush with the skin.

    The vent is laid out along the Z-axis (ship length). rng picks slit
    count and whether the slits glow (engine vent) or stay dark (intake).
    """
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    slits = int(rng.choice([3, 5]))
    glow = bool(rng.integers(0, 2))
    slit_role = Role.ENGINE_GLOW if glow else Role.HULL_DARK

    half = slits // 2
    cells: list[Placement] = []
    # Dark backing panel — 1 wider than the slits in each direction.
    for dx in (-1, 0, 1):
        for dz in range(-half - 1, half + 2):
            cells.append((x + dx, y, z + dz, Role.HULL_DARK))
    # Slits along z, spaced 1 apart.
    for dz in range(-half, half + 1):
        cells.append((x, y, z + dz, slit_role))
    return cells


def build_antenna(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Thin vertical mast: 2-5 cells tall, blinking tip light.

    Height is the only random parameter — every antenna is a single
    column, so it reads cleanly against the hull silhouette."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    height = int(rng.integers(2, 6))  # 2..5

    cells: list[Placement] = []
    for i in range(height):
        cells.append((x, y + i, z, Role.HULL_DARK))
    cells.append((x, y + height, z, Role.LIGHT))
    return cells


def build_panel_line(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Short dark seam: 3-6 cells of ``HULL_DARK`` along a random axis.

    Flush with the anchor plane — no height is added. Reads as painted-on
    panel lines rather than a protrusion."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    length = int(rng.integers(3, 7))  # 3..6
    axis = int(rng.integers(0, 2))  # 0 = along X, 1 = along Z

    cells: list[Placement] = []
    for i in range(length):
        if axis == 0:
            cells.append((x + i, y, z, Role.HULL_DARK))
        else:
            cells.append((x, y, z + i, Role.HULL_DARK))
    return cells


def build_sensor_pod(
    anchor_xyz: tuple[int, int, int], rng: np.random.Generator,
) -> list[Placement]:
    """Small housing: 2x2 hull block with one window facing outward.

    The window Y offset is randomized so a cluster of pods doesn't all
    stare in the same direction."""
    x, y, z = (int(anchor_xyz[0]), int(anchor_xyz[1]), int(anchor_xyz[2]))
    window_dy = int(rng.integers(0, 2))  # 0 or 1

    cells: list[Placement] = []
    # 2x2 housing rising one cell above the anchor.
    for dx in (0, 1):
        for dy in (0, 1):
            cells.append((x + dx, y + dy, z, Role.HULL))
    # Carve a single window.
    cells.append((x, y + window_dy, z, Role.WINDOW))
    return cells


# Dispatch table — kept here so ``build_greeble`` and ``scatter_greebles``
# share one authoritative mapping. Order does not matter to callers.
_BUILDERS = {
    GreebleType.TURRET: build_turret,
    GreebleType.DISH: build_dish,
    GreebleType.VENT: build_vent,
    GreebleType.ANTENNA: build_antenna,
    GreebleType.PANEL_LINE: build_panel_line,
    GreebleType.SENSOR_POD: build_sensor_pod,
}


def build_greeble(
    greeble_type: GreebleType,
    anchor_xyz: tuple[int, int, int],
    rng: np.random.Generator,
) -> list[Placement]:
    """Dispatch to the right builder for ``greeble_type``.

    Raises :class:`ValueError` on an unknown enum — catches the case where
    a new member is added without a builder to match."""
    builder = _BUILDERS.get(greeble_type)
    if builder is None:  # pragma: no cover - protects against partial adds
        raise ValueError(f"unknown GreebleType: {greeble_type!r}")
    return builder(anchor_xyz, rng)


# --- scatter ----------------------------------------------------------------


def _surface_anchors(shape: tuple[int, int, int]) -> list[tuple[int, int, int]]:
    """Enumerate candidate surface cells for a bounding-box ``shape``.

    Without a populated occupancy grid we approximate "surface" as the
    top face of the bounding box plus the mid-height sides. That's a
    stable, deterministic set of cells the scatter can sample from; if
    a caller wants true hull-surface sampling they should pass an
    actual occupancy array and gate by adjacency to empty cells.
    """
    W, H, L = (int(shape[0]), int(shape[1]), int(shape[2]))
    if W <= 0 or H <= 0 or L <= 0:
        return []

    y_top = max(0, H - 1)
    y_mid = H // 2
    anchors: list[tuple[int, int, int]] = []
    # Top face — one row per Z.
    for z in range(L):
        for x in range(W):
            anchors.append((x, y_top, z))
    # Side strips at mid-height (X=0 and X=W-1), excluding corners already
    # on the top face.
    for z in range(L):
        if y_mid != y_top:
            anchors.append((0, y_mid, z))
            if W > 1:
                anchors.append((W - 1, y_mid, z))
    return anchors


def _surface_anchors_from_grid(grid: np.ndarray) -> list[tuple[int, int, int]]:
    """Return non-empty cells whose +Y neighbor is empty (top-facing skin).

    This is the precise variant of :func:`_surface_anchors`; using it
    guarantees greebles only anchor on cells that actually have hull."""
    W, H, L = grid.shape
    anchors: list[tuple[int, int, int]] = []
    for x in range(W):
        for z in range(L):
            # Scan from the top down to the first filled cell.
            for y in range(H - 1, -1, -1):
                if grid[x, y, z] != Role.EMPTY:
                    above_empty = (y + 1 >= H) or (grid[x, y + 1, z] == Role.EMPTY)
                    if above_empty:
                        anchors.append((x, y, z))
                    break
    return anchors


def _coerce_shape(shape: np.ndarray | Sequence[int]) -> tuple[int, int, int]:
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


def scatter_greebles(
    shape: np.ndarray | Sequence[int],
    rng: np.random.Generator,
    density: float,
    *,
    types: Iterable[GreebleType] | None = None,
) -> list[Placement]:
    """Pick surface anchors and build greebles over them.

    Parameters
    ----------
    shape:
        Either a 3-D :class:`numpy.ndarray` grid (in which case anchors
        are true top-facing hull cells) or a plain ``(W, H, L)`` tuple
        (in which case the bounding-box approximation is used).
    rng:
        A seeded :class:`numpy.random.Generator`. Same rng state +
        inputs ⇒ byte-identical output.
    density:
        Fraction of candidate anchors to populate, in ``[0.0, 1.0]``.
        ``0.0`` returns ``[]`` without consuming rng state;
        ``1.0`` populates every candidate.
    types:
        Optional allow-list of :class:`GreebleType` members to draw
        from. Defaults to every type.

    Returns
    -------
    list of ``(x, y, z, Role)``:
        All placements, concatenated in deterministic scatter order.
        May include out-of-bounds cells if ``shape`` is a bounding-box
        tuple — clip on write if that matters to you.
    """
    if not 0.0 <= float(density) <= 1.0:
        raise ValueError(f"density must be in [0, 1]; got {density!r}")

    if isinstance(shape, np.ndarray):
        if shape.ndim != 3:
            raise ValueError(
                f"grid must be 3D (W, H, L); got {shape.ndim}D array"
            )
        anchors = _surface_anchors_from_grid(shape)
    else:
        anchors = _surface_anchors(_coerce_shape(shape))

    if not anchors or density == 0.0:
        return []

    allowed = list(types) if types is not None else list(GreebleType)
    if not allowed:
        return []
    # Normalize to the canonical enum set and drop dupes while keeping order.
    seen: set[GreebleType] = set()
    allowed = [t for t in allowed if not (t in seen or seen.add(t))]

    # Bernoulli mask — one draw per anchor — then a type choice per hit.
    # Doing two separate calls to rng keeps the distribution independent
    # of allow-list size for the mask, which makes seeded scatter
    # reproducible regardless of ``types``.
    mask = rng.random(len(anchors)) < float(density)
    type_indices = rng.integers(0, len(allowed), size=int(mask.sum()))

    out: list[Placement] = []
    hit_i = 0
    for i, anchor in enumerate(anchors):
        if not mask[i]:
            continue
        greeble_type = allowed[int(type_indices[hit_i])]
        hit_i += 1
        out.extend(build_greeble(greeble_type, anchor, rng))
    return out
