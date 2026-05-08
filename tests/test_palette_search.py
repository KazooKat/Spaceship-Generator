"""Smoke tests for ``scripts/palette_search.py``.

Mirrors the ``subprocess.run([sys.executable, ...])`` style of
``tests/test_palette_diff.py`` and ``tests/test_palette_stats.py`` so we
exercise the real CLI entry point (argparse + ``sys.path`` insertion of
``src/`` and ``scripts/``) rather than importing the module directly.
We deliberately don't pin exact hit counts — the palette corpus evolves
over time as new biome packs ship — so we assert the *shape* of the
output: a block known to be present in the corpus exits 0 with
non-empty stdout, and an absurd block name exits 1 with clean empty
output (no body rows beyond the header in CSV mode).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "palette_search.py"


def test_palette_search_finds_present_block() -> None:
    """A block known to be present in many palettes exits 0 with body rows."""
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--block",
            "minecraft:iron_block",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_search.py exited {result.returncode} for a present "
        f"block — expected 0\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), (
        f"palette_search.py produced empty stdout for a present block:\n"
        f"{out!r}"
    )
    # Header row must appear in the table — guards against a regression
    # that silently drops the column header.
    assert "palette" in out, f"'palette' header missing from stdout:\n{out}"
    assert "role" in out, f"'role' header missing from stdout:\n{out}"


def test_palette_search_no_hits_exits_1() -> None:
    """An absurd block id exits 1 and produces no body rows.

    Exit code 1 is the documented "no hits" signal — useful for shell
    pipelines that need to gate further work on whether a block is in
    use anywhere in the corpus. The header may still print, but the CSV
    output must be empty beyond the header line so downstream consumers
    don't accidentally treat phantom rows as hits.
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--block",
            "minecraft:no_such_block_xyz",
            "--csv",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 1, (
        f"palette_search.py should exit 1 when no hits, got "
        f"{result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    # CSV stdout must be exactly the header line + trailing newline (no
    # body rows) — guards against a regression where phantom rows leak
    # through for an absurd block.
    assert result.stdout == "palette,role\n", (
        f"expected only the CSV header for a no-hit search, got:\n"
        f"{result.stdout!r}"
    )
