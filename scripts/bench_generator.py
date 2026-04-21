"""Benchmark harness for the spaceship generator pipeline.

Stdlib + numpy only. Generates N ships and uses cProfile to split time across
four phases: shape_build, role_assign, palette_lookup, export.

Usage:
    .venv/Scripts/python scripts/bench_generator.py
    .venv/Scripts/python scripts/bench_generator.py --n 10 --save base.json
    .venv/Scripts/python scripts/bench_generator.py --compare base.json
"""

from __future__ import annotations

import argparse
import cProfile
import json
import platform
import pstats
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Phase -> list of (module_substring, function_name) attribution rules.
# A profiled function whose (file, name) matches any rule is charged to that
# phase. Order matters only for readability — every function maps to at most
# one phase because the substrings are disjoint.
# Phase attribution: (file_substring, func_name_or_empty). Empty func matches
# every function in that file. Substrings are matched against the normalized
# (forward-slash, lowercase) file path so e.g. the ``shape/`` package, the
# legacy ``shape.py``, and nested files like ``shape/assembly.py`` all resolve.
PHASE_RULES: dict[str, list[tuple[str, str]]] = {
    "shape_build": [
        ("/shape/", ""),           # whole shape/ package (paths normalized)
        ("/shape.py", ""),         # legacy top-level module, if present
        ("wing_styles.py", ""),
        ("structure_styles.py", ""),
    ],
    "role_assign":    [("texture.py", "")],
    "palette_lookup": [("palette.py", "")],
    "export": [
        ("export.py", ""),
        ("litemapy", ""),
        ("nbtlib", ""),
    ],
}

# Ship configurations cycled through during the benchmark. Kept small so the
# full run completes in a few seconds on a laptop.
DIM_PRESETS: list[tuple[str, dict[str, int]]] = [
    ("small", {"length": 24, "width_max": 12, "height_max": 8}),
    ("med",   {"length": 40, "width_max": 20, "height_max": 12}),
    ("large", {"length": 64, "width_max": 32, "height_max": 18}),
]

PALETTE_ROTATION = [
    "sci_fi_industrial",
    "stealth_black",
    "nordic_scout",
    "sleek_modern",
]


def classify(file_path: str, func_name: str) -> str | None:
    """Map a (file, func) pair to a phase name or ``None`` if unattributed."""
    norm = file_path.replace("\\", "/").lower()
    for phase, rules in PHASE_RULES.items():
        for file_sub, name_sub in rules:
            # Normalize the rule substring too (so a \\shape\\ rule still
            # matches the forward-slash norm, and vice versa).
            sub = file_sub.replace("\\", "/").lower()
            if sub not in norm:
                continue
            if name_sub and name_sub != func_name:
                continue
            return phase
    return None


def run_once(seed: int, dim_name: str, dim_kwargs: dict[str, int], palette_name: str,
             out_dir: Path) -> float:
    """Run a single generate() call and return wall-clock seconds."""
    from spaceship_generator.generator import generate
    from spaceship_generator.shape import ShapeParams

    sp = ShapeParams(**dim_kwargs)
    fname = f"bench_{dim_name}_{palette_name}_{seed}.litematic"
    t0 = time.perf_counter()
    generate(
        seed,
        palette=palette_name,
        shape_params=sp,
        out_dir=str(out_dir),
        filename=fname,
        with_preview=False,
    )
    return time.perf_counter() - t0


def build_workload(n: int) -> list[tuple[int, str, dict[str, int], str]]:
    """Return N (seed, dim_name, dim_kwargs, palette) tuples, deterministic."""
    jobs: list[tuple[int, str, dict[str, int], str]] = []
    for i in range(n):
        seed = 1000 + i * 37  # fixed, reproducible
        dim_name, dim_kwargs = DIM_PRESETS[i % len(DIM_PRESETS)]
        palette = PALETTE_ROTATION[i % len(PALETTE_ROTATION)]
        jobs.append((seed, dim_name, dict(dim_kwargs), palette))
    return jobs


def profile_workload(jobs: list[tuple[int, str, dict[str, int], str]],
                     out_dir: Path) -> tuple[pstats.Stats, list[float], cProfile.Profile]:
    """Run all jobs under cProfile and return (stats, per_job_wall, profiler)."""
    wall_times: list[float] = []
    prof = cProfile.Profile()
    prof.enable()
    try:
        for seed, dim_name, dim_kwargs, palette in jobs:
            wall = run_once(seed, dim_name, dim_kwargs, palette, out_dir)
            wall_times.append(wall)
    finally:
        prof.disable()
    stats = pstats.Stats(prof)
    return stats, wall_times, prof


def summarize_phases(stats: pstats.Stats, n_jobs: int) -> dict[str, dict[str, Any]]:
    """Walk pstats entries and bucket cumulative time by phase."""
    phases: dict[str, dict[str, Any]] = {
        name: {"total_s": 0.0, "hot_func": None, "hot_s": 0.0, "calls": 0}
        for name in PHASE_RULES
    }
    # Unattributed bucket so the table always sums to something sensible.
    phases["other"] = {"total_s": 0.0, "hot_func": None, "hot_s": 0.0, "calls": 0}

    # stats.stats is the raw dict: {(file, line, name): (cc, nc, tt, ct, callers)}
    # We use tt (total time in function, excluding subcalls) for attribution so
    # phases do not double-count nested calls.
    raw = stats.stats  # type: ignore[attr-defined]
    for (file_path, lineno, func_name), (_cc, nc, tt, _ct, _callers) in raw.items():
        phase = classify(file_path, func_name) or "other"
        entry = phases[phase]
        entry["total_s"] += tt
        entry["calls"] += nc
        if tt > entry["hot_s"]:
            entry["hot_s"] = tt
            pretty = f"{Path(file_path).name}:{lineno}:{func_name}"
            entry["hot_func"] = pretty

    grand = sum(p["total_s"] for p in phases.values()) or 1e-9
    for p in phases.values():
        p["mean_s"] = p["total_s"] / max(1, n_jobs)
        p["pct"] = 100.0 * p["total_s"] / grand
    return phases


def print_table(phases: dict[str, dict[str, Any]], wall_times: list[float]) -> None:
    order = ["shape_build", "role_assign", "palette_lookup", "export", "other"]
    total_wall = sum(wall_times)
    mean_wall = total_wall / max(1, len(wall_times))
    print()
    print(f"{'phase':<16} {'total_s':>10} {'mean_s':>10} {'pct':>7}   hottest")
    print("-" * 78)
    for name in order:
        p = phases[name]
        hot = p["hot_func"] or "-"
        print(
            f"{name:<16} {p['total_s']:>10.4f} {p['mean_s']:>10.4f} "
            f"{p['pct']:>6.1f}%   {hot}"
        )
    print("-" * 78)
    print(
        f"{'WALL TOTAL':<16} {total_wall:>10.4f} {mean_wall:>10.4f} "
        f"(n={len(wall_times)} ships)"
    )


def build_baseline(phases: dict[str, dict[str, Any]], wall_times: list[float],
                   n_jobs: int) -> dict[str, Any]:
    return {
        "meta": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "n_jobs": n_jobs,
        },
        "wall": {
            "total_s": sum(wall_times),
            "mean_s": sum(wall_times) / max(1, len(wall_times)),
            "per_job_s": wall_times,
        },
        "phases": {
            name: {
                "total_s": p["total_s"],
                "mean_s": p["mean_s"],
                "pct": p["pct"],
                "hot_func": p["hot_func"],
                "calls": p["calls"],
            }
            for name, p in phases.items()
        },
    }


def compare_baselines(current: dict[str, Any], base: dict[str, Any]) -> None:
    print("\n=== COMPARISON (current vs baseline) ===")
    bw, cw = base["wall"]["total_s"], current["wall"]["total_s"]
    d = cw - bw
    pct = (d / bw * 100.0) if bw else 0.0
    print(f"WALL TOTAL    base={bw:.3f}s  current={cw:.3f}s  delta={d:+.3f}s ({pct:+.1f}%)")
    print(f"{'phase':<16} {'base_s':>10} {'cur_s':>10} {'delta_s':>10} {'delta_%':>8}")
    print("-" * 60)
    for name in ["shape_build", "role_assign", "palette_lookup", "export", "other"]:
        b = base["phases"].get(name, {}).get("total_s", 0.0)
        c = current["phases"].get(name, {}).get("total_s", 0.0)
        dd = c - b
        pp = (dd / b * 100.0) if b else 0.0
        print(f"{name:<16} {b:>10.4f} {c:>10.4f} {dd:>10.4f} {pp:>7.1f}%")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=20, help="ships to generate (default 20)")
    p.add_argument("--save", type=str, default=None, help="write baseline JSON here")
    p.add_argument("--compare", type=str, default=None, help="diff against baseline JSON")
    p.add_argument("--keep-output", action="store_true", help="keep generated files")
    p.add_argument("--out-dir", type=str, default=None, help="output dir (default: tempdir)")
    p.add_argument("--top", type=int, default=10, help="top-N hottest functions to print")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.n < 1:
        print("--n must be >= 1", file=sys.stderr)
        return 2

    print(f"benchmark: n={args.n}  py={sys.version.split()[0]}  "
          f"proc={(platform.processor() or platform.machine())[:60]}")

    use_tmp = args.out_dir is None
    if use_tmp:
        tmp = tempfile.mkdtemp(prefix="bench_gen_")
        out_dir = Path(tmp)
    else:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    try:
        jobs = build_workload(args.n)
        # Warm-up: load one palette + generate one tiny ship so imports and
        # yaml parsing are not charged to the first profiled job.
        warm_seed, warm_dim, warm_kwargs, warm_pal = jobs[0]
        run_once(warm_seed, warm_dim, warm_kwargs, warm_pal, out_dir)

        stats, wall_times, _prof = profile_workload(jobs, out_dir)
        phases = summarize_phases(stats, args.n)
        print_table(phases, wall_times)

        print()
        print(f"=== TOP {args.top} HOTTEST FUNCTIONS (tottime) ===")
        stats.sort_stats("tottime")
        stats.print_stats(args.top)

        current = build_baseline(phases, wall_times, args.n)

        if args.save:
            save_path = Path(args.save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(current, indent=2))
            print(f"\nsaved baseline -> {save_path}")

        if args.compare:
            cmp_path = Path(args.compare)
            if not cmp_path.is_file():
                print(f"--compare: file not found: {cmp_path}", file=sys.stderr)
                return 2
            base = json.loads(cmp_path.read_text())
            compare_baselines(current, base)

        return 0
    finally:
        if use_tmp and not args.keep_output:
            # Best-effort cleanup; do not fail the bench on cleanup errors.
            for p in out_dir.glob("*"):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                out_dir.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
