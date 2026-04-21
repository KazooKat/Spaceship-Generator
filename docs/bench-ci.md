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
