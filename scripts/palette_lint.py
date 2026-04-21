"""Palette linter for ``palettes/*.yaml``: duplicate roles, dark windows,
low HULL contrast, non-emissive ENGINE_GLOW. Exit 0 = clean (warns allowed
unless ``--strict``); exit 1 = errors (or warns under ``--strict``).

    .venv/Scripts/python scripts/palette_lint.py
    .venv/Scripts/python scripts/palette_lint.py --file palettes/foo.yaml
    .venv/Scripts/python scripts/palette_lint.py --strict --format json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spaceship_generator.palette import REQUIRED_ROLES  # noqa: E402

_BLOCKSTATE_RE = re.compile(
    r"^(?P<id>[a-z0-9_]+:[a-z0-9_]+)(?:\[(?P<props>[^\]]*)\])?$"
)

# Blocks that actually emit light (or read as emissive) at preview scale.
# Wildcards: ``*_lamp`` and ``*_candle_cake`` cover the suffix-matched families.
_KNOWN_EMISSIVE_EXACT: frozenset[str] = frozenset(
    {
        "minecraft:shroomlight",
        "minecraft:sea_lantern",
        "minecraft:redstone_lamp",
        "minecraft:jack_o_lantern",
        "minecraft:glowstone",
        "minecraft:ochre_froglight",
        "minecraft:verdant_froglight",
        "minecraft:pearlescent_froglight",
        "minecraft:soul_torch",
        "minecraft:soul_lantern",
        "minecraft:torch",
        "minecraft:lantern",
    }
)
_KNOWN_EMISSIVE_SUFFIX: tuple[str, ...] = ("_lamp", "_candle_cake")

WINDOW_MIN_LUMINANCE: float = 0.35
HULL_CONTRAST_MIN: float = 1.5


def _parse_hex(value: object) -> tuple[float, float, float] | None:
    """Return (r,g,b) in 0..1, or None if unparseable."""
    if not isinstance(value, str):
        return None
    s = value.strip().lstrip("#")
    if len(s) not in (6, 8):
        return None
    try:
        return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)
    except ValueError:
        return None


def _yiq_luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Cheap perceived-contrast ratio via YIQ Y: (Y_hi+0.05)/(Y_lo+0.05)."""
    ya, yb = _yiq_luminance(a), _yiq_luminance(b)
    lo, hi = sorted((ya, yb))
    return (hi + 0.05) / (lo + 0.05)


def _match_blockstate(spec: object) -> re.Match[str] | None:
    if not isinstance(spec, str):
        return None
    return _BLOCKSTATE_RE.match(spec.strip())


def _is_known_emissive(block_spec: str) -> bool:
    m = _match_blockstate(block_spec)
    bare = m.group("id") if m else block_spec.strip()
    if bare in _KNOWN_EMISSIVE_EXACT:
        return True
    return any(bare.endswith(suffix) for suffix in _KNOWN_EMISSIVE_SUFFIX)


@dataclass
class LintResult:
    name: str
    path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def lint_palette(path: Path) -> LintResult:
    result = LintResult(name=path.stem, path=str(path))

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        result.errors.append(f"cannot read/parse YAML: {exc}")
        return result

    if not isinstance(data, dict):
        result.errors.append("top-level YAML must be a mapping")
        return result

    result.name = str(data.get("name") or path.stem)
    blocks = data.get("blocks") or {}
    colors = data.get("preview_colors") or {}
    if not isinstance(blocks, dict):
        result.errors.append("'blocks' must be a mapping")
        blocks = {}
    if not isinstance(colors, dict):
        result.warnings.append("'preview_colors' must be a mapping")
        colors = {}

    # --- Hard errors: missing required role + invalid block id ---
    for role in REQUIRED_ROLES:
        if role not in blocks:
            result.errors.append(f"missing required role: {role}")
            continue
        if _match_blockstate(blocks[role]) is None:
            result.errors.append(
                f"invalid block id format for role {role!r}: {blocks[role]!r}"
            )

    # --- Warning: two distinct roles map to the same block ---
    seen: dict[str, str] = {}
    for role in REQUIRED_ROLES:
        spec = blocks.get(role)
        if not isinstance(spec, str):
            continue
        key = spec.strip()
        prev = seen.get(key)
        if prev is not None and prev != role:
            result.warnings.append(f"roles {prev!r} and {role!r} both map to {key!r}")
        else:
            seen[key] = role

    # --- Preview color checks ---
    parsed: dict[str, tuple[float, float, float]] = {}
    for role in REQUIRED_ROLES:
        if role not in colors:
            continue
        rgb = _parse_hex(colors[role])
        if rgb is None:
            result.warnings.append(
                f"preview color for role {role!r} is unparseable: {colors[role]!r}"
            )
        else:
            parsed[role] = rgb

    window_rgb = parsed.get("WINDOW")
    if window_rgb is not None:
        y = _yiq_luminance(window_rgb)
        if y < WINDOW_MIN_LUMINANCE:
            result.warnings.append(
                f"WINDOW preview color luminance {y:.3f} < {WINDOW_MIN_LUMINANCE:.2f} "
                f"(too dark - windows won't read)"
            )

    hull = parsed.get("HULL")
    hull_dark = parsed.get("HULL_DARK")
    if hull is not None and hull_dark is not None:
        ratio = _contrast_ratio(hull, hull_dark)
        if ratio < HULL_CONTRAST_MIN:
            result.warnings.append(
                f"HULL vs HULL_DARK contrast {ratio:.2f} < {HULL_CONTRAST_MIN:.2f} "
                f"(too similar)"
            )

    # --- ENGINE_GLOW emissive check ---
    engine_glow = blocks.get("ENGINE_GLOW")
    if isinstance(engine_glow, str) and _match_blockstate(engine_glow) is not None:
        if not _is_known_emissive(engine_glow):
            result.warnings.append(
                f"ENGINE_GLOW {engine_glow!r} is not in the known-emissive list"
            )

    return result


def _format_text(results: list[LintResult]) -> str:
    lines: list[str] = []
    for r in results:
        if not r.errors and not r.warnings:
            lines.append(f"{r.name}: OK")
            continue
        lines.append(f"{r.name}: {len(r.warnings)} warning(s), {len(r.errors)} error(s)")
        for e in r.errors:
            lines.append(f"  error: {e}")
        for w in r.warnings:
            lines.append(f"  warn: {w}")
    return "\n".join(lines)


def _format_json(results: list[LintResult]) -> str:
    payload = [
        {"name": r.name, "path": r.path, "errors": r.errors, "warnings": r.warnings}
        for r in results
    ]
    return json.dumps(payload, indent=2)


def _collect_targets(file_arg: str | None) -> list[Path]:
    if file_arg:
        return [Path(file_arg)]
    return sorted((REPO_ROOT / "palettes").glob("*.yaml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint spaceship-generator palette YAMLs.")
    parser.add_argument("--file", help="Lint a single palette file instead of palettes/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    targets = _collect_targets(args.file)
    if not targets:
        print("no palette files found", file=sys.stderr)
        return 1

    results = [lint_palette(p) for p in targets]
    print(_format_json(results) if args.format == "json" else _format_text(results))

    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)
    if total_errors:
        return 1
    if args.strict and total_warnings:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
