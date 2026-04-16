"""Tests for palette loading + block-state parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from litemapy import BlockState

from spaceship_generator.palette import (
    REQUIRED_ROLES,
    Palette,
    Role,
    list_palettes,
    load_palette,
    palettes_dir,
    parse_block_state,
)


# ----- parse_block_state -----

def test_parse_block_state_plain():
    bs = parse_block_state("minecraft:stone")
    assert isinstance(bs, BlockState)
    assert str(bs).startswith("minecraft:stone")


def test_parse_block_state_with_props():
    bs = parse_block_state("minecraft:redstone_lamp[lit=true]")
    s = str(bs)
    assert "redstone_lamp" in s
    assert "lit=true" in s


def test_parse_block_state_multi_props():
    bs = parse_block_state("minecraft:oak_stairs[facing=east,half=top]")
    s = str(bs)
    assert "facing=east" in s
    assert "half=top" in s


def test_parse_block_state_rejects_garbage():
    with pytest.raises(ValueError):
        parse_block_state("not a block")


def test_parse_block_state_rejects_bad_prop():
    with pytest.raises(ValueError):
        parse_block_state("minecraft:foo[=true]")


# ----- Palette -----

def test_required_roles_complete():
    # Every Role except EMPTY must be required.
    non_empty = {r.name for r in Role if r != Role.EMPTY}
    assert set(REQUIRED_ROLES) == non_empty


@pytest.mark.parametrize("palette_name", ["sci_fi_industrial", "sleek_modern", "rustic_salvage"])
def test_builtin_palettes_load(palette_name: str):
    pal = load_palette(palette_name)
    assert pal.name == palette_name
    # Every role maps to a BlockState.
    for role_name in REQUIRED_ROLES:
        role = Role[role_name]
        bs = pal.block_state(role)
        assert isinstance(bs, BlockState)
        # Preview color is 4-tuple of floats in [0..1].
        color = pal.preview_color(role)
        assert len(color) == 4
        for v in color:
            assert 0.0 <= v <= 1.0


def test_palette_rejects_missing_role(tmp_path: Path):
    bad = tmp_path / "broken.yaml"
    bad.write_text(
        "name: broken\nblocks:\n  HULL: minecraft:stone\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing block roles"):
        Palette.load(bad)


def test_palette_block_state_empty_raises():
    pal = load_palette("sci_fi_industrial")
    with pytest.raises(ValueError):
        pal.block_state(Role.EMPTY)


def test_palette_preview_color_empty_is_transparent():
    pal = load_palette("sci_fi_industrial")
    color = pal.preview_color(Role.EMPTY)
    assert color == (0.0, 0.0, 0.0, 0.0)


def test_list_palettes_includes_builtins():
    names = list_palettes()
    assert "sci_fi_industrial" in names
    assert "sleek_modern" in names
    assert "rustic_salvage" in names


def test_palettes_dir_exists():
    d = palettes_dir()
    assert d.exists()
    assert d.is_dir()


def test_load_missing_palette_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_palette("nonexistent_palette_xyz", search_dir=tmp_path)
