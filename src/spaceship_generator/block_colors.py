"""Approximate display colors for Minecraft block states.

Samples the primary texture of each block from the ``misode/mcmeta`` vanilla
asset mirror (``https://github.com/misode/mcmeta``), computes the
alpha-weighted mean pixel color, and caches the result as a bundled JSON file
so subsequent runs work offline.

Usage
-----
``approximate_block_color("minecraft:iron_block")`` returns ``"#d8d8d8"`` or
similar. Unknown or unreachable blocks return ``None``.
"""

from __future__ import annotations

import io
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

try:  # pragma: no cover - import guard
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]


_MCMETA_BASE = (
    "https://raw.githubusercontent.com/misode/mcmeta/assets/"
    "assets/minecraft/textures/block/"
)

# Exact-match overrides: full block-state spec -> preferred texture stem.
_SPECIAL: dict[str, str] = {
    "minecraft:redstone_lamp[lit=true]": "redstone_lamp_on",
}

# Per-block texture hints when the default ``<name>.png`` doesn't exist.
_NAME_FALLBACKS: dict[str, list[str]] = {
    "crimson_hyphae": ["crimson_stem"],
    "warped_hyphae": ["warped_stem"],
    "glass_pane": ["glass"],
    "furnace": ["furnace_front", "furnace_side"],
    "magma_block": ["magma"],
    "snow_block": ["snow"],
    "smooth_quartz": ["quartz_block_bottom"],
    "quartz_block": ["quartz_block_side", "quartz_block_top"],
    "smooth_stone": ["smooth_stone", "smooth_stone_slab_side"],
    "smooth_sandstone": ["sandstone_top"],
    "smooth_red_sandstone": ["red_sandstone_top"],
    "smooth_basalt": ["smooth_basalt"],
    "oak_log": ["oak_log", "oak_log_top"],
    "spruce_log": ["spruce_log", "spruce_log_top"],
    "dark_oak_log": ["dark_oak_log", "dark_oak_log_top"],
    "birch_log": ["birch_log", "birch_log_top"],
    "chiseled_sandstone": ["chiseled_sandstone"],
    "cut_sandstone": ["cut_sandstone"],
}

# Suffixes to append after the bare block name when searching for a texture.
_SUFFIXES: tuple[str, ...] = ("", "_top", "_side", "_front", "_0", "_on")

_BLOCKID_RE = re.compile(r"^(?:minecraft:)?([a-z0-9_]+)(?:\[.*\])?$")


def _data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def _cache_path() -> Path:
    return _data_dir() / "block_colors.json"


_MEM_CACHE: dict[str, str] | None = None


def _load_cache() -> dict[str, str]:
    """Return the on-disk cache (mem-cached after first call)."""
    global _MEM_CACHE
    if _MEM_CACHE is not None:
        return _MEM_CACHE
    p = _cache_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    _MEM_CACHE = data if isinstance(data, dict) else {}
    return _MEM_CACHE


def _save_cache() -> None:
    if _MEM_CACHE is None:
        return
    try:
        _data_dir().mkdir(parents=True, exist_ok=True)
        _cache_path().write_text(
            json.dumps(_MEM_CACHE, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover - best effort
        pass


def _candidate_textures(block_id: str) -> list[str]:
    """Return an ordered, deduplicated list of texture stems to try."""
    candidates: list[str] = []
    if block_id in _SPECIAL:
        candidates.append(_SPECIAL[block_id])
    m = _BLOCKID_RE.match(block_id)
    if m:
        name = m.group(1)
        candidates.extend(_NAME_FALLBACKS.get(name, []))
        for suf in _SUFFIXES:
            candidates.append(name + suf)
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _fetch_png(stem: str, timeout: float = 5.0) -> bytes | None:
    url = _MCMETA_BASE + stem + ".png"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def _avg_color(png_bytes: bytes) -> str | None:
    """Return alpha-weighted ``#rrggbb`` mean, or None if undetermined."""
    if Image is None:
        return None
    try:
        im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:  # noqa: BLE001 - pillow raises many types
        return None

    # Animated block textures (sea_lantern, prismarine, ...) are tall vertical
    # strips of square frames. Use only the first frame.
    w, h = im.size
    if w and h > w and h % w == 0:
        im = im.crop((0, 0, w, w))

    pixels = im.get_flattened_data()
    r_sum = g_sum = b_sum = a_sum = 0
    for pr, pg, pb, pa in pixels:
        if pa == 0:
            continue
        r_sum += pr * pa
        g_sum += pg * pa
        b_sum += pb * pa
        a_sum += pa
    if a_sum == 0:
        return None
    return f"#{r_sum // a_sum:02x}{g_sum // a_sum:02x}{b_sum // a_sum:02x}"


def approximate_block_color(
    block_id: str, *, allow_network: bool = True
) -> str | None:
    """Return a ``"#rrggbb"`` color approximating ``block_id``.

    Results (including negatives) are cached on disk. Set ``allow_network=False``
    to prevent fetches; only cached entries will then resolve.
    """
    cache = _load_cache()
    if block_id in cache:
        hit = cache[block_id]
        return hit or None
    if not allow_network:
        return None
    for stem in _candidate_textures(block_id):
        data = _fetch_png(stem)
        if not data:
            continue
        col = _avg_color(data)
        if col:
            cache[block_id] = col
            _save_cache()
            return col
    # Negative-cache to avoid re-hitting the network for known-bad ids.
    cache[block_id] = ""
    _save_cache()
    return None


def _texture_dir() -> Path:
    return _data_dir() / "block_textures"


def _texture_stem_cache_path() -> Path:
    return _data_dir() / "block_texture_stems.json"


_STEM_MEM_CACHE: dict[str, str] | None = None


def _load_stem_cache() -> dict[str, str]:
    """Return the on-disk block_id -> stem map (cached in memory)."""
    global _STEM_MEM_CACHE
    if _STEM_MEM_CACHE is not None:
        return _STEM_MEM_CACHE
    p = _texture_stem_cache_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    _STEM_MEM_CACHE = data if isinstance(data, dict) else {}
    return _STEM_MEM_CACHE


def _save_stem_cache() -> None:
    if _STEM_MEM_CACHE is None:
        return
    try:
        _data_dir().mkdir(parents=True, exist_ok=True)
        _texture_stem_cache_path().write_text(
            json.dumps(_STEM_MEM_CACHE, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover - best effort
        pass


def _crop_first_frame(png_bytes: bytes) -> bytes:
    """Crop animated vertical-strip textures down to their first square frame.

    Returns the original bytes if Pillow isn't available or the texture is
    already square.
    """
    if Image is None:
        return png_bytes
    try:
        im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return png_bytes
    w, h = im.size
    if w and h > w and h % w == 0:
        im = im.crop((0, 0, w, w))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()
    return png_bytes


def block_texture_png(
    block_id: str, *, allow_network: bool = True
) -> bytes | None:
    """Return PNG bytes of a representative texture for ``block_id``.

    Resolution order:
      1. Disk cache at ``data/block_textures/<stem>.png`` (populated on first
         successful fetch and checked in via the repo).
      2. Upstream mcmeta mirror, tried against the same ordered candidate
         stems that :func:`approximate_block_color` uses.
      3. ``None`` if the block has no resolvable texture (also negative-cached
         so we don't hammer the network).

    Animated textures (tall vertical strips) are cropped to their first
    square frame so the icon renders without distortion.
    """
    stem_cache = _load_stem_cache()
    cached_stem = stem_cache.get(block_id)
    if cached_stem == "":
        return None
    if cached_stem:
        p = _texture_dir() / (cached_stem + ".png")
        if p.exists():
            try:
                return p.read_bytes()
            except OSError:
                pass

    if not allow_network:
        return None

    for stem in _candidate_textures(block_id):
        data = _fetch_png(stem)
        if not data:
            continue
        data = _crop_first_frame(data)
        try:
            _texture_dir().mkdir(parents=True, exist_ok=True)
            (_texture_dir() / (stem + ".png")).write_bytes(data)
        except OSError:  # pragma: no cover - best effort
            pass
        stem_cache[block_id] = stem
        _save_stem_cache()
        return data

    stem_cache[block_id] = ""
    _save_stem_cache()
    return None


def hex_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    """Convert ``"#rrggbb"`` to an RGBA tuple with full alpha."""
    s = hex_color.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Expected #rrggbb, got {hex_color!r}")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b, 1.0)


def _bare_block_name(block_id: str) -> str:
    """Return the lowercase bare block name (no namespace, no state spec).

    ``"minecraft:light_blue_stained_glass[waterlogged=true]"`` ->
    ``"light_blue_stained_glass"``. Unrecognized inputs are returned
    lowercased with whitespace stripped.
    """
    s = block_id.strip().lower()
    # Strip any ``[state=...]`` trailing state spec.
    i = s.find("[")
    if i != -1:
        s = s[:i]
    # Strip ``minecraft:`` (or any other namespace) prefix.
    j = s.rfind(":")
    if j != -1:
        s = s[j + 1 :]
    return s


def is_translucent(block_id: str) -> bool:
    """Return True if ``block_id`` renders with partial opacity in Minecraft.

    Matches common translucent blocks: glass (including stained glass and
    glass panes), ice variants, honey block, slime block. Matching is
    case-insensitive and ignores namespace prefixes and any ``[state]`` suffix.
    """
    name = _bare_block_name(block_id)
    if not name:
        return False
    if "glass" in name:
        return True
    # Ice family: ice, packed_ice, blue_ice, frosted_ice.
    if name == "ice" or name.endswith("_ice"):
        return True
    if name in ("honey_block", "slime_block"):
        return True
    return False


def block_alpha(block_id: str) -> float:
    """Return a suggested render alpha in ``(0, 1]`` for ``block_id``.

    Opaque blocks (the default) return ``1.0``. Translucent blocks return a
    value tuned to give a Minecraft-like glass/ice/slime look when composited
    with a standard over-operator. Honey and slime are only mildly
    translucent; stained glass is quite transparent; clear glass is the most
    see-through of the bunch.
    """
    if not is_translucent(block_id):
        return 1.0
    name = _bare_block_name(block_id)
    # Clear / tinted glass with no color qualifier: most see-through.
    if name in ("glass", "glass_pane", "tinted_glass"):
        return 0.35
    # Stained glass (and stained-glass panes): slightly less transparent so
    # the tint reads clearly.
    if "stained_glass" in name:
        return 0.4
    # Ice variants.
    if name == "ice" or name.endswith("_ice"):
        return 0.4
    # Honey and slime are thick and only lightly translucent.
    if name in ("honey_block", "slime_block"):
        return 0.75
    # Any other glass-containing id falls back to a mid value.
    return 0.4
