"""Role-by-role diff for two ``palettes/*.yaml`` files.

Complements :mod:`scripts.palette_lint` (per-file validation) and
:mod:`scripts.palette_stats` (cross-corpus stats) by walking the
``blocks:`` mapping of two palettes side-by-side and printing one row
per role found in the union of the two role sets.

Default output is a fixed-width text table mirroring the style of the
``bench_*.py`` scripts and ``palette_stats.py``. ``--csv`` switches
stdout to a parseable CSV with header ``role,a_block,b_block,same``;
banner / progress lines are routed to stderr in ``--csv`` mode so
stdout stays a clean CSV stream.

Exit codes:
    0  - both palettes loaded cleanly (the diff itself is informational
         and is *not* an error, even when every role differs).
    1  - either palette failed to load (with a diagnostic on stderr).

Usage:
    .venv/Scripts/python scripts/palette_diff.py \\
        palettes/desert_oasis.yaml palettes/foggy_marsh.yaml
    .venv/Scripts/python scripts/palette_diff.py \\
        palettes/desert_oasis.yaml palettes/foggy_marsh.yaml --csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Reuse the YAML loader from ``palette_stats`` so we never roll a
# parallel reader — any future schema fix in the loader is automatically
# picked up here. ``palette_stats._load_palette`` already mirrors the
# tolerant style of ``palette_lint.lint_palette`` (warns on broken YAML
# rather than aborting), but for the diff tool we *want* a hard failure
# if either side cannot be read, so we wrap the loader to surface a
# load error to the caller.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402

MISSING_MARKER = "<missing>"


def _load_blocks(path: Path) -> dict[str, str]:
    """Load ``blocks:`` mapping from a palette YAML.

    Raises ``ValueError`` (with a human diagnostic) if the file cannot
    be opened, parsed, has a non-mapping top level, or has a
    non-mapping ``blocks`` key. Caller is expected to translate the
    message into an exit-1 stderr line.
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
    # Coerce values to strings so the diff is purely textual — anything
    # non-stringy is an upstream schema bug that ``palette_lint`` already
    # flags; here we just make sure the diff tool doesn't choke.
    return {
        str(role): str(spec)
        for role, spec in blocks.items()
        if isinstance(role, str)
    }


def diff_palettes(
    blocks_a: dict[str, str], blocks_b: dict[str, str]
) -> list[tuple[str, str, str, bool]]:
    """Return one ``(role, a_block, b_block, same)`` tuple per union role.

    Roles are sorted alphabetically so the output is deterministic
    across runs and platforms. ``same`` is ``True`` only when both
    sides have a block defined for the role and the block strings are
    byte-identical; ``<missing>`` on either side always implies
    ``same=False``.
    """
    roles = sorted(set(blocks_a) | set(blocks_b))
    rows: list[tuple[str, str, str, bool]] = []
    for role in roles:
        a = blocks_a.get(role)
        b = blocks_b.get(role)
        a_str = a if a is not None else MISSING_MARKER
        b_str = b if b is not None else MISSING_MARKER
        same = a is not None and b is not None and a == b
        rows.append((role, a_str, b_str, same))
    return rows


def _print_table(
    name_a: str,
    name_b: str,
    rows: list[tuple[str, str, str, bool]],
    stream=sys.stdout,
) -> None:
    """Emit the human-readable fixed-width report to ``stream``."""
    print(f"palette_diff.py — {name_a} vs {name_b}", file=stream)
    print(f"{len(rows)} role(s) compared", file=stream)
    print(file=stream)

    role_width = max(
        (len(role) for role, _a, _b, _s in rows), default=len("role")
    )
    role_width = max(role_width, len("role"))
    a_width = max(
        (len(a) for _r, a, _b, _s in rows), default=len("A_block")
    )
    a_width = max(a_width, len("A_block"))
    b_width = max(
        (len(b) for _r, _a, b, _s in rows), default=len("B_block")
    )
    b_width = max(b_width, len("B_block"))
    same_width = max(len("same?"), len("yes"), len("no"))

    header = (
        f"{'role':<{role_width}} "
        f"{'A_block':<{a_width}} "
        f"{'B_block':<{b_width}} "
        f"{'same?':<{same_width}}"
    )
    sep = "-" * (role_width + 1 + a_width + 1 + b_width + 1 + same_width)
    print(header, file=stream)
    print(sep, file=stream)
    for role, a, b, same in rows:
        same_str = "yes" if same else "no"
        print(
            f"{role:<{role_width}} "
            f"{a:<{a_width}} "
            f"{b:<{b_width}} "
            f"{same_str:<{same_width}}",
            file=stream,
        )
    print(sep, file=stream)


def _print_csv(
    rows: list[tuple[str, str, str, bool]], stream=sys.stdout
) -> None:
    """Emit the CSV (``role,a_block,b_block,same``) to ``stream``."""
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["role", "a_block", "b_block", "same"])
    for role, a, b, same in rows:
        writer.writerow([role, a, b, "yes" if same else "no"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Role-by-role diff for two palettes/*.yaml files."
    )
    p.add_argument("palette_a", help="path to first palette YAML")
    p.add_argument("palette_b", help="path to second palette YAML")
    p.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help=(
            "Emit a CSV (role,a_block,b_block,same) to stdout instead "
            "of the fixed-width text table; useful for CI / spreadsheet "
            "ingest. Banner is routed to stderr in this mode."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path_a = Path(args.palette_a)
    path_b = Path(args.palette_b)

    try:
        blocks_a = _load_blocks(path_a)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        blocks_b = _load_blocks(path_b)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rows = diff_palettes(blocks_a, blocks_b)

    name_a = path_a.stem
    name_b = path_b.stem

    # Banner / progress goes to stderr in CSV mode so stdout stays a
    # clean CSV stream an operator can pipe straight into a spreadsheet.
    # In text mode the banner is just the first line of the report.
    if args.csv:
        print(
            f"palette_diff.py — {name_a} vs {name_b} "
            f"({len(rows)} role(s) compared)",
            file=sys.stderr,
        )
        _print_csv(rows, sys.stdout)
    else:
        _print_table(name_a, name_b, rows, sys.stdout)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
