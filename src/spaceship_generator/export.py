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

    # Cache one BlockState per role to avoid re-parsing.
    block_cache: dict[int, object] = {}
    filled = np.argwhere(role_grid != Role.EMPTY)
    for x, y, z in filled:
        role_value = int(role_grid[x, y, z])
        bs = block_cache.get(role_value)
        if bs is None:
            bs = palette.block_state(Role(role_value))
            block_cache[role_value] = bs
        region[int(x), int(y), int(z)] = bs

    schem = region.as_schematic(name=name, author=author, description=description)
    schem.save(str(out_path))
    return out_path


def filled_voxel_count(role_grid: np.ndarray) -> int:
    """Return the number of non-empty cells in ``role_grid``."""
    return int(np.count_nonzero(role_grid != Role.EMPTY))
