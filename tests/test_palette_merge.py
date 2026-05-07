"""Smoke tests for ``scripts/palette_merge.py``.

Mirrors the ``subprocess.run([sys.executable, ...])`` style of
``tests/test_palette_diff.py`` and ``tests/test_palette_stats.py`` so we
exercise the real CLI entry point (argparse + ``sys.path`` insertion of
``src/`` and ``scripts/``) rather than importing the module directly.
We deliberately don't pin exact merged-block contents — the input
palettes evolve over time — so we assert the *shape* of the output
(file exists, exit 0, lints clean under ``palette_lint.py --strict``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "palette_merge.py"
LINT_SCRIPT = REPO_ROOT / "scripts" / "palette_lint.py"
PALETTE_A = REPO_ROOT / "palettes" / "desert_oasis.yaml"
PALETTE_B = REPO_ROOT / "palettes" / "foggy_marsh.yaml"


def test_palette_merge_writes_strict_lint_clean_file(tmp_path: Path) -> None:
    """``--out PATH --strategy prefer-a`` writes a strict-lint-clean YAML.

    The merged file must (a) exist on disk after the script returns,
    (b) be non-empty, and (c) pass ``palette_lint.py --strict --file
    PATH`` with exit 0 and ``OK`` in stdout — guards against a
    regression where the merge tool emits a syntactically valid YAML
    that nonetheless fails the project's role / contrast lints.
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    assert LINT_SCRIPT.is_file(), f"missing lint script: {LINT_SCRIPT}"
    assert PALETTE_A.is_file(), f"missing palette fixture: {PALETTE_A}"
    assert PALETTE_B.is_file(), f"missing palette fixture: {PALETTE_B}"

    merged_path = tmp_path / "merged.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(PALETTE_A),
            str(PALETTE_B),
            "--out",
            str(merged_path),
            "--strategy",
            "prefer-a",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_merge.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert merged_path.is_file(), (
        f"palette_merge.py did not create the --out file: {merged_path}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert merged_path.stat().st_size > 0, (
        f"palette_merge.py produced empty file at {merged_path}"
    )

    lint_result = subprocess.run(
        [
            sys.executable,
            str(LINT_SCRIPT),
            "--file",
            str(merged_path),
            "--strict",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert lint_result.returncode == 0, (
        f"palette_lint.py --strict exited {lint_result.returncode} on the "
        f"merged palette\nstdout:\n{lint_result.stdout}\n"
        f"stderr:\n{lint_result.stderr}"
    )
    assert "OK" in lint_result.stdout, (
        f"'OK' missing from palette_lint.py --strict stdout for the "
        f"merged palette:\n{lint_result.stdout}"
    )
