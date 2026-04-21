"""Extra coverage tests for :mod:`spaceship_generator.block_colors`.

These tests exercise branches that the shipped on-disk cache cannot reach:
corrupt JSON caches, the network-fetch path (with mocked ``_fetch_png``),
average-color computation, animated-frame cropping, and the
``block_alpha`` fallback for unusual glass-family ids.

All network calls are monkeypatched — no real HTTP is made.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

import spaceship_generator.block_colors as bc
from spaceship_generator.block_colors import (
    _avg_color,
    _bare_block_name,
    _candidate_textures,
    _crop_first_frame,
    _fetch_png,
    approximate_block_color,
    block_alpha,
    block_texture_png,
    hex_to_rgba,
)

# ----------- helpers -----------


def _reset_caches(monkeypatch, tmpdir: Path) -> None:
    """Redirect caches to a fresh temp dir and clear in-memory state."""
    monkeypatch.setattr(bc, "_MEM_CACHE", None)
    monkeypatch.setattr(bc, "_STEM_MEM_CACHE", None)
    monkeypatch.setattr(bc, "_data_dir", lambda: tmpdir)


def _make_solid_png(color: tuple[int, int, int, int], size: int = 4) -> bytes:
    """Return PNG bytes for a solid-color square (requires Pillow)."""
    from PIL import Image

    im = Image.new("RGBA", (size, size), color=color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _make_strip_png(frames: int = 3, size: int = 4) -> bytes:
    """Return a vertical-strip animated-style PNG (height > width, multiple of width)."""
    from PIL import Image

    # Frame 0 is pure red; subsequent frames are other colors. The first
    # frame color drives the expected cropped output.
    im = Image.new("RGBA", (size, size * frames), color=(0, 255, 0, 255))
    red_top = Image.new("RGBA", (size, size), color=(255, 0, 0, 255))
    im.paste(red_top, (0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


# ----------- _load_cache / _save_cache -----------


def test_load_cache_handles_corrupt_json(monkeypatch, tmp_path: Path):
    """A corrupt cache file must degrade gracefully to an empty dict."""
    _reset_caches(monkeypatch, tmp_path)
    cache_file = tmp_path / "block_colors.json"
    cache_file.write_text("}{not valid json", encoding="utf-8")

    data = bc._load_cache()
    assert isinstance(data, dict)
    assert data == {}


def test_load_cache_caches_in_memory(monkeypatch, tmp_path: Path):
    """Second call must reuse the in-memory dict (mutations visible)."""
    _reset_caches(monkeypatch, tmp_path)
    first = bc._load_cache()
    first["sentinel"] = "#abcdef"
    second = bc._load_cache()
    assert second is first
    assert second.get("sentinel") == "#abcdef"


def test_load_cache_ignores_non_dict_json(monkeypatch, tmp_path: Path):
    """A JSON list/number must not be loaded as the cache."""
    _reset_caches(monkeypatch, tmp_path)
    (tmp_path / "block_colors.json").write_text("[1, 2, 3]", encoding="utf-8")
    data = bc._load_cache()
    assert data == {}


def test_save_cache_round_trip(monkeypatch, tmp_path: Path):
    """_save_cache writes to disk; re-load reads the same mapping back."""
    _reset_caches(monkeypatch, tmp_path)
    cache = bc._load_cache()
    cache["minecraft:stone"] = "#7f7f7f"
    bc._save_cache()

    # Force a fresh disk read.
    monkeypatch.setattr(bc, "_MEM_CACHE", None)
    reloaded = bc._load_cache()
    assert reloaded["minecraft:stone"] == "#7f7f7f"


def test_save_cache_noop_when_never_loaded(monkeypatch, tmp_path: Path):
    """Calling _save_cache with no in-memory cache writes nothing."""
    _reset_caches(monkeypatch, tmp_path)
    # _MEM_CACHE is None; _save_cache must silently return.
    bc._save_cache()
    assert not (tmp_path / "block_colors.json").exists()


# ----------- _fetch_png (urllib mocked) -----------


class _FakeResp:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_png_returns_bytes_on_200(monkeypatch):
    payload = b"\x89PNG\r\n\x1a\nfake"

    def _ok(url, timeout=5.0):
        assert url.endswith(".png")
        return _FakeResp(200, payload)

    monkeypatch.setattr(bc.urllib.request, "urlopen", _ok)
    assert _fetch_png("stone") == payload


def test_fetch_png_returns_none_on_non_200(monkeypatch):
    monkeypatch.setattr(
        bc.urllib.request,
        "urlopen",
        lambda url, timeout=5.0: _FakeResp(404, b""),
    )
    assert _fetch_png("missing") is None


def test_fetch_png_returns_none_on_url_error(monkeypatch):
    def _raise(url, timeout=5.0):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(bc.urllib.request, "urlopen", _raise)
    assert _fetch_png("stone") is None


def test_fetch_png_returns_none_on_timeout(monkeypatch):
    def _raise(url, timeout=5.0):
        raise TimeoutError("slow")

    monkeypatch.setattr(bc.urllib.request, "urlopen", _raise)
    assert _fetch_png("stone") is None


def test_fetch_png_returns_none_on_os_error(monkeypatch):
    def _raise(url, timeout=5.0):
        raise OSError("disk?")

    monkeypatch.setattr(bc.urllib.request, "urlopen", _raise)
    assert _fetch_png("stone") is None


# ----------- _avg_color -----------


def test_avg_color_solid_color_returns_expected_hex():
    pytest.importorskip("PIL")
    png = _make_solid_png((255, 0, 0, 255))
    assert _avg_color(png) == "#ff0000"


def test_avg_color_all_transparent_returns_none():
    pytest.importorskip("PIL")
    png = _make_solid_png((128, 64, 32, 0))
    assert _avg_color(png) is None


def test_avg_color_bad_bytes_returns_none():
    """Garbage input must not raise — Pillow decode failure yields None."""
    pytest.importorskip("PIL")
    assert _avg_color(b"not a png") is None


def test_avg_color_animated_strip_uses_first_frame():
    """Vertical strips (h > w and h%w==0) crop to the first square frame."""
    pytest.importorskip("PIL")
    # The helper paints a red top frame and green below. Averaging only the
    # first frame must give a pure-red result.
    png = _make_strip_png(frames=3, size=4)
    assert _avg_color(png) == "#ff0000"


def test_avg_color_weighted_by_alpha():
    """Semi-transparent pixels contribute proportionally to their alpha."""
    pytest.importorskip("PIL")
    from PIL import Image

    # Two-pixel image: one fully red opaque, one fully blue with tiny alpha.
    im = Image.new("RGBA", (2, 1))
    im.putpixel((0, 0), (255, 0, 0, 255))
    im.putpixel((1, 0), (0, 0, 255, 1))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    result = _avg_color(buf.getvalue())
    # Red must dominate because blue's weight is only 1/256.
    assert result is not None
    r = int(result[1:3], 16)
    b = int(result[5:7], 16)
    assert r > b


# ----------- _crop_first_frame -----------


def test_crop_first_frame_square_is_untouched():
    """Square textures return byte-identical input."""
    pytest.importorskip("PIL")
    png = _make_solid_png((1, 2, 3, 255), size=8)
    assert _crop_first_frame(png) == png


def test_crop_first_frame_strip_is_cropped():
    """Vertical strips are cropped and re-encoded."""
    pytest.importorskip("PIL")
    from PIL import Image

    png = _make_strip_png(frames=4, size=6)
    cropped_bytes = _crop_first_frame(png)
    assert cropped_bytes != png
    im = Image.open(io.BytesIO(cropped_bytes))
    assert im.size == (6, 6)


def test_crop_first_frame_bad_bytes_returns_input_unchanged():
    """Non-PNG input must round-trip untouched — not raise."""
    pytest.importorskip("PIL")
    garbage = b"definitely not a png"
    assert _crop_first_frame(garbage) == garbage


# ----------- approximate_block_color (network path) -----------


def test_approximate_block_color_uses_fetched_png(monkeypatch, tmp_path: Path):
    """A fresh cache + a network hit caches and returns the averaged color."""
    pytest.importorskip("PIL")
    _reset_caches(monkeypatch, tmp_path)
    payload = _make_solid_png((0, 128, 0, 255))

    calls: list[str] = []

    def _fake_fetch(stem: str, timeout: float = 5.0) -> bytes | None:
        calls.append(stem)
        return payload

    monkeypatch.setattr(bc, "_fetch_png", _fake_fetch)

    col = approximate_block_color("minecraft:stone")
    assert col == "#008000"
    # First candidate should have been tried.
    assert calls and calls[0] == "stone"

    # Second call must come from the cache — no new fetch.
    calls.clear()
    assert approximate_block_color("minecraft:stone") == "#008000"
    assert calls == []


def test_approximate_block_color_negative_caches_unresolvable(
    monkeypatch, tmp_path: Path
):
    """Failed lookups are negative-cached as ``""`` and still return None."""
    _reset_caches(monkeypatch, tmp_path)
    monkeypatch.setattr(bc, "_fetch_png", lambda stem, timeout=5.0: None)

    assert approximate_block_color("minecraft:nonexistent") is None
    # Cache should now have an empty string sentinel.
    cache = bc._load_cache()
    assert cache.get("minecraft:nonexistent") == ""
    # Subsequent call must not touch fetch either (allow_network=False).
    assert (
        approximate_block_color(
            "minecraft:nonexistent", allow_network=False
        )
        is None
    )


def test_approximate_block_color_skips_when_avg_color_returns_none(
    monkeypatch, tmp_path: Path
):
    """If an image is entirely transparent we keep trying later candidates."""
    pytest.importorskip("PIL")
    _reset_caches(monkeypatch, tmp_path)

    transparent = _make_solid_png((0, 0, 0, 0))
    solid = _make_solid_png((32, 64, 96, 255))

    def _fetcher(stem: str, timeout: float = 5.0) -> bytes | None:
        # First call -> all-transparent; later calls -> a real color.
        if stem == "stone":
            return transparent
        return solid

    monkeypatch.setattr(bc, "_fetch_png", _fetcher)
    col = approximate_block_color("minecraft:stone")
    assert col == "#204060"


# ----------- block_texture_png (network path + stem cache) -----------


def test_block_texture_png_stem_cache_corrupt_is_empty(
    monkeypatch, tmp_path: Path
):
    """A bad stem-cache JSON degrades to empty without raising."""
    _reset_caches(monkeypatch, tmp_path)
    (tmp_path / "block_texture_stems.json").write_text(
        "}{}bogus", encoding="utf-8"
    )
    stems = bc._load_stem_cache()
    assert stems == {}


def test_block_texture_png_stem_cache_non_dict_is_empty(
    monkeypatch, tmp_path: Path
):
    _reset_caches(monkeypatch, tmp_path)
    (tmp_path / "block_texture_stems.json").write_text(
        json.dumps(["a", "b"]), encoding="utf-8"
    )
    assert bc._load_stem_cache() == {}


def test_block_texture_png_caches_in_memory(monkeypatch, tmp_path: Path):
    _reset_caches(monkeypatch, tmp_path)
    first = bc._load_stem_cache()
    first["minecraft:foo"] = "foo"
    second = bc._load_stem_cache()
    assert second is first


def test_block_texture_png_returns_none_for_negative_cached_block(
    monkeypatch, tmp_path: Path
):
    """An empty-string stem in cache means 'known-bad' → None even online."""
    _reset_caches(monkeypatch, tmp_path)
    bc._load_stem_cache()["minecraft:nope"] = ""
    # Even with network allowed, negative cache must short-circuit.
    called = []
    monkeypatch.setattr(
        bc, "_fetch_png", lambda s, timeout=5.0: called.append(s) or None
    )
    assert block_texture_png("minecraft:nope") is None
    assert called == []


def test_block_texture_png_reads_from_disk_when_stem_cached(
    monkeypatch, tmp_path: Path
):
    """A cached stem pointing at an on-disk file returns those bytes."""
    pytest.importorskip("PIL")
    _reset_caches(monkeypatch, tmp_path)
    texture_dir = tmp_path / "block_textures"
    texture_dir.mkdir(parents=True)
    payload = _make_solid_png((10, 20, 30, 255))
    (texture_dir / "mystem.png").write_bytes(payload)
    bc._load_stem_cache()["minecraft:myblock"] = "mystem"

    # No fetch should happen.
    def _should_not_fetch(s, timeout=5.0):
        raise AssertionError(f"unexpected fetch for {s}")

    monkeypatch.setattr(bc, "_fetch_png", _should_not_fetch)
    assert block_texture_png("minecraft:myblock") == payload


def test_block_texture_png_network_path_writes_disk_and_caches_stem(
    monkeypatch, tmp_path: Path
):
    """On first miss + fetched data we write to disk and remember the stem."""
    pytest.importorskip("PIL")
    _reset_caches(monkeypatch, tmp_path)

    payload = _make_solid_png((200, 100, 50, 255), size=4)

    def _fetch(stem: str, timeout: float = 5.0) -> bytes | None:
        return payload if stem == "iron_block" else None

    monkeypatch.setattr(bc, "_fetch_png", _fetch)

    data = block_texture_png("minecraft:iron_block")
    assert data == payload
    # Disk + stem cache both populated.
    assert (tmp_path / "block_textures" / "iron_block.png").exists()
    assert bc._load_stem_cache()["minecraft:iron_block"] == "iron_block"


def test_block_texture_png_negative_caches_when_nothing_fetched(
    monkeypatch, tmp_path: Path
):
    _reset_caches(monkeypatch, tmp_path)
    monkeypatch.setattr(bc, "_fetch_png", lambda s, timeout=5.0: None)
    assert block_texture_png("minecraft:ghost_block") is None
    assert bc._load_stem_cache().get("minecraft:ghost_block") == ""


def test_block_texture_png_returns_none_when_offline_and_uncached(
    monkeypatch, tmp_path: Path
):
    _reset_caches(monkeypatch, tmp_path)
    # allow_network=False and no cached stem for this id → early None.
    assert block_texture_png(
        "minecraft:unknown_block_xyz", allow_network=False
    ) is None


# ----------- candidate-texture generation edge cases -----------


def test_candidate_textures_uses_fallback_list():
    """Hyphae blocks map to the stem name via the fallback table."""
    cands = _candidate_textures("minecraft:crimson_hyphae")
    # The fallback's 'crimson_stem' must appear before the bare-name attempts.
    assert "crimson_stem" in cands
    idx_stem = cands.index("crimson_stem")
    idx_hyphae = cands.index("crimson_hyphae")
    assert idx_stem < idx_hyphae


def test_candidate_textures_garbage_returns_empty():
    """A string that does not match the block-id regex yields no candidates."""
    assert _candidate_textures("NOT A BLOCK ID") == []


def test_candidate_textures_dedupes_repeats():
    """Returned stems must be unique in order."""
    cands = _candidate_textures("minecraft:iron_block")
    assert len(cands) == len(set(cands))


# ----------- is_translucent / block_alpha edge coverage -----------


def test_block_alpha_generic_glass_fallback():
    """An unusual glass-containing id falls into the final 0.4 branch."""
    # ``glass`` substring but not in any of the specific-id sets and not
    # matching stained_glass.
    assert block_alpha("minecraft:reinforced_glass_brick") == pytest.approx(0.4)


def test_block_alpha_respects_translucent_override():
    """honey/slime tier is 0.75 — higher than glass/ice but < 1."""
    assert block_alpha("minecraft:honey_block") > block_alpha("minecraft:glass")
    assert block_alpha("minecraft:slime_block") < block_alpha("minecraft:stone")


def test_bare_block_name_strips_namespace_and_state():
    assert (
        _bare_block_name(
            "minecraft:light_blue_stained_glass[waterlogged=true]"
        )
        == "light_blue_stained_glass"
    )
    assert _bare_block_name("minecraft:stone") == "stone"
    assert _bare_block_name("  STONE  ") == "stone"


def test_hex_to_rgba_case_insensitive():
    a = hex_to_rgba("#A1B2C3")
    b = hex_to_rgba("#a1b2c3")
    assert a == b
