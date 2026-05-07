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

## CSV output format

Every `bench_*.py` script accepts `--csv` to emit CSV instead of the
default fixed-width table. CSV goes to **stdout** (pipes straight into
a spreadsheet or CI parser); banner + per-iter progress moves to
**stderr**. Row semantics differ per script — see below.

### bench_shape.py — per-stage shape-pipeline wall-clock

Header `stage,mean_ms,p95_ms,total_ms`. One row per stage (`hull`,
`cockpit`, `engines`, `wings`, `greebles`, `assembly`) plus a `TOTAL`
row from the same aggregate the fixed-width formatter consumes.

### bench_full_pipeline.py — end-to-end `generate()` wall-clock

Header `stage,mean_ms,p95_ms,total_ms`. Two rows: a `pipeline` row
carrying the per-iteration aggregate and a `TOTAL` row that echoes
the same numbers (matches `bench_shape.py`'s shape).

### bench_palette.py — per-palette `generate()` wall-clock

Header `palette,mean_ms,p95_ms`. One row per palette (fixed-width
order) plus a final `TOTAL` row aggregated across the per-iter sample
pool of all palettes.

### bench_greeble_density.py — per-density `generate()` sweep

Header `density,mean_ms,p95_ms`. One row per density (3-decimal
format, in `--densities` order) plus a `TOTAL` row aggregated across
all per-iter samples.

### bench_mem.py — peak Python heap (MB) via `tracemalloc`

Header `iters,mean_mb,p95_mb,max_mb`. Exactly one data row carrying
the aggregate; no per-iter rows, no `TOTAL` row (the single row **is**
the total).

### bench_fleet.py — fleet-build wall-clock

Header `stage,mean_ms,p95_ms`. Three rows: `per_ship` (fleet wall /
`--fleet-count`), `fleet` (raw per-iter fleet wall), and `TOTAL`
(echoes `fleet`, since `per_ship` is a divided-by-N average).

### bench_generator.py — cProfile phase attribution over N ships

Header `phase,total_s,mean_s,pct`. One row per phase in fixed order
(`shape_build`, `role_assign`, `palette_lookup`, `export`, `other`)
plus a `WALL TOTAL` row whose `total_s` is summed walls, `mean_s` is
wall-per-ship, and `pct` is empty.

### bench_compare.py — diff between two `--save` baselines

Header `phase,baseline_s,current_s,delta_pct,status`. One row per
phase (`shape_build`, `role_assign`, `palette_lookup`, `export`,
`other`, `total`); no separate summary row (`total` **is** the
summary). `delta_pct` emits `+inf` for new phases; `status` is the
same `OK` / `WARN` / `FAIL` glyph as the markdown render.

### bench_summary.py — umbrella driver of all sibling benches

Header `bench,metric,iterations`. One row per child bench. `metric`
is `"<mean> <unit>"` on success (e.g. `12.345 ms`); failures emit
`metric=FAIL` and `iterations=0`. No separate `TOTAL` row.

### Quick reference

| script | columns | row meaning | TOTAL row? |
|---|---|---|---|
| `bench_shape.py` | `stage,mean_ms,p95_ms,total_ms` | per-stage | yes |
| `bench_full_pipeline.py` | `stage,mean_ms,p95_ms,total_ms` | single `pipeline` stage | yes (echoes `pipeline`) |
| `bench_palette.py` | `palette,mean_ms,p95_ms` | per-palette | yes |
| `bench_greeble_density.py` | `density,mean_ms,p95_ms` | per-density | yes |
| `bench_mem.py` | `iters,mean_mb,p95_mb,max_mb` | single summary | no (only row) |
| `bench_fleet.py` | `stage,mean_ms,p95_ms` | `per_ship` + `fleet` | yes (echoes `fleet`) |
| `bench_generator.py` | `phase,total_s,mean_s,pct` | per-phase | `WALL TOTAL` |
| `bench_compare.py` | `phase,baseline_s,current_s,delta_pct,status` | per-phase (incl. `total`) | no separate row |
| `bench_summary.py` | `bench,metric,iterations` | per-child-bench | no |

See [`bench-ci.md`](bench-ci.md) for ingest-into-CI patterns.
