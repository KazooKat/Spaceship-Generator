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
    validate_palette_file,
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


# ----- New themed palettes -----

NEW_PALETTES = (
    "stealth_black",
    "ice_crystal",
    "crimson_nether",
    "alien_bio",
    "gold_imperial",
    "diamond_tech",
    "end_void",
    "coral_reef",
    "candy_pop",
    "neon_arcade",
    "wooden_frigate",
    "desert_sandstone",
    "deepslate_drone",
    "amethyst_crystal",
    "nordic_scout",
)


@pytest.mark.parametrize("palette_name", NEW_PALETTES)
def test_new_palette_loads(palette_name: str):
    """Each new palette must load via load_palette() without errors."""
    pal = load_palette(palette_name)
    assert pal.name == palette_name


@pytest.mark.parametrize("palette_name", NEW_PALETTES)
def test_new_palette_textures_all_fine_roles(palette_name: str):
    """End-to-end: generating with each palette should exercise every fine role.

    The texture pass (HULL_DARK stripes, WINDOW grid, ENGINE_GLOW faces, LIGHT
    tips, INTERIOR infill) must fire regardless of palette choice — verifies
    the new palettes aren't just color swaps but are actually textured by the
    pipeline.
    """
    import numpy as np

    from spaceship_generator.shape import ShapeParams, generate_shape
    from spaceship_generator.texture import TextureParams, assign_roles

    sp = ShapeParams(length=40, width_max=20, height_max=12, engine_count=2)
    tp = TextureParams(
        window_period_cells=4,
        accent_stripe_period=8,
        engine_glow_depth=1,
        panel_line_bands=2,
        rivet_period=6,
        engine_glow_ring=True,
    )
    grid = assign_roles(generate_shape(42, sp), tp)

    for role in (
        Role.HULL,
        Role.HULL_DARK,
        Role.WINDOW,
        Role.ENGINE_GLOW,
        Role.LIGHT,
        Role.INTERIOR,
    ):
        assert np.any(grid == role), f"{palette_name}: role {role.name} not generated"


@pytest.mark.parametrize("palette_name", NEW_PALETTES)
def test_new_palette_has_all_roles(palette_name: str):
    """Each new palette must define all 10 required roles with valid BlockStates."""
    pal = load_palette(palette_name)
    for role_name in REQUIRED_ROLES:
        role = Role[role_name]
        bs = pal.block_state(role)
        assert isinstance(bs, BlockState)
        assert "minecraft:" in str(bs)
        color = pal.preview_color(role)
        assert len(color) == 4
        for v in color:
            assert 0.0 <= v <= 1.0


def test_list_palettes_includes_new_palettes():
    names = list_palettes()
    for n in NEW_PALETTES:
        assert n in names


# ----- validate_palette_file -----

def _write_full_palette(path: Path, name: str = "valid", *, drop_color: str | None = None):
    """Write a fully-populated palette YAML, optionally dropping one preview_color."""
    lines = [f"name: {name}", "blocks:"]
    for role in REQUIRED_ROLES:
        lines.append(f"  {role}: minecraft:stone")
    lines.append("preview_colors:")
    for role in REQUIRED_ROLES:
        if role == drop_color:
            continue
        lines.append(f'  {role}: "#808080"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validate_palette_file_returns_empty_for_valid(tmp_path: Path):
    good = tmp_path / "good.yaml"
    _write_full_palette(good)
    assert validate_palette_file(good) == []


def test_validate_palette_file_flags_missing_preview_color(tmp_path: Path):
    pal = tmp_path / "no_color.yaml"
    _write_full_palette(pal, drop_color="WINDOW")
    warnings = validate_palette_file(pal)
    assert any("preview_color" in w and "WINDOW" in w for w in warnings), warnings


def test_validate_palette_file_flags_missing_block(tmp_path: Path):
    pal = tmp_path / "broken.yaml"
    pal.write_text(
        "name: broken\nblocks:\n  HULL: minecraft:stone\n",
        encoding="utf-8",
    )
    warnings = validate_palette_file(pal)
    # Should flag 9 missing blocks + missing preview_colors entries.
    assert any("missing block" in w for w in warnings)


def test_validate_palette_file_flags_unknown_key(tmp_path: Path):
    pal = tmp_path / "extra.yaml"
    _write_full_palette(pal)
    # Append an unknown top-level key.
    with pal.open("a", encoding="utf-8") as f:
        f.write("bogus_key: 42\n")
    warnings = validate_palette_file(pal)
    assert any("unknown top-level key" in w and "bogus_key" in w for w in warnings), warnings


def test_validate_palette_file_flags_invalid_block_state(tmp_path: Path):
    pal = tmp_path / "bad_bs.yaml"
    _write_full_palette(pal)
    # Overwrite with one invalid block state.
    text = pal.read_text(encoding="utf-8")
    text = text.replace("  HULL: minecraft:stone", "  HULL: not a block")
    pal.write_text(text, encoding="utf-8")
    warnings = validate_palette_file(pal)
    assert any("invalid block state" in w and "HULL" in w for w in warnings), warnings


def test_validate_palette_file_missing_file(tmp_path: Path):
    warnings = validate_palette_file(tmp_path / "nope.yaml")
    assert any("does not exist" in w for w in warnings)


def test_validate_builtin_palettes_clean():
    """All shipped palettes should validate with zero warnings."""
    for name in list_palettes():
        path = palettes_dir() / f"{name}.yaml"
        assert validate_palette_file(path) == [], f"{name} had warnings"


# ----- list_palettes(include_errors=True) -----

def test_list_palettes_include_errors_returns_tuples(tmp_path: Path):
    _write_full_palette(tmp_path / "alpha.yaml", name="alpha")
    _write_full_palette(tmp_path / "beta.yaml", name="beta", drop_color="HULL")
    entries = list_palettes(search_dir=tmp_path, include_errors=True)
    assert isinstance(entries, list)
    assert all(isinstance(e, tuple) and len(e) == 2 for e in entries)
    names = [name for name, _ in entries]
    assert names == ["alpha", "beta"]
    by_name = dict(entries)
    assert by_name["alpha"] == []
    assert any("preview_color" in w and "HULL" in w for w in by_name["beta"])


def test_list_palettes_default_unchanged(tmp_path: Path):
    """include_errors=False must return plain list[str] (backward compat)."""
    _write_full_palette(tmp_path / "one.yaml", name="one")
    _write_full_palette(tmp_path / "two.yaml", name="two")
    names = list_palettes(search_dir=tmp_path)
    assert names == ["one", "two"]
    assert all(isinstance(n, str) for n in names)


# ----- Path-aware error messages -----

def test_palette_load_error_includes_path(tmp_path: Path):
    bad = tmp_path / "incomplete.yaml"
    bad.write_text(
        "name: incomplete\nblocks:\n  HULL: minecraft:stone\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        Palette.load(bad)
    msg = str(excinfo.value)
    assert str(bad) in msg
    assert "missing block roles" in msg


def test_load_palette_error_includes_path(tmp_path: Path):
    bad = tmp_path / "incomplete.yaml"
    bad.write_text(
        "name: incomplete\nblocks:\n  HULL: minecraft:stone\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_palette("incomplete", search_dir=tmp_path)
    msg = str(excinfo.value)
    assert str(bad) in msg


def test_from_dict_error_does_not_include_path():
    """from_dict should not mention a path — only load() wraps the error."""
    with pytest.raises(ValueError) as excinfo:
        Palette.from_dict({"name": "bare", "blocks": {"HULL": "minecraft:stone"}})
    assert "missing block roles" in str(excinfo.value)
    # Ensure no path-injection leaked in.
    assert ".yaml" not in str(excinfo.value)


# ----- M18: palette × structure_style cross-coverage -----

def _cross_cases() -> list[tuple[str, str]]:
    """Return ``[(style_value, palette_name), ...]`` for full cross-product.

    Sorted palette names keep parametrize IDs stable. The meta ``"random"``
    value is filtered out defensively in case it is ever added to the
    shipped list.
    """
    from spaceship_generator.structure_styles import StructureStyle

    palette_names = sorted(
        n for n in list_palettes() if n != "random"
    )
    cases: list[tuple[str, str]] = []
    for style in StructureStyle:
        for pal_name in palette_names:
            cases.append((style.value, pal_name))
    return cases


@pytest.mark.parametrize(
    "style_value,palette_name",
    _cross_cases(),
    ids=lambda v: v,
)
def test_generate_palette_x_structure_style_cross(
    style_value: str, palette_name: str, tmp_path: Path
):
    """Every StructureStyle × every palette must generate without exception."""
    from spaceship_generator.generator import generate
    from spaceship_generator.shape import ShapeParams
    from spaceship_generator.structure_styles import StructureStyle

    style = StructureStyle(style_value)
    params = ShapeParams(structure_style=style)
    result = generate(
        seed=17,
        palette=palette_name,
        shape_params=params,
        out_dir=tmp_path,
        with_preview=False,
    )
    assert result.block_count > 0
    assert result.role_grid.shape == (
        params.width_max,
        params.height_max,
        params.length,
    )
