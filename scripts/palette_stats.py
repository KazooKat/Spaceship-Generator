"""Cross-corpus stats for ``palettes/*.yaml``.

Complements :mod:`scripts.palette_lint` (per-file validation) by walking
*every* palette under ``palettes/`` and aggregating global statistics
across the whole corpus — useful for spotting which Minecraft blocks the
catalog leans on, and for confirming uniform role coverage.

Default output is a fixed-width text table mirroring the style of the
``bench_*.py`` scripts. ``--csv`` switches stdout to a single
**long-format CSV** with a leading ``section`` column so all three
logical sections (summary / top blocks / role coverage) live in one
parseable document. Banner / progress lines are routed to stderr in
``--csv`` mode so stdout stays a clean CSV stream.

CSV schema (long-format, one row per fact):

    section,key,value
    summary,palettes_scanned,69
    summary,distinct_blocks,123
    top_block,minecraft:smooth_basalt,7
    role_coverage,HULL,69/69
    ...

Usage:
    .venv/Scripts/python scripts/palette_stats.py
    .venv/Scripts/python scripts/palette_stats.py --top 20
    .venv/Scripts/python scripts/palette_stats.py --csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

# Reuse the YAML loader / blockstate regex from ``palette_lint`` so we
# never roll a parallel reader — any future schema fix in the linter is
# automatically picked up here.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402
from palette_lint import _match_blockstate  # noqa: E402

from spaceship_generator.palette import REQUIRED_ROLES, palettes_dir  # noqa: E402


def _load_palette(path: Path) -> dict:
    """Load a single palette YAML, returning ``{}`` on read/parse failure.

    Mirrors the tolerant style of ``palette_lint.lint_palette``: a
    malformed file is skipped (with a warning to stderr) rather than
    aborting the cross-corpus scan, so one broken YAML doesn't
    black-hole the rest of the catalog.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        print(f"warn: cannot read/parse {path.name}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _bare_block_id(spec: object) -> str | None:
    """Return ``namespace:id`` for a blockstate spec, or ``None`` if invalid.

    Strips any ``[prop=val,...]`` blockstate properties so two palettes
    that reference the same underlying block via different blockstates
    aggregate together in the histogram (e.g. ``minecraft:oak_log`` and
    ``minecraft:oak_log[axis=y]`` count once toward the same block).
    """
    m = _match_blockstate(spec)
    if m is None:
        return None
    return m.group("id")


def aggregate(pal_dir: Path) -> tuple[int, Counter[str], Counter[str]]:
    """Walk every ``*.yaml`` under ``pal_dir`` and aggregate stats.

    Returns ``(palette_count, block_counter, role_counter)`` where:

    * ``palette_count`` is the number of YAML files actually scanned
      (matches the count we banner-print so the two can never drift).
    * ``block_counter`` maps a bare ``namespace:id`` block spec to the
      number of (palette, role) references to that block across the
      whole corpus.
    * ``role_counter`` maps a role name to the number of palettes that
      define it. Computed across the union of every role we observed
      (so a palette that defines an unknown extra role still surfaces
      in the table — handy for catching schema drift).
    """
    palette_paths = sorted(pal_dir.glob("*.yaml"))
    block_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()

    for path in palette_paths:
        data = _load_palette(path)
        blocks = data.get("blocks") or {}
        if not isinstance(blocks, dict):
            continue
        for role, spec in blocks.items():
            if not isinstance(role, str):
                continue
            role_counter[role] += 1
            bare = _bare_block_id(spec)
            if bare is not None:
                block_counter[bare] += 1

    # Make sure every REQUIRED_ROLE appears in the role counter even if
    # zero palettes defined it — the role-coverage table should always
    # show 0/N for a missing required role rather than silently omitting
    # the row.
    for role in REQUIRED_ROLES:
        role_counter.setdefault(role, 0)

    return len(palette_paths), block_counter, role_counter


def _top_blocks(
    block_counter: Counter[str], top_n: int
) -> list[tuple[str, int]]:
    """Return the ``top_n`` most-referenced blocks (ties broken alphabetically).

    ``Counter.most_common`` is stable on insertion order which is *not*
    what we want — operators expect deterministic output across runs and
    across platforms, so we explicitly sort ``(-count, name)`` to break
    ties alphabetically by block id.
    """
    items = sorted(block_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return items[:top_n]


def _print_table(
    palette_count: int,
    block_counter: Counter[str],
    role_counter: Counter[str],
    top_n: int,
    stream=sys.stdout,
) -> None:
    """Emit the human-readable fixed-width report to ``stream``."""
    print(f"palette_stats.py — {palette_count} palettes scanned", file=stream)
    print(f"Distinct MC blocks used: {len(block_counter)}", file=stream)
    print(file=stream)

    # --- Section 2: top-N most-frequently referenced blocks ---
    top = _top_blocks(block_counter, top_n)
    print(f"Top {len(top)} most-referenced blocks:", file=stream)
    if top:
        block_width = max((len(name) for name, _c in top), default=8)
        block_width = max(block_width, len("block"))
        print(f"{'block':<{block_width}} {'count':>8}", file=stream)
        print("-" * (block_width + 1 + 8), file=stream)
        for name, count in top:
            print(f"{name:<{block_width}} {count:>8}", file=stream)
        print("-" * (block_width + 1 + 8), file=stream)
    else:
        print("(no blocks observed)", file=stream)
    print(file=stream)

    # --- Section 3: role coverage histogram ---
    print("Role coverage:", file=stream)
    role_names = sorted(role_counter.keys())
    if role_names:
        role_width = max(len(name) for name in role_names)
        role_width = max(role_width, len("role"))
        cov_header = f"defined_in / {palette_count}"
        print(f"{'role':<{role_width}} {cov_header:>20}", file=stream)
        print("-" * (role_width + 1 + 20), file=stream)
        for role in role_names:
            cov = f"{role_counter[role]} / {palette_count}"
            print(f"{role:<{role_width}} {cov:>20}", file=stream)
        print("-" * (role_width + 1 + 20), file=stream)
    else:
        print("(no roles observed)", file=stream)


def _print_csv(
    palette_count: int,
    block_counter: Counter[str],
    role_counter: Counter[str],
    top_n: int,
    stream=sys.stdout,
) -> None:
    """Emit the long-format CSV (``section,key,value``) to ``stream``.

    A single long-format document is easier to ingest than three
    side-by-side CSV blocks: spreadsheets / pandas can pivot on the
    ``section`` column, and adding a future fourth section never
    invalidates an existing parser.
    """
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["section", "key", "value"])
    writer.writerow(["summary", "palettes_scanned", palette_count])
    writer.writerow(["summary", "distinct_blocks", len(block_counter)])
    for name, count in _top_blocks(block_counter, top_n):
        writer.writerow(["top_block", name, count])
    for role in sorted(role_counter.keys()):
        writer.writerow(
            ["role_coverage", role, f"{role_counter[role]}/{palette_count}"]
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cross-corpus stats for palettes/*.yaml."
    )
    p.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help=(
            "Emit a single long-format CSV (section,key,value) to stdout "
            "instead of the fixed-width text report; useful for CI / "
            "spreadsheet ingest. Banner is routed to stderr in this mode."
        ),
    )
    p.add_argument(
        "--top",
        type=int,
        default=10,
        help=(
            "cap for the most-referenced-blocks histogram (default: 10). "
            "Ties broken alphabetically by block id so output is stable."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.top < 0:
        print("--top must be >= 0", file=sys.stderr)
        return 2

    pal_dir = palettes_dir()
    if not pal_dir.is_dir():
        print(f"no palettes directory at {pal_dir}", file=sys.stderr)
        return 1

    palette_count, block_counter, role_counter = aggregate(pal_dir)

    # Banner / progress goes to stderr in CSV mode so stdout stays a
    # clean CSV stream an operator can pipe straight into a spreadsheet.
    # In text mode the banner is just the first line of the report.
    if args.csv:
        print(
            f"palette_stats.py — {palette_count} palettes scanned",
            file=sys.stderr,
        )
        _print_csv(
            palette_count, block_counter, role_counter, args.top, sys.stdout
        )
    else:
        _print_table(
            palette_count, block_counter, role_counter, args.top, sys.stdout
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
