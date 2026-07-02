"""Export a role grid to a Litematica ``.litematic`` file via litemapy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from litemapy import Region

from .palette import Palette, Role


def export_litematic(
    role_grid: np.ndarray,
    palette: Palette,
    out_path: str | Path,
    *,
    name: str = "spaceship",
    author: str = "spaceship-generator",
    description: str = "Procedurally generated spaceship",
) -> Path:
    """Write ``role_grid`` to ``out_path`` as a litematic schematic.

    ``role_grid`` is an integer numpy array indexed ``grid[x, y, z]`` where
    ``x`` is width (east/west), ``y`` is height (up), and ``z`` is length
    (north/south) — matching Minecraft's coordinate system and litemapy's
    :class:`Region` constructor ``Region(x, y, z, width, height, length)``.

    Cells equal to ``Role.EMPTY`` (0) are left as ``minecraft:air``.
    """
    if role_grid.ndim != 3:
        raise ValueError(f"role_grid must be 3D, got shape {role_grid.shape}")
    width, height, length = role_grid.shape
    if width <= 0 or height <= 0 or length <= 0:
        raise ValueError(f"role_grid dims must be positive, got {role_grid.shape}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    region = Region(0, 0, 0, width, height, length)

    # Fast path: determine each role's first-encounter order in C-order scan of
    # the filled voxels, pre-seed the region's block palette in that same
    # order, then vectorize the whole grid -> palette-index write.
    #
    # Why we bypass region[x, y, z] = bs (and region.setblock): litemapy's
    # per-voxel setters do ``block in self.__palette`` +
    # ``self.__palette.index(block)`` per write, which scans the palette
    # linearly using BlockState.__eq__. For a grid of ~15k filled voxels, that
    # is ~790k __eq__ calls (~31% of total time). We skip that entirely by
    # assigning palette indices directly to the region's internal uint32
    # blocks array. The palette pre-seeding below reproduces the exact same
    # palette ordering as the naive loop, so the resulting .litematic bytes
    # are identical.
    #
    # NOTE (H1, iter3): ``_Region__palette`` / ``_Region__blocks`` are
    # *name-mangled private* attributes on ``litemapy.Region``. They are an
    # implementation detail and may be renamed in any litemapy release. We
    # therefore probe for them defensively via ``getattr`` and fall back to a
    # slow-but-correct per-voxel ``region.setblock(...)`` loop on
    # AttributeError. If even ``setblock`` is missing on an older litemapy,
    # the inner fallback uses ``region[x, y, z] = bs``. This degrades a
    # litemapy upgrade that touches its internals from "every export crashes"
    # to "exports are slower but still correct".

    # Role values present in the grid, in first-encounter (C-order) order.
    flat = role_grid.ravel(order="C")
    nonzero_flat = flat[flat != Role.EMPTY]
    if nonzero_flat.size == 0:
        schem = region.as_schematic(name=name, author=author, description=description)
        schem.save(str(out_path))
        return out_path

    # np.unique with return_index gives us the first index each unique value
    # appears at. Sorting by those indices yields encounter order.
    unique_roles, first_idx = np.unique(nonzero_flat, return_index=True)
    order = np.argsort(first_idx)
    roles_in_order = unique_roles[order].tolist()

    # Resolve each role -> BlockState up front. Surfacing missing-role
    # mappings here (rather than mid-loop) keeps the error semantics the same
    # whether we end up taking the fast or slow path.
    role_to_block: dict[int, object] = {}
    for role_value in roles_in_order:
        try:
            role_enum = Role(role_value)
        except ValueError as exc:
            raise ValueError(
                f"palette {palette.name!r} missing block for role {role_value!r}"
            ) from exc
        try:
            role_to_block[int(role_value)] = palette.block_state(role_enum)
        except KeyError as exc:
            raise ValueError(
                f"palette {palette.name!r} missing block for role {role_enum!r}"
            ) from exc

    try:
        # Fast path — direct manipulation of litemapy's internal palette
        # list + blocks array. ``getattr`` with no default raises
        # AttributeError on a rename, which the except clause below catches.
        pal_list = region._Region__palette
        blocks = region._Region__blocks
        # Sanity-check that the attributes still look like what we expect;
        # a rename to a non-list / non-ndarray would otherwise corrupt
        # output silently. Re-raise as AttributeError to take the slow path.
        if not isinstance(pal_list, list):  # pragma: no cover - defensive
            raise AttributeError(
                "litemapy Region.__palette is not a list (incompatible version)"
            )
        if not hasattr(blocks, "__setitem__"):  # pragma: no cover - defensive
            raise AttributeError(
                "litemapy Region.__blocks is not array-like (incompatible version)"
            )

        # Append BlockStates to the palette in encounter order. ``len(pal_list)``
        # before append is the index this entry will land at; AIR already
        # occupies index 0, so new entries start at index 1.
        role_to_index: dict[int, int] = {}
        for role_value in roles_in_order:
            bs = role_to_block[int(role_value)]
            role_to_index[int(role_value)] = len(pal_list)
            pal_list.append(bs)

        # Build a small lookup table indexed by role_value -> palette index.
        # Role values are small non-negative ints (IntEnum), so a dense array
        # is fine.
        max_role = int(max(roles_in_order))
        lut = np.zeros(max_role + 1, dtype=np.uint32)
        for rv, pi in role_to_index.items():
            lut[rv] = pi

        # Clamp role_grid values through the LUT. Cells equal to Role.EMPTY
        # map to lut[0] == 0 (AIR), which matches the default zero-filled
        # blocks array. Any role value beyond max_role would be out of range,
        # but by construction every non-empty value in the grid is in
        # ``roles_in_order``.
        # role_grid may be any int dtype; cast through intp for safe indexing.
        blocks[...] = lut[role_grid.astype(np.intp, copy=False)]
    except AttributeError:
        # Slow fallback: litemapy renamed / removed its private blocks array.
        # Use the public per-voxel setter (or __setitem__ on even older
        # versions). Empty cells default to AIR in a fresh Region, so we
        # iterate only over filled voxels.
        setblock_fn = getattr(region, "setblock", None)
        if setblock_fn is None:
            def setblock_fn(x: int, y: int, z: int, bs: object) -> None:  # type: ignore[misc]
                region[x, y, z] = bs  # type: ignore[index]

        # np.argwhere gives (N, 3) of (x, y, z) for filled cells.
        filled_idx = np.argwhere(role_grid != Role.EMPTY)
        for xi, yi, zi in filled_idx:
            role_value = int(role_grid[xi, yi, zi])
            setblock_fn(int(xi), int(yi), int(zi), role_to_block[role_value])

    schem = region.as_schematic(name=name, author=author, description=description)
    schem.save(str(out_path))
    return out_path


def filled_voxel_count(role_grid: np.ndarray) -> int:
    """Return the number of non-empty cells in ``role_grid``."""
    return int(np.count_nonzero(role_grid != Role.EMPTY))
