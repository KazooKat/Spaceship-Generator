# Perf bench CI

## What it does

`.github/workflows/bench.yml` runs on every pull request that touches
`src/**`, `scripts/bench_generator.py`, or `scripts/bench_compare.py`. It:

1. Checks out the PR base and PR head into separate directories.
2. Runs `scripts/bench_generator.py --n 12 --save <path>` on each, under
   Python 3.12 on `ubuntu-latest`.
3. Diffs the two JSON baselines via `scripts/bench_compare.py --threshold 0.10`.
4. Posts the resulting markdown table as a PR comment.

The job never fails the check run; it is informational only.

## How to read the comment

The comment renders one row per phase (`shape_build`, `role_assign`,
`palette_lookup`, `export`, `other`, `total`) with:

- `baseline_s` — wall seconds on the PR base commit.
- `current_s` — wall seconds on the PR head commit.
- `delta_%` — relative change (positive means slower).
- `status` — a glyph: check mark for fine, warning for mild drift,
  cross for a regression above the configured threshold (default 10%).

## Updating the baseline when a slowdown is intentional

There is no committed baseline file; each run compares PR base to PR head.
If a regression is intentional (for example, a more accurate shape algorithm
that is inherently slower):

1. Call it out in the PR description so reviewers understand the cross glyph.
2. If desired, raise the threshold for this one PR by editing the workflow
   (`--threshold 0.15` etc.) in a follow-up, then revert.
3. After merge, the next PR will see the new post-merge timings as its
   baseline, so the regression is "absorbed" automatically.

## Caveat: runner variance

GitHub-hosted runners share hardware and show 5-15% per-run variance on
short CPU-bound workloads. Treat a single red cell as a yellow flag, not
proof of regression. If a delta looks real, run the bench locally
(`.venv/Scripts/python scripts/bench_generator.py --n 40`) to confirm.

## Example CI snippets

Concrete copy-paste stanzas for ingesting `bench_*.py --csv` output into
CI. Column / row semantics for each script are documented in
[`bench.md`](bench.md) under `## CSV output format` — match the column
names from there when parsing.

Every `--csv` invocation writes CSV to **stdout** and the banner /
per-iter progress to **stderr**. Redirect stdout only (`> file.csv`);
do **not** use `2>&1`, which would interleave the banner into the CSV
and break header parsing.

### GitHub Actions

```yaml
jobs:
  bench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - name: Run aggregate bench summary
        run: python scripts/bench_summary.py --csv > bench-summary.csv
      - uses: actions/upload-artifact@v4
        with:
          name: bench-summary
          path: bench-summary.csv
```

Swap `bench_summary.py` for `bench_full_pipeline.py --csv` or any other
sibling script when a narrower signal is wanted.

### GitLab CI

```yaml
bench:
  image: python:3.12
  script:
    - pip install -e .
    - python scripts/bench_summary.py --csv > bench-summary.csv
  artifacts:
    paths:
      - bench-summary.csv
    expire_in: 1 week
```

### Regression detection against a committed baseline

Commit a known-good `bench_generator.py --save` baseline at
`bench/baseline.csv` (generated via `bench_compare.py --csv` against
itself, or hand-rolled from a `--save` JSON), then fail the job if any
phase's `delta_pct` exceeds a threshold. `bench_compare.py --csv` emits
`phase,baseline_s,current_s,delta_pct,status` — the bash one-liner below
parses the `delta_pct` column (field 4) and exits non-zero if any row
breaches 10%.

```yaml
jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - run: python scripts/bench_generator.py --n 12 --save current.json
      - name: Compare against baseline and fail on >10% regression
        run: |
          python scripts/bench_compare.py bench/baseline.json current.json --csv > diff.csv
          awk -F, 'NR>1 && $4+0 > 10.0 { print "REGRESSION:", $0; bad=1 } END { exit bad }' diff.csv
```

## Sample GitHub Actions workflow

Drop-in `.github/workflows/bench.yml` companion to the per-stanza
snippets above — a complete, self-contained workflow that runs the
end-to-end `bench_full_pipeline.py` driver, uploads the CSV as an
artifact, and (optionally) gates on a checked-in baseline using the
Python one-liner mirrored from [`bench.md`](bench.md#3-diff-csv-vs-baseline-awk-one-liner).

Triggers on every push and every pull request so both branch CI and PR
checks share the same artifact name. Baseline diff step is gated on
`bench/baseline.csv` existing, so the workflow stays green on repos
that haven't committed one yet.

```yaml
name: bench
on: [push, pull_request]
jobs:
  bench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e .
      - name: Run end-to-end pipeline bench
        run: python scripts/bench_full_pipeline.py --iterations 20 --csv > bench_out.csv
      - uses: actions/upload-artifact@v4
        with:
          name: bench-full-pipeline
          path: bench_out.csv
      - name: Diff against checked-in baseline (optional)
        if: hashFiles('bench/baseline.csv') != ''
        run: |
          python - <<'PY'
          import csv, sys
          base = {r[0]: float(r[1]) for r in csv.reader(open("bench/baseline.csv")) if r and r[0] != "stage"}
          bad = 0
          for r in csv.reader(open("bench_out.csv")):
              if not r or r[0] == "stage" or r[0] not in base: continue
              cur = float(r[1])
              if cur > base[r[0]] * 1.20:
                  print(f"REGRESSION {r[0]}: {cur:.3f} vs {base[r[0]]:.3f}"); bad = 1
          sys.exit(bad)
          PY
```

Swap `bench_full_pipeline.py` for any sibling bench (`bench_shape.py`,
`bench_palette.py`, `bench_mem.py`, ...) when a narrower signal is
wanted — the rest of the workflow (setup, artifact upload, baseline
gate) stays identical because every `bench_*.py --csv` writes to
stdout under the same stream-split convention.
