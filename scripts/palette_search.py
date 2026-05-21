"""Search ``palettes/*.yaml`` for a given Minecraft block id.

Complements :mod:`scripts.palette_lint` (per-file validation),
:mod:`scripts.palette_stats` (cross-corpus stats), and
:mod:`scripts.palette_diff` (role-by-role diff) by walking every palette
under ``palettes/`` and printing one ``(palette, role)`` pair per
reference to a target Minecraft block id. Useful when authoring a new
palette and wondering "which palettes already use ``minecraft:stone``,
and in what role?", or when retiring a block and needing to find every
palette that has to be edited.

Default output is a fixed-width text table mirroring the style of the
``bench_*.py`` scripts and the sibling ``palette_*.py`` tools.
``--csv`` switches stdout to a parseable CSV with header
``palette,role``; banner / progress lines are routed to stderr in
``--csv`` mode so stdout stays a clean CSV stream.

Match semantics: the search compares the *bare* ``namespace:id`` of each
block spec (any ``[prop=val,...]`` blockstate properties are stripped)
so a query for ``minecraft:oak_log`` matches both
``minecraft:oak_log`` and ``minecraft:oak_log[axis=y]``. This mirrors
the histogram-aggregation rule in ``palette_stats.py`` so the two tools
agree on what "uses block X" means.

Exit codes:
    0  - at least one (palette, role) hit was found.
    1  - no hits (or the ``palettes/`` directory is missing).
    2  - bad CLI args (handled by argparse).

Usage:
    .venv/Scripts/python scripts/palette_search.py --block minecraft:stone
    .venv/Scripts/python scripts/palette_search.py --block minecraft:stone --csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Reuse the YAML loader / blockstate regex from ``palette_lint`` /
# ``palette_stats`` so we never roll a parallel reader — any future
# schema fix in the linter is automatically picked up here. Mirrors the
# ``sys.path`` insertion done by ``palette_stats.py`` so the script can
# be invoked directly without ``pip install -e .``.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402
from palette_lint import _match_blockstate  # noqa: E402

from spaceship_generator.palette import palettes_dir  # noqa: E402


def _load_palette(path: Path) -> dict:
    """Load a single palette YAML, returning ``{}`` on read/parse failure.

    Mirrors the tolerant style of ``palette_stats._load_palette`` /
    ``palette_lint.lint_palette``: a malformed file is skipped (with a
    warning to stderr) rather than aborting the cross-corpus search, so
    one broken YAML doesn't black-hole the rest of the catalog.
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

    Strips any ``[prop=val,...]`` blockstate properties so a search for
    ``minecraft:oak_log`` matches both ``minecraft:oak_log`` and
    ``minecraft:oak_log[axis=y]``. Mirrors ``palette_stats._bare_block_id``
    exactly so the two tools agree on what "this palette uses block X"
    means.
    """
    m = _match_blockstate(spec)
    if m is None:
        return None
    return m.group("id")


def search(pal_dir: Path, target: str) -> list[tuple[str, str]]:
    """Walk every ``*.yaml`` under ``pal_dir`` and collect hits.

    Returns a list of ``(palette_name, role)`` tuples sorted
    alphabetically by ``(palette_name, role)`` so output is deterministic
    across runs and platforms. ``palette_name`` is the YAML stem (no
    directory, no ``.yaml`` extension) to match the naming convention
    used by ``palette_diff.py`` / ``palette_stats.py``.
    """
    palette_paths = sorted(pal_dir.glob("*.yaml"))
    hits: list[tuple[str, str]] = []
    for path in palette_paths:
        data = _load_palette(path)
        blocks = data.get("blocks") or {}
        if not isinstance(blocks, dict):
            continue
        for role, spec in blocks.items():
            if not isinstance(role, str):
                continue
            bare = _bare_block_id(spec)
            if bare == target:
                hits.append((path.stem, role))
    hits.sort()
    return hits


def _print_table(
    target: str,
    hits: list[tuple[str, str]],
    palette_count: int,
    stream=sys.stdout,
) -> None:
    """Emit the human-readable fixed-width report to ``stream``."""
    print(
        f"palette_search.py — {target} "
        f"({len(hits)} hit(s) across {palette_count} palettes)",
        file=stream,
    )
    print(file=stream)

    palette_width = max(
        (len(name) for name, _r in hits), default=len("palette")
    )
    palette_width = max(palette_width, len("palette"))
    role_width = max(
        (len(role) for _n, role in hits), default=len("role")
    )
    role_width = max(role_width, len("role"))

    header = f"{'palette':<{palette_width}} {'role':<{role_width}}"
    sep = "-" * (palette_width + 1 + role_width)
    print(header, file=stream)
    print(sep, file=stream)
    for name, role in hits:
        print(f"{name:<{palette_width}} {role:<{role_width}}", file=stream)
    print(sep, file=stream)
    print(f"TOTAL {len(hits)}", file=stream)


def _print_csv(
    hits: list[tuple[str, str]], stream=sys.stdout
) -> None:
    """Emit the CSV (``palette,role``) to ``stream``."""
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["palette", "role"])
    for name, role in hits:
        writer.writerow([name, role])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Search palettes/*.yaml for a given Minecraft block id "
            "and print which palettes use it (per-role)."
        )
    )
    p.add_argument(
        "--block",
        required=True,
        help=(
            "Minecraft block id to search for, e.g. 'minecraft:stone'. "
            "Blockstate properties (any '[prop=val,...]' suffix) are "
            "stripped before comparison so the query matches palettes "
            "that reference the same block via different blockstates."
        ),
    )
    p.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help=(
            "Emit a CSV (palette,role) to stdout instead of the "
            "fixed-width text table; useful for CI / spreadsheet ingest. "
            "Banner is routed to stderr in this mode."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    pal_dir = palettes_dir()
    if not pal_dir.is_dir():
        print(f"no palettes directory at {pal_dir}", file=sys.stderr)
        return 1

    # Strip any blockstate suffix from the user's query too, so that
    # ``--block minecraft:oak_log[axis=y]`` is treated the same as
    # ``--block minecraft:oak_log`` — keeps the search semantics
    # symmetric between the query and the corpus.
    query = args.block.strip()
    bare_query = _bare_block_id(query) or query

    hits = search(pal_dir, bare_query)
    palette_count = len(sorted(pal_dir.glob("*.yaml")))

    # Banner / progress goes to stderr in CSV mode so stdout stays a
    # clean CSV stream an operator can pipe straight into a spreadsheet.
    # In text mode the banner is just the first line of the report.
    if args.csv:
        print(
            f"palette_search.py — {bare_query} "
            f"({len(hits)} hit(s) across {palette_count} palettes)",
            file=sys.stderr,
        )
        _print_csv(hits, sys.stdout)
    else:
        _print_table(bare_query, hits, palette_count, sys.stdout)

    return 0 if hits else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
