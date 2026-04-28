"""Smoke test for the bench scripts under ``scripts/``.

Runs each script via ``subprocess`` (so we exercise the real CLI entry
point, including ``argparse`` and the ``sys.path`` insertion of ``src/``)
with a very small iteration count. This catches:

* import errors / syntax errors,
* ``argparse`` regressions on the documented flags,
* and missing stage names in the printed summary table.

We deliberately do not assert exact timing values — this is a smoke test,
not a perf test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "bench_shape.py"
FULL_PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "bench_full_pipeline.py"

EXPECTED_STAGES = ("hull", "cockpit", "engines", "wings", "greebles", "assembly")


def test_bench_shape_runs_with_two_iterations() -> None:
    """Script exits 0 and prints every stage name + a TOTAL row."""
    assert SCRIPT.is_file(), f"missing bench script: {SCRIPT}"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--iterations", "2", "--seed", "1"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"bench_shape.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    for stage in EXPECTED_STAGES:
        assert stage in out, f"stage {stage!r} not in stdout:\n{out}"
    assert "TOTAL" in out, f"TOTAL row missing from stdout:\n{out}"
    # Header columns we promised in the docstring + spec.
    assert "mean_ms" in out
    assert "p95_ms" in out


def test_bench_full_pipeline_runs_with_two_iterations() -> None:
    """End-to-end bench exits 0 and prints the pipeline + TOTAL rows."""
    assert FULL_PIPELINE_SCRIPT.is_file(), (
        f"missing bench script: {FULL_PIPELINE_SCRIPT}"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(FULL_PIPELINE_SCRIPT),
            "--iterations",
            "2",
            "--seed",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"bench_full_pipeline.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_full_pipeline.py produced empty stdout:\n{out!r}"
    assert "pipeline" in out, f"'pipeline' row missing from stdout:\n{out}"
    assert "TOTAL" in out, f"TOTAL row missing from stdout:\n{out}"
    # Header columns we promised in the docstring + spec.
    assert "mean_ms" in out
    assert "p95_ms" in out
    assert "total_ms" in out
