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

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "bench_shape.py"
FULL_PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "bench_full_pipeline.py"
MEM_SCRIPT = REPO_ROOT / "scripts" / "bench_mem.py"
PALETTE_SCRIPT = REPO_ROOT / "scripts" / "bench_palette.py"
GREEBLE_DENSITY_SCRIPT = REPO_ROOT / "scripts" / "bench_greeble_density.py"
FLEET_SCRIPT = REPO_ROOT / "scripts" / "bench_fleet.py"
SUMMARY_SCRIPT = REPO_ROOT / "scripts" / "bench_summary.py"
COMPARE_SCRIPT = REPO_ROOT / "scripts" / "bench_compare.py"
GENERATOR_SCRIPT = REPO_ROOT / "scripts" / "bench_generator.py"

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


def test_bench_shape_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + per-stage rows + TOTAL row.

    The run-banner must NOT pollute the CSV stream in `--csv` mode (it's
    routed to stderr instead) so the stdout is a clean parseable CSV
    document an operator can pipe straight into a spreadsheet / CI parser.
    """
    assert SCRIPT.is_file(), f"missing bench script: {SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--csv",
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
        f"bench_shape.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_shape.py --csv produced empty stdout:\n{out!r}"
    lines = out.splitlines()
    assert lines[0] == "stage,mean_ms,p95_ms,total_ms", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # Subsequent rows must include at least one per-stage data row and a
    # TOTAL row — catches a regression where the header emits but the body
    # / TOTAL summary row is dropped.
    body_rows = lines[1:]
    assert any(
        row and not row.startswith("TOTAL,") and not row.startswith("stage,")
        for row in body_rows
    ), f"no per-stage row in CSV body:\n{body_rows}"
    assert any(
        row.startswith("TOTAL,") for row in body_rows
    ), f"TOTAL row missing from CSV body:\n{body_rows}"


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


def test_bench_full_pipeline_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + per-stage rows + TOTAL row.

    The run-banner must NOT pollute the CSV stream in `--csv` mode (it's
    routed to stderr instead) so the stdout is a clean parseable CSV
    document an operator can pipe straight into a spreadsheet / CI parser.
    """
    assert FULL_PIPELINE_SCRIPT.is_file(), (
        f"missing bench script: {FULL_PIPELINE_SCRIPT}"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(FULL_PIPELINE_SCRIPT),
            "--csv",
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
        f"bench_full_pipeline.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), (
        f"bench_full_pipeline.py --csv produced empty stdout:\n{out!r}"
    )
    lines = out.splitlines()
    assert lines[0] == "stage,mean_ms,p95_ms,total_ms", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # Subsequent rows must include at least one per-stage data row and a
    # TOTAL row — catches a regression where the header emits but the body
    # / TOTAL summary row is dropped.
    body_rows = lines[1:]
    assert any(
        row and not row.startswith("TOTAL,") and not row.startswith("stage,")
        for row in body_rows
    ), f"no per-stage row in CSV body:\n{body_rows}"
    assert any(
        row.startswith("TOTAL,") for row in body_rows
    ), f"TOTAL row missing from CSV body:\n{body_rows}"


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


def test_bench_palette_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + one row per palette + TOTAL row.

    The per-palette run-banner must NOT pollute the CSV stream in `--csv`
    mode (it's routed to stderr instead) so the stdout is a clean
    parseable CSV document an operator can pipe straight into a
    spreadsheet / CI parser.
    """
    assert PALETTE_SCRIPT.is_file(), f"missing bench script: {PALETTE_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(PALETTE_SCRIPT),
            "--csv",
            "--iterations",
            "2",
            "--limit",
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
        f"bench_palette.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_palette.py --csv produced empty stdout:\n{out!r}"
    lines = out.splitlines()
    assert lines[0] == "palette,mean_ms,p95_ms", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # Subsequent rows must include at least one palette name and a TOTAL
    # row — the test catches a regression where the header emits but the
    # body is dropped, or where the TOTAL summary row stops being written.
    body_rows = lines[1:]
    assert any(
        row and not row.startswith("TOTAL,") and not row.startswith("palette,")
        for row in body_rows
    ), f"no per-palette row in CSV body:\n{body_rows}"
    assert any(
        row.startswith("TOTAL,") for row in body_rows
    ), f"TOTAL row missing from CSV body:\n{body_rows}"


def test_bench_greeble_density_runs_minimal() -> None:
    """Per-density bench exits 0 and prints the column headers + TOTAL row."""
    assert GREEBLE_DENSITY_SCRIPT.is_file(), (
        f"missing bench script: {GREEBLE_DENSITY_SCRIPT}"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(GREEBLE_DENSITY_SCRIPT),
            "--iterations",
            "2",
            "--densities",
            "0.0,0.5",
            "--seed",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"bench_greeble_density.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_greeble_density.py produced empty stdout:\n{out!r}"
    # Header columns we promised in the docstring + spec.
    assert "density" in out, f"'density' header missing from stdout:\n{out}"
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


def test_bench_fleet_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + per-stage rows + TOTAL row.

    The fleet run-banner must NOT pollute the CSV stream in `--csv` mode
    (it's routed to stderr instead) so the stdout is a clean parseable
    CSV document an operator can pipe straight into a spreadsheet / CI
    parser.
    """
    assert FLEET_SCRIPT.is_file(), f"missing bench script: {FLEET_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(FLEET_SCRIPT),
            "--csv",
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
        f"bench_fleet.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_fleet.py --csv produced empty stdout:\n{out!r}"
    lines = out.splitlines()
    assert lines[0] == "stage,mean_ms,p95_ms", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # Subsequent rows must include at least one per-stage data row and a
    # TOTAL row — catches a regression where the header emits but the body
    # / TOTAL summary row is dropped.
    body_rows = lines[1:]
    assert any(
        row and not row.startswith("TOTAL,") and not row.startswith("stage,")
        for row in body_rows
    ), f"no per-stage row in CSV body:\n{body_rows}"
    assert any(
        row.startswith("TOTAL,") for row in body_rows
    ), f"TOTAL row missing from CSV body:\n{body_rows}"


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


def test_bench_summary_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + one row per bench on stdout.

    Per-bench "running ..." progress lines must NOT pollute the CSV stream
    in `--csv` mode (they're routed to stderr instead) so the stdout is a
    clean parseable CSV document an operator can pipe straight into a
    spreadsheet / CI parser.
    """
    assert SUMMARY_SCRIPT.is_file(), f"missing bench script: {SUMMARY_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(SUMMARY_SCRIPT),
            "--csv",
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
        f"bench_summary.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_summary.py --csv produced empty stdout:\n{out!r}"
    lines = out.splitlines()
    assert lines[0] == "bench,metric,iterations", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # At least one bench name must appear in the subsequent CSV rows so
    # the test catches a regression where the body is dropped while the
    # header still emits.
    body = "\n".join(lines[1:])
    assert any(
        name in body
        for name in (
            "bench_shape",
            "bench_full_pipeline",
            "bench_palette",
            "bench_mem",
            "bench_fleet",
        )
    ), f"no bench-name row in CSV body:\n{body}"


def test_bench_compare_csv_emits_csv(tmp_path: Path) -> None:
    """`--csv` flag produces a CSV header + one row per compared phase.

    bench_compare diffs two JSON baselines (the schema produced by
    ``bench_generator.py --save``) so this test synthesizes two minimal
    baseline JSON documents in ``tmp_path`` (one with a small regression in
    the ``export`` phase so the FAIL glyph is exercised) and asserts that
    ``--csv`` emits a header row + at least one data row on stdout. The
    script exits 1 on regression — we still exercise that codepath because
    a clean run with all phases equal would skip the FAIL row entirely
    (lower-signal smoke); the CSV output contract itself is independent
    of the exit code so we assert the contract, not the code.
    """
    assert COMPARE_SCRIPT.is_file(), f"missing bench script: {COMPARE_SCRIPT}"
    baseline = {
        "wall": {"total_s": 1.0},
        "phases": {
            "shape_build": {"total_s": 0.5},
            "export": {"total_s": 0.5},
        },
    }
    current = {
        "wall": {"total_s": 1.05},
        "phases": {
            "shape_build": {"total_s": 0.5},
            # 10 % regression in ``export`` so the comparator emits a FAIL
            # row — exercises the non-empty-CSV-body path.
            "export": {"total_s": 0.55},
        },
    }
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(baseline))
    current_path.write_text(json.dumps(current))

    result = subprocess.run(
        [
            sys.executable,
            str(COMPARE_SCRIPT),
            str(baseline_path),
            str(current_path),
            "--csv",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    # bench_compare exits 1 when any phase regressed beyond threshold (it
    # does in this fixture), but we don't pin the exact code — the CSV
    # output contract is independent of regression status.
    out = result.stdout
    assert out.strip(), (
        f"bench_compare.py --csv produced empty stdout:\n{out!r}\n"
        f"stderr:\n{result.stderr}"
    )
    lines = out.splitlines()
    assert lines[0] == "phase,baseline_s,current_s,delta_pct,status", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # At least one data row must appear in the CSV body — catches a
    # regression where the header emits but the body is dropped.
    body_rows = [row for row in lines[1:] if row.strip()]
    assert body_rows, f"no per-phase row in CSV body:\n{lines}"


def test_bench_generator_csv_emits_csv() -> None:
    """`--csv` flag produces a CSV header + per-phase rows + WALL TOTAL row.

    The run banner / cProfile top-N print must NOT pollute the CSV stream
    in `--csv` mode (they're routed to stderr instead) so the stdout is a
    clean parseable CSV document an operator can pipe straight into a
    spreadsheet / CI parser. ``bench_generator.py`` uses ``--n`` (not
    ``--iterations``) for ship count — that's the minimal arg required to
    keep the smoke run fast.
    """
    assert GENERATOR_SCRIPT.is_file(), f"missing bench script: {GENERATOR_SCRIPT}"
    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--csv",
            "--n",
            "2",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"bench_generator.py --csv exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"bench_generator.py --csv produced empty stdout:\n{out!r}"
    lines = out.splitlines()
    assert lines[0] == "phase,total_s,mean_s,pct", (
        f"first stdout line should be the CSV header, got:\n{lines[0]!r}"
    )
    # Subsequent rows must include at least one per-phase data row — catches
    # a regression where the header emits but the body / WALL TOTAL summary
    # row is dropped.
    body_rows = lines[1:]
    assert any(
        row and not row.startswith("WALL TOTAL,") and not row.startswith("phase,")
        for row in body_rows
    ), f"no per-phase row in CSV body:\n{body_rows}"
    assert any(
        row.startswith("WALL TOTAL,") for row in body_rows
    ), f"WALL TOTAL row missing from CSV body:\n{body_rows}"
