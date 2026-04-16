"""Round-trip tests for the litematic exporter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from litemapy import Schematic

from spaceship_generator.export import export_litematic, filled_voxel_count
from spaceship_generator.palette import Palette, Role, load_palette


@pytest.fixture
def palette():
    return load_palette("sci_fi_industrial")


def _tiny_grid() -> np.ndarray:
    """3x3x3 with a few roles set."""
    g = np.zeros((3, 3, 3), dtype=np.int8)
    g[0, 0, 0] = Role.HULL
    g[1, 0, 0] = Role.WINDOW
    g[2, 0, 0] = Role.ENGINE_GLOW
    g[0, 1, 0] = Role.LIGHT  # stateful block: redstone_lamp[lit=true]
    return g


def test_export_creates_file(tmp_path: Path, palette):
    grid = _tiny_grid()
    out = export_litematic(grid, palette, tmp_path / "tiny.litematic")
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_round_trip_blocks(tmp_path: Path, palette):
    grid = _tiny_grid()
    out = export_litematic(grid, palette, tmp_path / "rt.litematic")

    schem = Schematic.load(str(out))
    regions = list(schem.regions.values())
    assert len(regions) == 1
    region = regions[0]

    assert str(region[0, 0, 0]).startswith("minecraft:light_gray_concrete")
    assert "light_blue_stained_glass" in str(region[1, 0, 0])
    assert "sea_lantern" in str(region[2, 0, 0])
    s_lamp = str(region[0, 1, 0])
    assert "redstone_lamp" in s_lamp and "lit=true" in s_lamp

    # Empty cell should still be air.
    assert "air" in str(region[2, 2, 2])


def test_export_block_count_matches_filled(tmp_path: Path, palette):
    grid = _tiny_grid()
    out = export_litematic(grid, palette, tmp_path / "count.litematic")
    schem = Schematic.load(str(out))
    region = list(schem.regions.values())[0]

    non_air = 0
    for x in range(3):
        for y in range(3):
            for z in range(3):
                if "air" not in str(region[x, y, z]):
                    non_air += 1
    assert non_air == filled_voxel_count(grid)


def test_export_rejects_non_3d(tmp_path: Path, palette):
    with pytest.raises(ValueError):
        export_litematic(np.zeros((3, 3)), palette, tmp_path / "bad.litematic")


def test_export_rejects_zero_dim(tmp_path: Path, palette):
    with pytest.raises(ValueError):
        export_litematic(np.zeros((0, 3, 3), dtype=np.int8), palette, tmp_path / "bad.litematic")


def test_export_metadata(tmp_path: Path, palette):
    grid = _tiny_grid()
    out = export_litematic(
        grid, palette, tmp_path / "meta.litematic",
        name="MyShip", author="KazooKat", description="A cool one"
    )
    schem = Schematic.load(str(out))
    assert schem.name == "MyShip"
    assert schem.author == "KazooKat"
    assert schem.description == "A cool one"


def test_export_creates_missing_parent_dir(tmp_path: Path, palette):
    grid = _tiny_grid()
    nested = tmp_path / "a" / "b" / "c"
    out = export_litematic(grid, palette, nested / "s.litematic")
    assert out.exists()


def test_filled_voxel_count_zero():
    g = np.zeros((5, 5, 5), dtype=np.int8)
    assert filled_voxel_count(g) == 0


def test_filled_voxel_count_nonzero():
    g = np.zeros((5, 5, 5), dtype=np.int8)
    g[0, 0, 0] = Role.HULL
    g[4, 4, 4] = Role.WINDOW
    assert filled_voxel_count(g) == 2


def test_export_raises_valueerror_on_unmapped_role(tmp_path: Path, palette):
    # Build a palette lacking the HULL role and a grid that uses it. The
    # exporter should surface a ValueError explaining the missing mapping,
    # not a raw KeyError.
    partial = Palette(
        name="partial",
        blocks={r: palette.blocks[r] for r in palette.blocks if r != Role.HULL},
        preview_colors=palette.preview_colors,
    )
    grid = np.zeros((2, 2, 2), dtype=np.int8)
    grid[0, 0, 0] = Role.HULL

    with pytest.raises(ValueError) as excinfo:
        export_litematic(grid, partial, tmp_path / "missing_role.litematic")
    msg = str(excinfo.value)
    assert "partial" in msg
    assert "HULL" in msg or "role" in msg.lower()
