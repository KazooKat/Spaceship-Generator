# Contributing

Short development guide for anyone working on the codebase — including the
dev-swarm tick that ships small feature units cycle-over-cycle. Cross-links to
the deeper docs at the bottom.

## Repo layout

- `src/spaceship_generator/` — Python package source. Top-level modules
  (`cli.py`, `generator.py`, `fleet.py`, `texture.py`, `palette.py`,
  `preview.py`, `export.py`, `*_styles.py`, `presets.py`, `block_colors.py`)
  plus the `shape/` voxel-pipeline subpackage and the `web/` Flask app.
- `tests/` — `pytest` suite (2116 tests at time of writing). Property tests
  live in `tests/test_properties.py`; bench smoke tests live in
  `tests/test_bench_smoke.py`.
- `scripts/` — developer-facing utilities: `bench_*.py` micro-benchmarks,
  `palette_lint.py` (strict palette linter), `gen_gallery.py`, `smoke_e2e.py`.
- `palettes/` — block-palette YAML files (one per palette). Drop a new
  `<name>.yaml` here to ship a new palette.
- `docs/` — Markdown documentation. `CHANGELOG.md` and `todo.md` live here.

## Local setup

Requires Python 3.11+.

```bash
git clone https://github.com/KazooKat/Spaceship-Generator.git
cd Spaceship-Generator
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
```

The `[dev]` extra pulls in `pytest`, `pytest-cov`, `hypothesis`, and `ruff`
(declared in `pyproject.toml`).

## Tests & lint

```bash
python -m pytest -q       # full suite (2116 tests)
ruff check .              # lint
```

Property tests (Hypothesis + parametrize) live in `tests/test_properties.py`
and pin invariants like "every `(StructureStyle, HullStyle)` pair generates a
non-empty `.litematic`". Bench smoke tests in `tests/test_bench_smoke.py`
shell out to each `scripts/bench_*.py` script with the smallest footprint to
catch regressions in the bench harnesses themselves.

## Benchmarks

The `scripts/bench_*.py` family measures wall-clock cost of every hot path
(`bench_shape`, `bench_full_pipeline`, `bench_palette`, `bench_fleet`,
`bench_mem`, `bench_generator`, `bench_compare`, `bench_greeble_density`).
See [bench.md](bench.md) for the full catalog and [bench-ci.md](bench-ci.md)
for the CI snapshot integration.

For a one-shot perf snapshot before/after a refactor use
`scripts/bench_summary.py` — it runs every sibling bench and prints their
TOTAL rows in a single consolidated table.

## Adding a palette

Drop `<name>.yaml` under `palettes/` mapping every required `Role` to a
Minecraft block ID, then run the strict linter before opening a PR:

```bash
python scripts/palette_lint.py --file palettes/<name>.yaml --strict
```

See [palette_authoring.md](palette_authoring.md) for the full schema, contrast
floor, and emissive-ENGINE_GLOW rule.

## Branch / commit / PR convention

- Branch off `main`; one feature unit per branch (`feat-<short-slug>`).
- Commit messages follow Conventional Commits — `feat(...)`, `fix(...)`,
  `docs(...)`, `chore(...)`, `test(...)` prefixes (match `git log`).
- Keep the diff focused — one feature/fix per PR. Close every PR with a
  CHANGELOG bullet at the top of `## [Unreleased]` in `docs/CHANGELOG.md`.

## Where to file bugs

Open an issue at <https://github.com/KazooKat/Spaceship-Generator/issues>.
Include the seed, palette name, and CLI args (or web form values) needed to
reproduce — most bugs in a deterministic procedural generator are
seed-specific, so a minimal repro saves a lot of bisecting.

## Cross-links

- [quickstart.md](quickstart.md) — 5-minute getting-started guide.
- [architecture.md](architecture.md) — pipeline + bounded contexts.
- [cli.md](cli.md) — full CLI flag reference.
- [web_ui.md](web_ui.md) — HTTP API + Flask routes.
- [release.md](release.md) — release checklist (tag-driven, PyPI OIDC).
- [troubleshooting.md](troubleshooting.md) — common-error reference.
- [faq.md](faq.md) — common-question reference.
- [bench.md](bench.md) — bench-script catalog.
- [palette_authoring.md](palette_authoring.md) — palette YAML schema.
