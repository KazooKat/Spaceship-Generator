"""Smoke tests for ``scripts/palette_diff.py``.

Mirrors the ``subprocess.run([sys.executable, ...])`` style of
``tests/test_palette_stats.py`` and ``tests/test_bench_smoke.py`` so we
exercise the real CLI entry point (argparse + ``sys.path`` insertion of
``src/`` and ``scripts/``) rather than importing the module directly.
We deliberately don't pin exact counts or the per-role ``yes/no`` mix —
the palette corpus evolves over time — so we assert the *shape* of the
output (header present, body non-empty, CSV parses cleanly, banner on
the correct stream).
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

from spaceship_generator.palette import palettes_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "palette_diff.py"
PALETTE_A = palettes_dir() / "desert_oasis.yaml"
PALETTE_B = palettes_dir() / "foggy_marsh.yaml"


def test_palette_diff_runs_text_mode() -> None:
    """Default invocation exits 0, stdout non-empty, contains a ``role`` header."""
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    assert PALETTE_A.is_file(), f"missing palette fixture: {PALETTE_A}"
    assert PALETTE_B.is_file(), f"missing palette fixture: {PALETTE_B}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(PALETTE_A), str(PALETTE_B)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_diff.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"palette_diff.py produced empty stdout:\n{out!r}"
    # ``role`` header column must appear in the table — guards against a
    # regression that silently drops the column header row.
    assert "role" in out, f"'role' header missing from stdout:\n{out}"
    # Both column-header siblings should also appear so the test catches
    # a regression that drops the A/B column labels.
    assert "A_block" in out, f"'A_block' header missing from stdout:\n{out}"
    assert "B_block" in out, f"'B_block' header missing from stdout:\n{out}"
    assert "same?" in out, f"'same?' header missing from stdout:\n{out}"


def test_palette_diff_csv_emits_csv() -> None:
    """``--csv`` flag produces a parseable CSV with the documented header.

    The banner must NOT pollute the CSV stream in ``--csv`` mode (it's
    routed to stderr instead) so the stdout is a clean parseable CSV
    document an operator can pipe straight into a spreadsheet / CI
    parser. We assert the header row matches the schema from the
    docstring and that at least one body row follows it (the union of
    two real palettes must surface at least one role).
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(PALETTE_A), str(PALETTE_B), "--csv"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_diff.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"palette_diff.py --csv produced empty stdout:\n{out!r}"

    # Stdout must parse with csv.reader without raising — guards against
    # a regression where a future block id containing a comma sneaks
    # through without the script using the stdlib csv writer's quoting.
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed, f"csv.reader returned no rows for stdout:\n{out!r}"
    assert parsed[0] == ["role", "a_block", "b_block", "same"], (
        f"first CSV row must be the documented header, got:\n{parsed[0]!r}"
    )
    body_rows = [row for row in parsed[1:] if row]
    assert len(body_rows) >= 1, (
        f"expected at least 1 body row beyond the header, got "
        f"{len(body_rows)}:\n{body_rows!r}"
    )
    # Every body row must have exactly 4 columns (role, a_block,
    # b_block, same) — catches a regression where a future role name
    # leaks an extra/missing column.
    assert all(len(row) == 4 for row in body_rows), (
        f"every CSV body row must have 4 columns; got:\n{body_rows!r}"
    )
    # The ``same`` column must be either ``yes`` or ``no`` for every
    # row — catches a regression where the boolean serialization drifts.
    assert all(row[3] in ("yes", "no") for row in body_rows), (
        f"'same' column must be yes/no in every row; got:\n{body_rows!r}"
    )

    # Banner must be on stderr, not stdout, in --csv mode so the stdout
    # stream stays a clean CSV document.
    assert "palette_diff.py" in result.stderr, (
        f"banner should be on stderr in --csv mode, got stderr:\n"
        f"{result.stderr!r}"
    )
    assert "palette_diff.py" not in out, (
        f"banner leaked onto stdout in --csv mode:\n{out!r}"
    )
