"""Merge two ``palettes/*.yaml`` files into a single palette.

Complements :mod:`scripts.palette_lint` (per-file validation),
:mod:`scripts.palette_stats` (cross-corpus stats), and
:mod:`scripts.palette_diff` (role-by-role diff) by combining the
``blocks:`` and ``preview_colors:`` mappings of two palettes into a new,
well-formed palette YAML using a configurable conflict-resolution
strategy.

Strategies:
    prefer-a         For every role, use A's block if A defines it,
                     else B's. Same rule applies to preview_colors.
    prefer-b         For every role, use B's block if B defines it,
                     else A's. Same rule applies to preview_colors.
    prefer-defined   For every role, use whichever side has a defined
                     (non-None / non-``<missing>``) block; if both
                     define it, prefer A; if only one defines it, use
                     the defined side.

Without ``--out`` the merged YAML is written to stdout and the banner
goes to stderr (so stdout stays a clean YAML stream pipe-able into
``palette_lint.py``). With ``--out PATH`` the YAML is written to that
file and progress / banner go to stderr.

Exit codes:
    0  - both palettes loaded cleanly and the merged palette was
         emitted successfully.
    1  - either input palette failed to load (with a diagnostic on
         stderr).

Usage:
    .venv/Scripts/python scripts/palette_merge.py \\
        palettes/desert_oasis.yaml palettes/foggy_marsh.yaml
    .venv/Scripts/python scripts/palette_merge.py \\
        palettes/desert_oasis.yaml palettes/foggy_marsh.yaml \\
        --strategy prefer-defined --out palettes/merged.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reuse the YAML loader semantics from ``palette_diff`` / ``palette_lint``
# rather than rolling a parallel reader so any future schema fix to the
# loader is automatically picked up here.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402

from spaceship_generator.palette import REQUIRED_ROLES  # noqa: E402

MISSING_MARKER = "<missing>"
STRATEGIES: tuple[str, ...] = ("prefer-a", "prefer-b", "prefer-defined")


def _load_palette(path: Path) -> dict:
    """Load a palette YAML, raising ``ValueError`` with a human diagnostic.

    Mirrors the strict variant of the loader used in ``palette_diff``:
    any read / parse / shape failure raises ``ValueError`` so the caller
    can translate the message into an exit-1 stderr line. Unlike
    ``palette_stats._load_palette`` we want a hard failure here — the
    merge tool must not silently emit a half-merged palette if either
    side is broken.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read/parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"top-level YAML must be a mapping in {path}")
    blocks = data.get("blocks") or {}
    if not isinstance(blocks, dict):
        raise ValueError(f"'blocks' must be a mapping in {path}")
    colors = data.get("preview_colors") or {}
    if not isinstance(colors, dict):
        raise ValueError(f"'preview_colors' must be a mapping in {path}")
    return data


def _is_defined(value: object) -> bool:
    """Return True if ``value`` is a real defined entry (not None / missing)."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() in ("", MISSING_MARKER):
        return False
    return True


def _pick(a: object, b: object, strategy: str) -> object | None:
    """Pick a value for a role/color key per the merge strategy.

    Returns ``None`` if neither side defines the value, in which case
    the caller should omit the key entirely from the merged palette.
    """
    a_def = _is_defined(a)
    b_def = _is_defined(b)
    if strategy == "prefer-a":
        if a_def:
            return a
        if b_def:
            return b
        return None
    if strategy == "prefer-b":
        if b_def:
            return b
        if a_def:
            return a
        return None
    # prefer-defined: prefer A when both define, else whichever is defined.
    if a_def and b_def:
        return a
    if a_def:
        return a
    if b_def:
        return b
    return None


def merge_palettes(
    palette_a: dict,
    palette_b: dict,
    strategy: str,
    name_a: str,
    name_b: str,
) -> dict:
    """Merge two parsed palette dicts into a new well-formed palette dict.

    The output preserves the existing palette schema (``name``,
    ``description``, ``blocks``, ``preview_colors``) and uses the
    REQUIRED_ROLES order for both ``blocks`` and ``preview_colors`` so
    the result lints cleanly under ``palette_lint.py --strict``.
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"unknown strategy {strategy!r}; expected one of {STRATEGIES}"
        )

    blocks_a = palette_a.get("blocks") or {}
    blocks_b = palette_b.get("blocks") or {}
    colors_a = palette_a.get("preview_colors") or {}
    colors_b = palette_b.get("preview_colors") or {}

    merged_blocks: dict[str, str] = {}
    merged_colors: dict[str, str] = {}

    # Walk REQUIRED_ROLES first so the canonical role order is preserved
    # in the output (palette_lint cares about presence, not order, but
    # downstream tooling and humans both prefer the conventional order).
    for role in REQUIRED_ROLES:
        block = _pick(blocks_a.get(role), blocks_b.get(role), strategy)
        if block is not None:
            merged_blocks[role] = str(block)
        color = _pick(colors_a.get(role), colors_b.get(role), strategy)
        if color is not None:
            merged_colors[role] = str(color)

    # Surface any extra roles defined in either input that are NOT in
    # REQUIRED_ROLES (schema drift) — preserving them keeps the merge
    # round-trippable. Sort for determinism.
    extra_roles = sorted(
        (set(blocks_a) | set(blocks_b) | set(colors_a) | set(colors_b))
        - set(REQUIRED_ROLES)
    )
    for role in extra_roles:
        if not isinstance(role, str):
            continue
        block = _pick(blocks_a.get(role), blocks_b.get(role), strategy)
        if block is not None:
            merged_blocks[role] = str(block)
        color = _pick(colors_a.get(role), colors_b.get(role), strategy)
        if color is not None:
            merged_colors[role] = str(color)

    name_a_str = str(palette_a.get("name") or name_a)
    name_b_str = str(palette_b.get("name") or name_b)
    merged_name = f"{name_a_str}__{name_b_str}__{strategy}"
    merged_description = (
        f"Merged palette: {name_a_str} + {name_b_str} "
        f"(strategy={strategy})."
    )

    # Preserve the canonical key order seen in real palettes
    # (name -> description -> blocks -> preview_colors).
    return {
        "name": merged_name,
        "description": merged_description,
        "blocks": merged_blocks,
        "preview_colors": merged_colors,
    }


def _dump_yaml(merged: dict) -> str:
    """Serialize the merged palette dict to a YAML string.

    ``sort_keys=False`` preserves the insertion order from
    :func:`merge_palettes` (name -> description -> blocks ->
    preview_colors with REQUIRED_ROLES first inside each mapping) so
    the output mirrors the shape of hand-authored palettes.
    """
    return yaml.safe_dump(
        merged,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Merge two palettes/*.yaml files into a single palette using a "
            "configurable conflict-resolution strategy."
        )
    )
    p.add_argument("palette_a", help="path to first palette YAML")
    p.add_argument("palette_b", help="path to second palette YAML")
    p.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="prefer-a",
        help=(
            "Conflict-resolution strategy when both palettes define a role. "
            "prefer-a (default): use A when defined, else B. "
            "prefer-b: use B when defined, else A. "
            "prefer-defined: use whichever side has a defined value; "
            "ties go to A."
        ),
    )
    p.add_argument(
        "--out",
        default=None,
        help=(
            "Optional output path for the merged YAML. Without --out, "
            "the merged YAML is written to stdout (banner to stderr)."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path_a = Path(args.palette_a)
    path_b = Path(args.palette_b)

    try:
        palette_a = _load_palette(path_a)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        palette_b = _load_palette(path_b)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    merged = merge_palettes(
        palette_a, palette_b, args.strategy, path_a.stem, path_b.stem
    )
    yaml_text = _dump_yaml(merged)

    name_a = path_a.stem
    name_b = path_b.stem
    banner = (
        f"palette_merge.py — {name_a} + {name_b} "
        f"(strategy={args.strategy})"
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_text, encoding="utf-8")
        print(banner, file=sys.stderr)
        print(f"wrote {out_path}", file=sys.stderr)
    else:
        # Banner goes to stderr in stdout mode so the stdout stream
        # stays a clean YAML document an operator can pipe straight
        # into palette_lint.py.
        print(banner, file=sys.stderr)
        sys.stdout.write(yaml_text)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
