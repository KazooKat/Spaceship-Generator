# Bench scripts

Catalog of every `scripts/bench_*.py` micro-benchmark — what each one
measures and the canonical invocation. Companion to
[quickstart.md](quickstart.md) (5-minute walk),
[cli.md](cli.md) (CLI flag reference),
[troubleshooting.md](troubleshooting.md) (common errors), and
[faq.md](faq.md) ("how do I...?" reference).

All scripts are stdlib + numpy only and write any `.litematic` output
into a `tempfile.TemporaryDirectory` so nothing leaks onto disk between
runs. Pass `--help` to any script for the full flag list.

## Catalog

| Script | What it measures | Example invocation |
|---|---|---|
| `bench_shape.py` | Per-stage wall-clock for the shape pipeline (`hull` -> `cockpit` -> `engines` -> `wings` -> `greebles` -> `assembly`). | `.venv/Scripts/python scripts/bench_shape.py --iterations 50 --seed 0` |
| `bench_full_pipeline.py` | End-to-end wall-clock for one full `generate()` call (shape + texture + weapons + `.litematic` write). | `.venv/Scripts/python scripts/bench_full_pipeline.py --iterations 50 --seed 0` |
| `bench_palette.py` | Per-palette wall-clock for `generate()` across every shipped palette (or a `--limit N` subset). | `.venv/Scripts/python scripts/bench_palette.py --iterations 3 --limit 0` |
| `bench_greeble_density.py` | Per-greeble-density wall-clock sweep for `generate()` — surfaces cost slope vs density. | `.venv/Scripts/python scripts/bench_greeble_density.py --iterations 3 --densities 0.0,0.25,0.5,0.75,1.0` |
| `bench_mem.py` | Peak Python heap (MB) for one full `generate()` call via `tracemalloc`. | `.venv/Scripts/python scripts/bench_mem.py --iterations 5 --seed 0` |
| `bench_fleet.py` | Fleet-build wall-clock — planning + per-ship `generate()` calls inside a single `perf_counter` window. | `.venv/Scripts/python scripts/bench_fleet.py --fleet-count 4 --iterations 3` |
| `bench_generator.py` | cProfile-based phase attribution (`shape_build` / `role_assign` / `palette_lookup` / `export` / `other`) over N ships; can `--save baseline.json` for later comparison. | `.venv/Scripts/python scripts/bench_generator.py --n 20 --save base.json` |
| `bench_compare.py` | Markdown diff table comparing two `bench_generator.py --save` baselines; exits 1 if any phase regressed beyond `--threshold` (default 10%). | `.venv/Scripts/python scripts/bench_compare.py base.json current.json --threshold 0.10` |
| `bench_summary.py` | Umbrella driver — runs every sibling bench via `subprocess.run([sys.executable, ...])` and prints a single aggregate `bench | metric | iterations` table. | `.venv/Scripts/python scripts/bench_summary.py --iterations 2 --limit 2 --fleet-count 2` |

## How to read the output

Every wall-clock bench prints a fixed-width table whose rows carry
`mean_ms` and `p95_ms` columns and whose final `TOTAL` row aggregates
the per-iteration samples across all measured units (stages, palettes,
densities, ships). `bench_mem.py` substitutes `mean_mb` / `p95_mb` /
`max_mb` for the same shape, and `bench_generator.py` prints a
cProfile-attributed `phase | total_s | mean_s | pct` table instead.

## Aggregate snapshot

For a one-shot perf snapshot before/after a refactor, run
`bench_summary.py` — it invokes `bench_shape`, `bench_full_pipeline`,
`bench_palette`, `bench_mem`, and `bench_fleet` in sequence and prints
their TOTAL rows in a single consolidated table.
