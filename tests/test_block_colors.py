"""Tests for the approximate-block-color module.

These tests rely ONLY on the bundled on-disk cache (no network calls) by
passing ``allow_network=False``. The cache is populated by running the
module during development against the misode/mcmeta asset mirror.
"""

from __future__ import annotations

import pytest

from spaceship_generator.block_colors import (
    _candidate_textures,
    approximate_block_color,
    block_texture_png,
    hex_to_rgba,
)


def test_cache_has_common_palette_blocks():
    """Every block used in the shipped palettes should have a cached color."""
    expected = [
        "minecraft:iron_block",
        "minecraft:light_gray_concrete",
        "minecraft:sea_lantern",
        "minecraft:magma_block",
        "minecraft:snow_block",
        "minecraft:smooth_quartz",
        "minecraft:redstone_lamp[lit=true]",
    ]
    for block_id in expected:
        col = approximate_block_color(block_id, allow_network=False)
        assert col is not None, f"no cached color for {block_id}"
        assert col.startswith("#") and len(col) == 7, f"bad hex for {block_id}: {col!r}"


def test_unknown_block_returns_none_offline():
    """Unknown block + no network → None (does not raise)."""
    col = approximate_block_color(
        "minecraft:definitely_not_a_block", allow_network=False
    )
    assert col is None


def test_candidate_textures_includes_block_name():
    cands = _candidate_textures("minecraft:iron_block")
    assert "iron_block" in cands
    # Should also include common suffix variants.
    assert any(c.startswith("iron_block") for c in cands)


def test_candidate_textures_handles_blockstate_props():
    cands = _candidate_textures("minecraft:redstone_lamp[lit=true]")
    # Special mapping puts the lit texture first.
    assert cands[0] == "redstone_lamp_on"
    # Bare name still appears as a fallback.
    assert "redstone_lamp" in cands


def test_hex_to_rgba_round_trip():
    r, g, b, a = hex_to_rgba("#ff8040")
    assert a == 1.0
    assert abs(r - 1.0) < 1e-6
    assert abs(g - 128 / 255) < 1e-6
    assert abs(b - 64 / 255) < 1e-6


def test_hex_to_rgba_rejects_bad_format():
    with pytest.raises(ValueError):
        hex_to_rgba("not-a-color")


def test_block_texture_png_returns_cached_bytes():
    """Common palette blocks should have a cached PNG on disk."""
    png = block_texture_png("minecraft:iron_block", allow_network=False)
    assert png is not None
    assert png.startswith(b"\x89PNG"), "expected PNG magic bytes"


def test_block_texture_png_unknown_is_none_offline():
    png = block_texture_png(
        "minecraft:definitely_not_a_block", allow_network=False
    )
    assert png is None
