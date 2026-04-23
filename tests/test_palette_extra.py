"""Extra coverage tests for :mod:`spaceship_generator.palette`.

Focuses on ``_parse_color`` edge cases, ``validate_palette_file`` branches
that the main suite does not exercise (YAML errors, non-mapping top-level,
non-mapping blocks/preview_colors, non-string block specs, unknown roles),
and the ``list_palettes`` / ``from_dict`` gap paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spaceship_generator.palette import (
    REQUIRED_ROLES,
    Palette,
    Role,
    _parse_color,
    list_palettes,
    load_palette,
    validate_palette_file,
)

# ----------- _parse_color -----------


def test_parse_color_rgb_tuple():
    r, g, b, a = _parse_color([0.1, 0.2, 0.3])
    assert (r, g, b, a) == (pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.3), 1.0)


def test_parse_color_rgba_tuple():
    out = _parse_color([0.1, 0.2, 0.3, 0.5])
    assert out == (
        pytest.approx(0.1),
        pytest.approx(0.2),
        pytest.approx(0.3),
        pytest.approx(0.5),
    )


def test_parse_color_rgba_list_tuple_form():
    out = _parse_color((0.0, 1.0, 0.0, 1.0))
    assert out == (0.0, 1.0, 0.0, 1.0)


def test_parse_color_list_wrong_length_raises():
    with pytest.raises(ValueError):
        _parse_color([0.1, 0.2])
    with pytest.raises(ValueError):
        _parse_color([0.1, 0.2, 0.3, 0.4, 0.5])


def test_parse_color_hex_rrggbb():
    r, g, b, a = _parse_color("#ff8040")
    assert a == 1.0
    assert r == pytest.approx(1.0)
    assert g == pytest.approx(128 / 255)
    assert b == pytest.approx(64 / 255)


def test_parse_color_hex_rrggbbaa():
    r, g, b, a = _parse_color("#ff804080")
    assert r == pytest.approx(1.0)
    assert g == pytest.approx(128 / 255)
    assert b == pytest.approx(64 / 255)
    assert a == pytest.approx(128 / 255)


def test_parse_color_rejects_bad_string():
    with pytest.raises(ValueError):
        _parse_color("#fff")  # 3-digit shorthand not supported


def test_parse_color_rejects_unsupported_type():
    with pytest.raises(ValueError):
        _parse_color(12345)  # type: ignore[arg-type]


# ----------- Palette.from_dict -----------


def test_from_dict_missing_blocks_raises():
    with pytest.raises(ValueError, match="include 'name' and 'blocks'"):
        Palette.from_dict({"name": "x"})


def test_from_dict_missing_name_raises():
    with pytest.raises(ValueError, match="include 'name' and 'blocks'"):
        Palette.from_dict({"blocks": {}})


def test_from_dict_missing_preview_color_uses_gray_fallback():
    """No ``preview_colors`` mapping → every role gets mid-gray preview."""
    full = {
        "name": "minimal",
        "blocks": dict.fromkeys(REQUIRED_ROLES, "minecraft:stone"),
    }
    pal = Palette.from_dict(full)
    for r in REQUIRED_ROLES:
        role = Role[r]
        assert pal.preview_color(role) == (0.5, 0.5, 0.5, 1.0)


def test_from_dict_partial_preview_colors_fallback_only_for_missing_roles():
    """Only the omitted role falls back to gray; the rest keep their colors."""
    blocks = dict.fromkeys(REQUIRED_ROLES, "minecraft:stone")
    preview = {r: "#112233" for r in REQUIRED_ROLES if r != "WINDOW"}
    pal = Palette.from_dict(
        {"name": "partial", "blocks": blocks, "preview_colors": preview}
    )
    assert pal.preview_color(Role.WINDOW) == (0.5, 0.5, 0.5, 1.0)
    # Another role has the expected color.
    hull = pal.preview_color(Role.HULL)
    assert hull[0] == pytest.approx(0x11 / 255)
    assert hull[3] == 1.0


# ----------- validate_palette_file -----------


def _write_full(
    path: Path,
    *,
    extra_block: str = "",
    extra_preview: str = "",
) -> None:
    """Write a complete, valid palette YAML with optional extra entries.

    ``extra_block`` is appended under the ``blocks:`` section (indented two
    spaces). ``extra_preview`` is appended under ``preview_colors:``.
    """
    lines = ["name: sample", "blocks:"]
    for r in REQUIRED_ROLES:
        lines.append(f"  {r}: minecraft:stone")
    if extra_block:
        lines.append(f"  {extra_block}")
    lines.append("preview_colors:")
    for r in REQUIRED_ROLES:
        lines.append(f'  {r}: "#808080"')
    if extra_preview:
        lines.append(f"  {extra_preview}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validate_invalid_yaml(tmp_path: Path):
    """A file that isn't YAML at all produces a single 'invalid YAML' warning."""
    bad = tmp_path / "trash.yaml"
    # Unbalanced brackets upset PyYAML.
    bad.write_text(": : : [not-yaml", encoding="utf-8")
    warnings = validate_palette_file(bad)
    assert any("invalid YAML" in w for w in warnings)


def test_validate_non_mapping_top_level(tmp_path: Path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- one\n- two\n", encoding="utf-8")
    warnings = validate_palette_file(bad)
    assert any("top-level YAML must be a mapping" in w for w in warnings)


def test_validate_missing_name_key(tmp_path: Path):
    bad = tmp_path / "noname.yaml"
    bad.write_text("blocks:\n  HULL: minecraft:stone\n", encoding="utf-8")
    warnings = validate_palette_file(bad)
    assert any("missing top-level 'name'" in w for w in warnings)


def test_validate_missing_blocks_key(tmp_path: Path):
    bad = tmp_path / "noblocks.yaml"
    bad.write_text("name: foo\n", encoding="utf-8")
    warnings = validate_palette_file(bad)
    assert any("missing top-level 'blocks'" in w for w in warnings)


def test_validate_blocks_must_be_mapping(tmp_path: Path):
    """'blocks' being a list (not dict) produces a specific warning."""
    bad = tmp_path / "listblocks.yaml"
    bad.write_text(
        "name: foo\nblocks:\n  - minecraft:stone\n",
        encoding="utf-8",
    )
    warnings = validate_palette_file(bad)
    assert any("'blocks' must be a mapping" in w for w in warnings)


def test_validate_preview_colors_must_be_mapping(tmp_path: Path):
    pal = tmp_path / "listcolors.yaml"
    lines = ["name: foo", "blocks:"]
    for r in REQUIRED_ROLES:
        lines.append(f"  {r}: minecraft:stone")
    lines.append("preview_colors:")
    lines.append("  - '#808080'")
    pal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    warnings = validate_palette_file(pal)
    assert any(
        "'preview_colors' must be a mapping" in w for w in warnings
    )


def test_validate_block_spec_not_string(tmp_path: Path):
    pal = tmp_path / "intspec.yaml"
    lines = ["name: foo", "blocks:"]
    for r in REQUIRED_ROLES:
        if r == "HULL":
            lines.append(f"  {r}: 42")
        else:
            lines.append(f"  {r}: minecraft:stone")
    lines.append("preview_colors:")
    for r in REQUIRED_ROLES:
        lines.append(f'  {r}: "#808080"')
    pal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    warnings = validate_palette_file(pal)
    assert any(
        "must be a string" in w and "HULL" in w for w in warnings
    )


def test_validate_invalid_preview_color(tmp_path: Path):
    """A preview_color whose value can't be parsed is flagged."""
    pal = tmp_path / "badcolor.yaml"
    lines = ["name: foo", "blocks:"]
    for r in REQUIRED_ROLES:
        lines.append(f"  {r}: minecraft:stone")
    lines.append("preview_colors:")
    for r in REQUIRED_ROLES:
        if r == "WINDOW":
            lines.append(f"  {r}: 123")
        else:
            lines.append(f'  {r}: "#808080"')
    pal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    warnings = validate_palette_file(pal)
    assert any(
        "invalid preview_color" in w and "WINDOW" in w for w in warnings
    )


def test_validate_unknown_role_in_blocks(tmp_path: Path):
    pal = tmp_path / "unknown_role.yaml"
    _write_full(pal, extra_block="NOT_A_ROLE: minecraft:stone")
    warnings = validate_palette_file(pal)
    assert any("unknown role in 'blocks'" in w for w in warnings)


def test_validate_unknown_role_in_preview_colors(tmp_path: Path):
    """Unknown role keys inside preview_colors are flagged."""
    pal = tmp_path / "pc_unknown.yaml"
    _write_full(pal, extra_preview='NOT_A_ROLE: "#000000"')
    warnings = validate_palette_file(pal)
    assert any(
        "unknown role in 'preview_colors'" in w for w in warnings
    )


# ----------- list_palettes -----------


def test_list_palettes_missing_dir_returns_empty(tmp_path: Path):
    """A nonexistent search_dir returns an empty list, not a crash."""
    missing = tmp_path / "does_not_exist"
    assert list_palettes(search_dir=missing) == []


# ----------- autumn_harvest smoke test -----------


def test_autumn_harvest_loads_all_roles():
    """autumn_harvest must load and expose valid block states + preview colors for every role."""
    from litemapy import BlockState

    pal = load_palette("autumn_harvest")
    assert pal.name == "autumn_harvest"
    for role_name in REQUIRED_ROLES:
        role = Role[role_name]
        bs = pal.block_state(role)
        assert isinstance(bs, BlockState), f"autumn_harvest: {role_name} missing BlockState"
        assert "minecraft:" in str(bs), f"autumn_harvest: {role_name} block lacks minecraft: prefix"
        color = pal.preview_color(role)
        assert len(color) == 4, f"autumn_harvest: {role_name} preview_color is not 4-tuple"
        for v in color:
            assert 0.0 <= v <= 1.0, f"autumn_harvest: {role_name} color component out of range"
