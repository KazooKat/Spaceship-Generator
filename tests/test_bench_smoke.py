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
MEM_SCRIPT = REPO_ROOT / "scripts" / "bench_mem.py"
PALETTE_SCRIPT = REPO_ROOT / "scripts" / "bench_palette.py"
FLEET_SCRIPT = REPO_ROOT / "scripts" / "bench_fleet.py"
SUMMARY_SCRIPT = REPO_ROOT / "scripts" / "bench_summary.py"

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


def test_bench_mem_runs_with_two_iterations() -> None:
    """Peak-memory bench exits 0 and prints the pipeline + TOTAL rows."""
    assert MEM_SCRIPT.is_file(), f"missing bench script: {MEM_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(MEM_SCRIPT),
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
        f"bench_mem.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_mem.py produced empty stdout:\n{out!r}"
    assert "pipeline" in out, f"'pipeline' row missing from stdout:\n{out}"
    assert "TOTAL" in out, f"TOTAL row missing from stdout:\n{out}"
    # Header columns we promised in the docstring + spec.
    assert "mean_mb" in out
    assert "p95_mb" in out
    assert "max_mb" in out


def test_bench_palette_runs_with_two_palettes_two_iterations() -> None:
    """Per-palette bench exits 0 and prints the column headers + TOTAL row."""
    assert PALETTE_SCRIPT.is_file(), f"missing bench script: {PALETTE_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(PALETTE_SCRIPT),
            "--limit",
            "2",
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
        f"bench_palette.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_palette.py produced empty stdout:\n{out!r}"
    # Header columns we promised in the docstring + spec.
    assert "palette" in out, f"'palette' header missing from stdout:\n{out}"
    assert "mean_ms" in out
    assert "p95_ms" in out
    assert "TOTAL" in out, f"TOTAL row missing from stdout:\n{out}"


def test_bench_fleet_runs_with_two_ships_two_iterations() -> None:
    """Fleet-build bench exits 0 and prints the column headers + TOTAL row."""
    assert FLEET_SCRIPT.is_file(), f"missing bench script: {FLEET_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(FLEET_SCRIPT),
            "--fleet-count",
            "2",
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
        f"bench_fleet.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_fleet.py produced empty stdout:\n{out!r}"
    # Header columns + per-ship/fleet rows + TOTAL we promised in the spec.
    assert "stage" in out, f"'stage' header missing from stdout:\n{out}"
    assert "mean_ms" in out
    assert "p95_ms" in out
    assert "per_ship" in out, f"'per_ship' row missing from stdout:\n{out}"
    assert "fleet" in out, f"'fleet' row missing from stdout:\n{out}"
    assert "TOTAL" in out, f"TOTAL row missing from stdout:\n{out}"


def test_bench_summary_runs_minimal() -> None:
    """Umbrella driver exits 0 and prints every child bench's name."""
    assert SUMMARY_SCRIPT.is_file(), f"missing bench script: {SUMMARY_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(SUMMARY_SCRIPT),
            "--iterations",
            "2",
            "--limit",
            "2",
            "--fleet-count",
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
        f"bench_summary.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_summary.py produced empty stdout:\n{out!r}"
    # Every child bench script's name must appear in the aggregate table
    # so this smoke test catches a regression where the umbrella silently
    # drops one of the rows (e.g. a typo in the BENCHES tuple).
    for name in (
        "bench_shape",
        "bench_full_pipeline",
        "bench_palette",
        "bench_mem",
        "bench_fleet",
    ):
        assert name in out, f"bench {name!r} missing from stdout:\n{out}"
