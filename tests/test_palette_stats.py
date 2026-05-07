"""Smoke tests for ``scripts/palette_stats.py``.

Mirrors the ``subprocess.run([sys.executable, ...])`` style of
``tests/test_bench_smoke.py`` so we exercise the real CLI entry point
(argparse + ``sys.path`` insertion of ``src/`` and ``scripts/``) rather
than importing the module directly. We deliberately don't pin exact
counts — the corpus grows over time as new biome palettes ship — so we
assert the *shape* of the output (banner string present, CSV header
present, body non-empty, CSV parses cleanly).
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "palette_stats.py"


def test_palette_stats_runs_without_args() -> None:
    """Default invocation exits 0, stdout non-empty, contains the banner."""
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_stats.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"palette_stats.py produced empty stdout:\n{out!r}"
    # Banner string from the spec — guards against a regression that
    # silently drops the header section of the report.
    assert "palettes scanned" in out, (
        f"'palettes scanned' banner missing from stdout:\n{out}"
    )
    # Each of the three logical sections should appear in the table
    # output — catches a regression where the role-coverage or top-N
    # block table is silently dropped.
    assert "Distinct MC blocks used" in out, (
        f"'Distinct MC blocks used' line missing from stdout:\n{out}"
    )
    assert "Role coverage" in out, (
        f"'Role coverage' section header missing from stdout:\n{out}"
    )


def test_palette_stats_csv_emits_csv() -> None:
    """``--csv`` flag produces a parseable long-format CSV with body rows.

    The banner must NOT pollute the CSV stream in ``--csv`` mode (it's
    routed to stderr instead) so the stdout is a clean parseable CSV
    document an operator can pipe straight into a spreadsheet / CI
    parser. We assert the header row matches the schema from the
    docstring and that at least 2 body rows follow it (the two
    ``summary`` rows are the minimum guaranteed by the contract; over
    the real 60+ palette corpus the body will be much larger).
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--csv"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_stats.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"palette_stats.py --csv produced empty stdout:\n{out!r}"

    # Stdout must parse with csv.reader without raising — guards against
    # a regression where a future block id containing a comma sneaks
    # through without the script using the stdlib csv writer's quoting.
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed, f"csv.reader returned no rows for stdout:\n{out!r}"
    assert parsed[0] == ["section", "key", "value"], (
        f"first CSV row must be the long-format header, got:\n{parsed[0]!r}"
    )
    body_rows = [row for row in parsed[1:] if row]
    assert len(body_rows) >= 2, (
        f"expected at least 2 body rows beyond the header, got "
        f"{len(body_rows)}:\n{body_rows!r}"
    )

    # Banner must be on stderr, not stdout, in --csv mode so the stdout
    # stream stays a clean CSV document.
    assert "palettes scanned" in result.stderr, (
        f"banner should be on stderr in --csv mode, got stderr:\n"
        f"{result.stderr!r}"
    )
    assert "palettes scanned" not in out, (
        f"banner leaked onto stdout in --csv mode:\n{out!r}"
    )
