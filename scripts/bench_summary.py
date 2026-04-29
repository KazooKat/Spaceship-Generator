"""Umbrella driver running every bench script under ``scripts/``.

Stdlib only. Spawns the five sibling bench scripts via :func:`subprocess.run`
(using :data:`sys.executable` so we share the active interpreter / venv) and
parses each one's TOTAL line to build a single fixed-width aggregate table.

Covered benches:

* ``bench_full_pipeline.py`` — end-to-end ``generate()`` wall-clock
* ``bench_shape.py``         — per-stage shape pipeline wall-clock
* ``bench_palette.py``       — per-palette ``generate()`` wall-clock
* ``bench_mem.py``           — peak Python heap (MB) per ``generate()``
* ``bench_fleet.py``         — fleet-build wall-clock

This turns the five micro-benches into a single "perf snapshot" command
useful before/after a refactor — complements per-script depth with
cross-script breadth. We keep going if one bench fails (the row prints
``FAIL`` and the umbrella exits non-zero only at the end), so a single
broken bench doesn't blackhole the rest of the snapshot.

Usage:
    .venv/Scripts/python scripts/bench_summary.py
    .venv/Scripts/python scripts/bench_summary.py --iterations 5 --seed 42
    .venv/Scripts/python scripts/bench_summary.py --limit 4 --fleet-count 4

Each child bench writes its own ``.litematic`` files into a private
``tempfile.TemporaryDirectory``, so this driver also leaves no files
behind on disk.
"""

from __future__ import annotations

import argparse
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Locate sibling scripts. Resolved up-front so an early ``--help`` doesn't
# pay the cost of stat'ing every script.
SCRIPTS_DIR = Path(__file__).resolve().parent

# Regex catching the TOTAL row from any of the five sibling benches. The
# benches all use the same fixed-width ``{label:<10} {n:>12.3f} {n:>12.3f}
# [...]`` template (see e.g. ``bench_full_pipeline.print_table``), so we
# pull every numeric field after the literal ``TOTAL`` token and let the
# caller decide how to label them. Trailing ``(n=...)`` / ``(palettes=...,
# n=...)`` / ``(ships=..., n=...)`` annotations are ignored — the n value
# we report is the one passed in via ``--iterations``.
_TOTAL_RE = re.compile(
    r"^\s*TOTAL\s+(?P<rest>.+?)\s*$",
    re.MULTILINE,
)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class BenchSpec:
    """One row of the umbrella table — a single child bench to run."""

    name: str  # script filename without ``.py`` (e.g. ``bench_shape``)
    script: str  # script filename WITH ``.py`` (for subprocess argv)
    metric_unit: str  # ``ms`` or ``mb`` — drives the table's value column header
    args_factory: str  # method name on Args to build this bench's argv tail


@dataclass
class BenchResult:
    """One row of parsed output from a child bench."""

    name: str
    ok: bool
    # Primary metric (mean) extracted from the TOTAL line. ``None`` on FAIL.
    mean: float | None
    # Iteration count we asked the bench to run (echoed back into the table
    # so an operator can see at a glance which N produced these numbers).
    iterations: int
    unit: str  # ``ms`` or ``mb``
    # Stderr captured from the child — printed below the table on FAIL so
    # the operator sees the actual error without having to re-run the bench.
    stderr: str = ""


# Bench list in the order they should appear in the aggregate table. We
# put the cheapest (shape, ~ms per iter) first and the broadest
# (full_pipeline, palette, fleet) after so a Ctrl-C mid-run still leaves
# the operator with the cheapest signal.
BENCHES: tuple[BenchSpec, ...] = (
    BenchSpec(
        name="bench_shape",
        script="bench_shape.py",
        metric_unit="ms",
        args_factory="shape_args",
    ),
    BenchSpec(
        name="bench_full_pipeline",
        script="bench_full_pipeline.py",
        metric_unit="ms",
        args_factory="full_pipeline_args",
    ),
    BenchSpec(
        name="bench_palette",
        script="bench_palette.py",
        metric_unit="ms",
        args_factory="palette_args",
    ),
    BenchSpec(
        name="bench_mem",
        script="bench_mem.py",
        metric_unit="mb",
        args_factory="mem_args",
    ),
    BenchSpec(
        name="bench_fleet",
        script="bench_fleet.py",
        metric_unit="ms",
        args_factory="fleet_args",
    ),
)


class _ArgsBuilder:
    """Builds per-bench argv tails from the umbrella's parsed CLI args.

    Each ``*_args`` method returns the list passed to ``subprocess.run``
    *after* the script path. Centralising this here keeps the bench-spec
    table above declarative — every flag mapping lives in one place.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args

    def shape_args(self) -> list[str]:
        return [
            "--iterations", str(self._args.iterations),
            "--seed", str(self._args.seed),
        ]

    def full_pipeline_args(self) -> list[str]:
        return [
            "--iterations", str(self._args.iterations),
            "--seed", str(self._args.seed),
        ]

    def palette_args(self) -> list[str]:
        # ``--limit 0`` would mean "all palettes" — keep the umbrella fast
        # by clamping to a small subset by default, mirroring the
        # bench_palette smoke-test pattern.
        return [
            "--iterations", str(self._args.iterations),
            "--limit", str(self._args.limit),
            "--seed", str(self._args.seed),
        ]

    def mem_args(self) -> list[str]:
        return [
            "--iterations", str(self._args.iterations),
            "--seed", str(self._args.seed),
        ]

    def fleet_args(self) -> list[str]:
        return [
            "--iterations", str(self._args.iterations),
            "--fleet-count", str(self._args.fleet_count),
            "--seed", str(self._args.seed),
        ]


def _parse_total_mean(stdout: str) -> float | None:
    """Pull the first numeric field from the TOTAL row of a bench's stdout.

    All five sibling benches print their TOTAL row in the same shape:

        TOTAL  mean_X  p95_X  [extra cols...]  (annotations)

    so the first number after ``TOTAL`` is always the mean. Returning the
    mean (rather than e.g. the total) keeps the umbrella's headline column
    apples-to-apples across benches whose rightmost column differs
    (``total_ms`` for time benches, ``max_mb`` for the memory bench, no
    third numeric for palette/fleet because they only print mean+p95).
    """
    match = _TOTAL_RE.search(stdout)
    if match is None:
        return None
    numbers = _NUMBER_RE.findall(match.group("rest"))
    if not numbers:
        return None
    try:
        return float(numbers[0])
    except ValueError:
        return None


def _run_bench(
    spec: BenchSpec,
    extra_argv: list[str],
    *,
    iterations: int,
) -> BenchResult:
    """Run one child bench and return a parsed :class:`BenchResult`.

    Errors (non-zero exit, missing TOTAL line, unparseable mean) are
    captured into ``BenchResult(ok=False, ...)`` rather than raised — the
    umbrella keeps walking and the caller decides the final exit code.
    """
    script_path = SCRIPTS_DIR / spec.script
    if not script_path.is_file():
        return BenchResult(
            name=spec.name,
            ok=False,
            mean=None,
            iterations=iterations,
            unit=spec.metric_unit,
            stderr=f"missing script: {script_path}",
        )

    cmd = [sys.executable, str(script_path), *extra_argv]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # e.g. interpreter missing on a busted venv
        return BenchResult(
            name=spec.name,
            ok=False,
            mean=None,
            iterations=iterations,
            unit=spec.metric_unit,
            stderr=f"OSError: {exc}",
        )

    if completed.returncode != 0:
        return BenchResult(
            name=spec.name,
            ok=False,
            mean=None,
            iterations=iterations,
            unit=spec.metric_unit,
            stderr=completed.stderr.strip() or completed.stdout.strip(),
        )

    mean = _parse_total_mean(completed.stdout)
    if mean is None:
        return BenchResult(
            name=spec.name,
            ok=False,
            mean=None,
            iterations=iterations,
            unit=spec.metric_unit,
            stderr=(
                "could not parse TOTAL line from stdout; got:\n"
                + completed.stdout.strip()
            ),
        )

    return BenchResult(
        name=spec.name,
        ok=True,
        mean=mean,
        iterations=iterations,
        unit=spec.metric_unit,
    )


def print_table(results: list[BenchResult]) -> None:
    """Emit the aggregate fixed-width table to stdout.

    Layout mirrors ``bench_full_pipeline.print_table`` so an operator can
    eyeball the umbrella next to any single child bench. Columns:

        bench_name | mean (ms or mb) | iterations

    Failed rows print ``FAIL`` in the metric column with their unit still
    showing so the operator knows which metric was being measured.
    """
    name_width = max((len(r.name) for r in results), default=10)
    name_width = max(name_width, len("bench"))

    print()
    print(f"{'bench':<{name_width}} {'metric':>16} {'iterations':>12}")
    print("-" * (name_width + 1 + 16 + 1 + 12))
    for r in results:
        if r.ok and r.mean is not None:
            metric_str = f"{r.mean:>10.3f} {r.unit}"
        else:
            metric_str = f"{'FAIL':>10} {r.unit}"
        # The right-justified format width is 16 chars for the metric
        # column so the ``mean unit`` text lines up regardless of the
        # number's width. ``{metric_str:>16}`` would re-pad after we
        # already padded internally — write it raw instead.
        print(f"{r.name:<{name_width}} {metric_str:>16} {r.iterations:>12d}")
    print("-" * (name_width + 1 + 16 + 1 + 12))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--iterations", type=int, default=2,
        help="iterations passed to each child bench (default: 2)",
    )
    p.add_argument(
        "--limit", type=int, default=2,
        help="palette subset size for bench_palette (default: 2)",
    )
    p.add_argument(
        "--seed", type=int, default=0,
        help="base seed forwarded to every bench (default: 0)",
    )
    p.add_argument(
        "--fleet-count", type=int, default=2,
        help="ships per fleet for bench_fleet (default: 2)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1:
        print("--iterations must be >= 1", file=sys.stderr)
        return 2
    if args.limit < 1:
        # Unlike bench_palette, where ``--limit 0`` means "all palettes",
        # the umbrella defaults to a small subset to keep wall-clock low.
        # Allowing 0 here would silently expand the matrix on every
        # invocation, which is rarely what an operator wants from a
        # snapshot driver.
        print("--limit must be >= 1", file=sys.stderr)
        return 2
    if args.fleet_count < 1:
        print("--fleet-count must be >= 1", file=sys.stderr)
        return 2

    print(
        f"bench_summary: iterations={args.iterations}  limit={args.limit}  "
        f"seed={args.seed}  fleet_count={args.fleet_count}  "
        f"py={sys.version.split()[0]}  "
        f"proc={(platform.processor() or platform.machine())[:60]}"
    )

    builder = _ArgsBuilder(args)
    results: list[BenchResult] = []
    for spec in BENCHES:
        # ``getattr`` lookup on the builder keeps the bench-spec table
        # declarative — adding a new bench is just a new BenchSpec entry
        # plus a new ``*_args`` method.
        factory = getattr(builder, spec.args_factory)
        # Print the bench name *before* running so an operator who
        # ctrl-c's mid-run knows which bench was in flight.
        print(f"running {spec.name} ...")
        results.append(_run_bench(
            spec,
            factory(),
            iterations=args.iterations,
        ))

    print_table(results)

    # Print captured stderr for any failures *after* the table so the
    # aggregate table stays the last thing scrolled when everything passes
    # but the operator still sees diagnostics on failure.
    failures = [r for r in results if not r.ok]
    for r in failures:
        print(f"\n[{r.name}] FAIL", file=sys.stderr)
        if r.stderr:
            print(r.stderr, file=sys.stderr)

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
