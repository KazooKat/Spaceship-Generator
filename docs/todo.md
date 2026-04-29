# TODO

Backlog the dev-swarm tick (`spaceship-swarm-resume`) reads, picks from, and
appends to. One bullet per unit of work. Tick off (`[x]`) only when shipped
to `main` with tests + changelog bullet.

Format per item:

```
- [ ] <id>: <one-line goal>
      scope: <files/areas allowed>
      accept: <how we know it's done>
      notes: <optional context, links, dep on other items>
```

Sort newest-on-top inside each section. Closed items are kept (with `[x]`)
for one release cycle, then pruned during release prep.

## Open — Features

### Complex & compound ship shapes
Umbrella epic: today every ship is one ellipsoid-of-revolution per
`HullStyle`. The items below extend the shape pipeline so a single ship
can be built from multiple primitives, blended profiles, or CSG ops.
Land them independently — each is its own design doc + plan.

- [ ] shapes-A-multibody: multi-body ships (twin-fuselage / catamaran / saucer-on-stick / mothership-with-pods)
      scope: `src/spaceship_generator/shape/`, `structure_styles.py`, new tests in `tests/`
      accept: at least 2 multi-body archetypes generate, pass property tests, render in preview, render in `.litematic`; new style enum + CLI flag; gallery sample committed
      notes: needs a connector/strut concept so bodies are bridged, not floating; reuse `_connect_floaters`


- [ ] shapes-C-csg: CSG operations on primitives (union/subtract/intersect of cylinders, ellipsoids, boxes)
      scope: new `src/spaceship_generator/shape/csg.py`, `shape/hull.py` (call sites), tests
      accept: ring-spine / hangar-bay cutout / hollow torus achievable via composed primitives; primitive registry + op enum; documented in `docs/architecture.md`
      notes: voxel CSG over the int8 grid is enough — no SDF library needed; keep it numpy-vectorized

- [ ] shapes-D-modular: modular segments (N stacked modules along Z, each its own primitive, with connectors)
      scope: new `shape/modules.py`, `shape/core.py` (params)
      accept: cargo-pod + bridge + engine-block archetype; segment count + module-type list configurable; greebles still place; tests
      notes: overlaps with B and C — consider whether modular-block (existing `HullStyle.MODULAR_BLOCK`) absorbs this or stays as a stepped-profile cousin

- [ ] shapes-F-other: open slot for compound-shape ideas not in A–E
      scope: TBD per concrete proposal
      accept: TBD per concrete proposal
      notes: must come with a one-paragraph design before opening a new item below this one

## Open — Bugs

(none tracked here yet)

## Open — Chores / docs

(none tracked here yet)

## Closed (last cycle)

- [x] feat-palettes-biome-pack-2026-04-29: add 2 more biome palettes (`desert_temple`, `nether_wastes`)
      scope: `palettes/desert_temple.yaml`, `palettes/nether_wastes.yaml`, `docs/palettes.md`, `docs/CHANGELOG.md`
      accept: both pass `test_palette_lint`; loadable via `--palette NAME`; alphabetical row insert in `docs/palettes.md`; CHANGELOG bullet
      notes: shipped 2026-04-29; rounds palette count to 53; `desert_temple` = sandstone hull / chiseled-sandstone HULL_DARK accent / orange-stained-glass windows / polished-granite engines / torch ENGINE_GLOW (known-emissive list) / yellow-stained-glass cockpit / smooth-sandstone wings / cut-sandstone greebles / redstone-lamp running lights / orange-terracotta interior — chose `redstone_lamp` for LIGHT (instead of torch) to avoid the duplicate-mapping warning that `windswept_hills` and `desert_sandstone` both ship with; `nether_wastes` = netherrack hull / nether-bricks HULL_DARK accent / red-stained-glass windows (preview hex `#c85a3a`, Y≈0.467 well above the 0.35 floor) / magma-block engines / glowstone ENGINE_GLOW (known-emissive list) / tinted-glass cockpit / red-nether-bricks wings / basalt greebles / soul-torch running lights / blackstone interior — every role maps to a distinct block id so no duplicate warnings; both `--strict` lint clean (WINDOW luminance ≥ 0.35, HULL/HULL_DARK contrast ≥ 1.5, ENGINE_GLOW emissive, no role duplicates); catalog rows inserted alphabetically in `docs/palettes.md` between `desert_sandstone`/`diamond_tech` and between `neon_arcade`/`nordic_scout` respectively; header count bumped from 51 to 53; full `pytest -q` + `ruff check .` both green

- [x] feat-bench-fleet: add `scripts/bench_fleet.py` micro-bench timing fleet generation across N ships
      scope: `scripts/bench_fleet.py` (new), `tests/test_bench_smoke.py` (extend), `docs/CHANGELOG.md`
      accept: script generates a fleet of N ships into a tmpdir, prints fixed-width table with per-ship mean/p95 ms + total fleet ms; exits 0; smoke test runs --fleet-count 2 --iterations 2; CHANGELOG bullet
      notes: complements `bench_full_pipeline.py` (one ship) and `bench_palette.py` (per-palette one-ship); covers the fleet path which goes through different code (--fleet-count + manifest aggregation); shipped 2026-04-29 — bench calls the in-process Python API (`generate_fleet()` plan + per-ship `generate()`) rather than shelling out so timing reflects only the build cost; warm-up iteration runs untimed so import-time caching/palette-load doesn't skew the first sample; per-ship row in the printed table is `fleet_total_ms / fleet_count` (the average per-ship cost — a true per-ship distribution would require timing each `generate()` call individually and is intentionally out of scope); `pytest -q` (1972 tests) + `ruff check .` both green

- [x] feat-tests-property-greeble-types: add property test asserting `generate()` succeeds for every (`GreebleType` × seed) pair via `--greeble-style` plumbing
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each `GreebleType` enum member × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending greeble-type + seed; CHANGELOG bullet
      notes: shipped 2026-04-29; chose `pytest.mark.parametrize` over Hypothesis (same rationale as the hull/engine companions in `3dbeea9` and the palette one in `3321b88` — deterministic, faster, parametrize IDs self-name failures as `[seed-greeble_type]`) with `ids=lambda t: t.value` so failure node IDs read e.g. `[7-circuit_board]` rather than the noisy `<GreebleType.CIRCUIT_BOARD: 'circuit_board'>` repr; `GreebleType` has 11 members today (TURRET, DISH, VENT, ANTENNA, PANEL_LINE, SENSOR_POD, CIRCUIT_BOARD, BATTLE_DAMAGE, PIPE_CLUSTER, ORGANIC_GROWTH, NANO_MESH) × 3 seeds = 33 test nodes; mirrors how the `--greeble-style TYPE` CLI flag plumbs into `generate()` (`cli.py:687-691` builds `[GreebleType(args.greeble_style)]` and forwards as `greeble_types=` to `generate()` at `generator.py:133`) so the per-type CLI plumbing is exercised end-to-end per enum member; `greeble_density=0.3` is set on `ShapeParams` so the scatter actually fires and the restricted-type list has a chance to matter (a zero-density run would yield identical grids regardless of `greeble_types=`); test asserts `litematic_path.exists()`, `os.path.getsize(...) > 0`, `block_count > 0` with explicit `pytest.fail(f"...{greeble_type.value}...{seed}...")` messages on the missing/zero-byte paths so failures are unambiguous in either the node ID or the message; 33 new test nodes run in ~0.7 s on the dev box at `length=16/width=8/height=6` (well under the 30 s acceptance budget); complements the Hypothesis-based shape tests (which sample `greeble_density` but never restrict to a single `GreebleType`) and the existing hull/engine parametrize tests, so a regression in any single greeble builder now surfaces deterministically as a self-named failure node; full `pytest -q` (1971 tests) + `ruff check .` both green

- [x] feat-docs-quickstart: add `docs/quickstart.md` — 5-minute getting-started guide
      scope: `docs/quickstart.md` (new), one-line link from README near top
      accept: file walks through install → first ship → palette swap → preset use → web UI launch in ≤80 lines; sourced from existing CLI flags and README content; CHANGELOG bullet
      notes: shipped 2026-04-29; new `docs/quickstart.md` is a 55-line (excluding code-fence delimiters; 65 total) walkthrough with five numbered steps in the order specified by the brief (install → first ship → palette swap → preset use → web UI launch) plus a short "Next steps" footer; every command is copy-pasteable and sourced from `docs/cli.md` flag declarations (so the doc and the CLI stay in lockstep) — `spaceship-generator --seed 42` for the first ship, `--palette NAME` / `--palette random` for the palette swap (links to `docs/palettes.md`), `--preset NAME` for the preset (links to `docs/presets.md`), `flask --app spaceship_generator.web.app run` for the web UI (links to `docs/web_ui.md`); install snippet copied verbatim from the README's existing `## Install` section so the two stay in sync; cross-link header at the top points to `cli.md`/`palettes.md`/`presets.md`/`web_ui.md` so users land in the right reference doc one click away from any step; one-line README link added directly under the existing intro paragraph and above the `## Pipeline` heading (no restructure — the new line reads "New here? See [docs/quickstart.md](docs/quickstart.md) for a 5-minute getting-started guide.") so first-time visitors hit the guide before they scroll past the dense Features/Install/CLI sections; full `pytest -q` (1971 tests) + `ruff check .` both green (docs-only change, but run for safety per the brief)

- [x] feat-docs-presets: add `docs/presets.md` catalog listing every preset with one-line description
      scope: `docs/presets.md` (new), one-line link from README
      accept: file lists every preset shipped under `presets/` (or wherever the YAML lives) in alphabetical order with one-line description sourced from yaml; CHANGELOG bullet; one-line README link
      notes: shipped 2026-04-29; presets live in Python (`SHIP_PRESETS` dict in `src/spaceship_generator/presets.py`), not YAML — the task brief assumed a `presets/` YAML directory parallel to `palettes/` but the actual loader is the in-source dict (`--list-presets` enumerates `list_presets()` which sorts `SHIP_PRESETS.keys()`); rewrote the existing partial doc (which only enumerated 6 of the 9 archetypes in a hand-curated table and predated the per-preset `description:` field that landed alongside the 3 newer presets `scout`, `battlecruiser`, `capital_carrier`) into a full 9-row catalog (`battlecruiser`, `capital_carrier`, `corvette`, `dropship`, `freighter_heavy`, `gunship`, `interceptor`, `science_vessel`, `scout`) sourced directly from each preset's `description:` field so the doc, the `--list-presets` CLI output, and `SHIP_PRESETS` stay in lockstep without manual translation; 2-column Markdown table style matches `docs/palettes.md` (commit `36da455`) exactly; companion sections preserved verbatim where possible (Python usage with `apply_preset(...)` / `list_presets()`, raw-table inspection via `SHIP_PRESETS` + `PRESET_KEYS`, "Adding a new preset" checklist updated to require a `description:` line and alphabetical-by-name placement); the older `## Scope and roadmap` section was dropped because the CLI integration it deferred has long-since shipped (`--preset` flag is documented in `docs/cli.md`); one-line link added to the existing `--preset` bullet in README's `### Key flags` (no restructure — the bullet now reads "...; run `--list-presets` to list all (see [docs/presets.md](docs/presets.md) for the full catalog)"); full `pytest -q` + `ruff check .` both green (no code changes — docs-only)

- [x] feat-cli-stats-json: add `--stats-json` flag — machine-readable variant of `--stats`
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--stats-json` prints a single JSON document (block counts, dims, role tallies) to stdout instead of human-formatted; exits 0 after writing; mutually compatible with `--quiet` (output-json carve-out behavior); tested; CHANGELOG bullet
      notes: shipped 2026-04-29; new `--stats-json` argparse flag emits a single JSON document via `_print_stats_json(result)`; refactored `_print_stats` to consume a shared `_compute_stats(result)` helper that returns a dict with `seed`, `palette`, `shape` (`[W, H, L]`), `total_blocks`, `density`, `total_cells`, and a `roles` array of `{role, count, pct}` entries (sorted by count desc, EMPTY skipped, unknown role ids surface as `ROLE_<int>`) so the human and JSON paths can never drift on the underlying numbers; mutually exclusive with `--stats` (rejected via `parser.error` → exit 2 + `mutually exclusive` stderr message, mirroring the `--no-greebles` vs `--greeble-density` pattern from `e33a3f2`); deliberately NOT silenced by `--quiet` so scripts can pair `--quiet --stats-json` (same carve-out as `--output-json`, documented in the help text); wired into both the fleet branch and the seeds-loop branch so bulk runs (`--seeds` / `--repeat` / `--fleet-count`) emit one JSON document per ship newline-delimited (NDJSON), parallelling `--output-json`; three new tests in `tests/test_cli.py` cover (a) happy path `--stats-json --seed 1001` produces exactly one parseable JSON document with the required keys + sorted-desc role counts + summed counts equal to `total_blocks` + density in `(0, 1)`, (b) `--quiet --stats-json` still emits exactly one JSON line (no `Role distribution:` header, no `Seed:` success lines), and (c) `--stats --stats-json` errors non-zero with both flag names and `mutually exclusive` in stderr; full `pytest -q` (1914 tests) + `ruff check .` both green

- [x] feat-tests-property-shape-styles: add property test asserting `generate()` succeeds for every (HullStyle × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each `HullStyle` enum member × small seed grid (`[0, 1, 7]` is fine — 3 seeds keeps runtime down); assert `generate()` exits cleanly + writes a non-empty `.litematic`; failure message names the offending hull-style + seed; CHANGELOG bullet
      notes: shipped 2026-04-29; chose `pytest.mark.parametrize` over Hypothesis (same rationale as the palette companion in `3321b88` — deterministic, faster, parametrize IDs self-name failures as `[seed-style]`) with `ids=lambda s: s.value` so failure node IDs read e.g. `[7-blocky_freighter]` rather than the noisy `<HullStyle.BLOCKY_FREIGHTER: 'blocky_freighter'>` repr; HullStyle has 10 members today (ARROW, SAUCER, WHALE, DAGGER, BLOCKY_FREIGHTER, ORGANIC_BIO, HEXAGONAL_LATTICE, ASYMMETRIC_SCAVENGER, MODULAR_BLOCK, SLEEK_RACING) × 3 seeds = 30 hull test nodes; companion `test_property_engine_style_seed_grid_generates_non_empty_litematic` covers every `EngineStyle` member (9) since `EngineStyle` is the only other shape-style enum exposed directly on `generate()`'s public signature (`engine_style=`) — 27 more nodes for 57 total; `WingStyle` is intentionally not duplicated here since it flows only via `ShapeParams` and is already exercised by the Hypothesis `test_property_all_style_combos_symmetric` test plus the `StructureStyle × HullStyle` cross-product test (`test_property_structure_x_hull_cross_product_no_crash`); 57 new test nodes run in ~1.2 s on the dev box at `length=16/width=8/height=6` (well under the 30 s acceptance budget); test asserts `litematic_path.exists()`, `os.path.getsize(...) > 0`, `block_count > 0` with explicit `pytest.fail(f"...{style}...{seed}...")` messages on the missing/zero-byte paths so failures are unambiguous in either the node ID or the message; complements the Hypothesis-based `test_property_hull_x_engine_matrix_produces_valid_grid` which samples 20 random pairs and may legitimately skip enum members on any given run, so a regression in any single style now surfaces deterministically as a self-named failure node

- [x] feat-bench-palette: add `scripts/bench_palette.py` per-palette generate() time micro-bench
      scope: `scripts/bench_palette.py` (new), `tests/test_bench_smoke.py` (extend with N=2 smoke)
      accept: script iterates all palettes (or a `--limit` subset) running N `generate()` calls each, prints fixed-width palette × mean/p95 ms table, exits 0; smoke runs --limit 2 --iterations 2; CHANGELOG bullet
      notes: shipped 2026-04-29; argparse mirrors `bench_full_pipeline.py` / `bench_mem.py` (`--iterations` default 3, `--limit` default 0 = all, `--seed` default 0); palettes discovered dynamically via `spaceship_generator.palette.list_palettes()` (same enumeration `tests/test_palette_lint.py::test_all_shipped_palettes_have_zero_errors` + `tests/test_properties.py::test_property_palette_seed_grid_generates_non_empty_litematic` use, so adding a YAML auto-widens the matrix); fixed-width table is `palette | mean_ms | p95_ms` with column width auto-fit to the longest palette name (16 chars today, future-proofs for longer names) + a TOTAL summary row that aggregates *per-iter* samples across all palettes (not the row-level means) so a regression in any single palette also surfaces in the catalog-wide p95; one untimed warm-up iteration on the first palette before the timed loop, mirroring `bench_full_pipeline` / `bench_mem`; numpy + stdlib only (np.percentile for p95, np.float64 buffer per palette — no pandas/matplotlib); writes each iteration's `.litematic` into a `tempfile.TemporaryDirectory` so nothing leaks; `tests/test_bench_smoke.py::test_bench_palette_runs_with_two_palettes_two_iterations` runs `subprocess.run([..., bench_palette.py, --limit 2, --iterations 2, --seed 0])` and asserts exit 0 + presence of `palette`/`mean_ms`/`p95_ms`/`TOTAL` in stdout; complements `bench_full_pipeline.py` (one palette deep) by surfacing per-palette cost variance and giving a catalog-wide p95 baseline that future palette PRs can be benched against; full `pytest -q` (1854 tests) + `ruff check .` both green

- [x] feat-cli-no-weapons: add `--no-weapons` shortcut equivalent to `--weapon-count 0`, mutually exclusive with `--weapon-count`
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--no-weapons` resolves to `weapon_count=0` end-to-end; passing both `--no-weapons` and `--weapon-count` errors with non-zero exit; tested; CHANGELOG bullet
      notes: shipped 2026-04-29; parallels the existing `--no-greebles` / `--greeble-density` mutual-exclusion pattern from `e33a3f2`; because `--weapon-count` defaults to `0`, the mutex check uses the `_explicit_flags(argv)` set (mirrors how `--from-manifest` distinguishes "user typed `--seed`" from "argparse filled in the default") rather than a `None`-sentinel comparison; downstream plumbing reads only `args.weapon_count` so no special-case threading is needed; three new tests in `tests/test_cli.py` cover (a) end-to-end resolution by asserting `--no-weapons` produces the same `--output-json` block count as `--weapon-count 0` while a `--weapon-count 5` run produces strictly more (sanity-checks that weapon scatter would have fired absent the shortcut), (b) the mutual-exclusion exit-non-zero + stderr message, and (c) the help text mentions both `--no-weapons` and `--weapon-count`

- [x] feat-docs-web-ui: add `docs/web_ui.md` covering Flask blueprint endpoints + browser UX
      scope: `docs/web_ui.md` (new), one-line link from README
      accept: file documents every `/api/*` route + the HTML pages served by `web/blueprints/`; sourced from `_OPENAPI_PATHS`; CHANGELOG bullet; one-line README link
      notes: shipped 2026-04-29; `docs/web_ui.md` is a 4-section reference (HTML pages / auxiliary binary+JSON routes / `/api/*` JSON API / rate limiting + env tunables) mirroring the table style of `docs/cli.md` and `docs/palettes.md` for consistency; HTML pages enumerated by grepping `render_template(` in `src/spaceship_generator/web/blueprints/ship.py` (`/`, `POST /generate`, `/result/<gen_id>`); auxiliary routes (PNG previews + JSON voxels + block-texture passthrough + `.litematic` download + zipped fleet download) sourced from `ship.py` + `static_ext.py`; `/api/*` table sourced directly from the canonical `_OPENAPI_PATHS` dict in `ship.py` (every key, method, summary, params, and 200 response shape) so the doc and the `GET /api/spec` document stay in lockstep; rate-limited endpoints (`POST /generate`, `POST /api/generate`, `POST /api/batch`, `GET /preview-lite`, `GET /download-fleet`) called out explicitly with their `SHIPFORGE_RATE_LIMIT` / `SHIPFORGE_RATE_WINDOW` / `SHIPFORGE_CSP` env tunables; one-line link added under the existing `## Usage — Web UI` section of `README.md` (no restructure); complements `docs/cli.md` flag reference and `docs/palettes.md` catalog so users no longer have to grep blueprints or read the OpenAPI document by hand

- [x] feat-cli-stdout-litematic: support `--output -` to write `.litematic` bytes to stdout instead of a file
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--output - --seed 1 > ship.litematic` produces a valid litematic via pipe; exits 0; mutually exclusive with `--repeat`/`--fleet-count` (single-ship only); CHANGELOG bullet
      notes: shipped 2026-04-29; new `--output PATH` argparse flag (`metavar=PATH`) — when set to `-` we generate one ship into a `tempfile.TemporaryDirectory`, read the resulting `.litematic` bytes, and emit them on `sys.stdout.buffer.write(...)` (NOT `print`, so the binary payload survives round-trip); single-ship-only enforced via `parser.error` (exit 2) when paired with `--repeat > 1`, `--fleet-count > 1`, or `--seeds`; success-path informational stdout lines (Seed/Palette/Wrote/...) are unconditionally suppressed in this mode so the binary stream isn't corrupted (regardless of `--quiet`); errors and warnings still flow through stderr; three new tests in `tests/test_cli.py` cover happy path (non-empty bytes + gzip-magic `\x1f\x8b` prefix verifying litematic = NBT-in-gzip, captured via pytest's `capfdbinary`) and the two conflict paths; convention is hyphen-as-stdout (`spaceship-generator --output - | mc-server-tool import-schematic`)

- [x] feat-tests-property-palette-stability: add property test asserting `generate()` succeeds for every (palette × small-seed-grid) pair
      scope: `tests/test_properties.py` (extend or new test)
      accept: Hypothesis test (or simple parametrize) iterates every palette with 5-10 distinct seeds, asserts `generate()` exits cleanly + writes a non-empty `.litematic`; failures should name the offending palette + seed; CHANGELOG bullet
      notes: shipped 2026-04-29; chose `pytest.mark.parametrize` over Hypothesis (deterministic, faster, parametrize IDs self-name failures as `[palette-seed]`); palette list discovered dynamically via `palettes_dir().glob('*.yaml')` (mirrors `tests/test_palette_lint.py::test_all_shipped_palettes_have_zero_errors` style — no hard-coded names, so adding a YAML auto-widens the matrix); seed grid `[0, 1, 7, 42, 99]` (5 seeds) × 51 palettes = 255 generate() calls in ~2.2 s on the dev box at `length=16/width=8/height=6` (well under the 60 s budget — no `slow` marker needed, and pyproject.toml only declares `ui` anyway); test asserts `litematic_path.exists()`, `os.path.getsize(...) > 0`, `block_count > 0` with explicit `pytest.fail(f"...palette={...} seed={...}")` messages on the missing/zero-byte paths so failures are unambiguous in either the node ID or the message; fills the gap that would have caught `bug-weapon-count-decreases-cells` style palette-driven regressions one tick earlier (current Hypothesis tests focus on shape params + weapon_count, not palette coverage)

- [x] feat-palettes-biome-pack-2026-04-28b: add 2 more biome palettes (windswept_hills, ice_spikes)
      scope: `palettes/windswept_hills.yaml`, `palettes/ice_spikes.yaml`, `docs/palettes.md`, `docs/CHANGELOG.md`
      accept: both pass `test_palette_lint`; loadable via `--palette NAME`; CHANGELOG bullet
      notes: shipped 2026-04-29; windswept_hills = stone hull / gravel HULL_DARK accent / spruce-plank wings / lantern engine glow / andesite greebles (1.18 mountains windswept variant); ice_spikes = packed-ice hull / blue-ice HULL_DARK accent / snow-block wings / sea-lantern engine glow / prismarine-brick engines / dripstone-block greebles (rare cold biome); both pass strict lint (WINDOW luminance, HULL/HULL_DARK contrast, ENGINE_GLOW emissive); rounds palette count to 51; catalog rows added to `docs/palettes.md` in alphabetical order

- [x] feat-bench-mem: add `scripts/bench_mem.py` peak-memory micro-bench for `generate()`
      scope: `scripts/bench_mem.py` (new), `tests/test_bench_smoke.py` (extend with N=2 smoke)
      accept: script runs N iterations of `generate()`, reports peak RSS in MB (via `tracemalloc.peak`) per iteration + mean/p95; exits 0; smoke test runs N=2; CHANGELOG bullet
      notes: shipped 2026-04-29 (this commit); `tracemalloc` only (stdlib) — no `psutil`/`pympler`; mirrors `bench_full_pipeline.py` schema (argparse `--iterations N` default 5, `--seed`, `--palette`; fixed-width `pipeline / TOTAL` table); reports mean/p95/max MB (peak Python heap, not RSS — sufficient to spot regressions cross-OS); `tracemalloc.reset_peak()` between iterations isolates per-iter peak; `tests/test_bench_smoke.py::test_bench_mem_runs_with_two_iterations` smoke test added; foundation for `shapes-A`..`shapes-D` mem-budget work

- [x] feat-cli-version: add `--version` / `-V` flag printing package version + exits 0
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--version` prints `spaceship_generator <ver>`, exits 0; `-V` short alias works; tested
      notes: tiny conventional unix flag; version source = `spaceship_generator.__version__` (matches `/api/health` and OpenAPI doc-builder pattern); useful for bug reports / CI

- [x] feat-api-palette-detail: add `GET /api/palettes/<name>` single-palette detail endpoint
      scope: `src/spaceship_generator/web/blueprints/ship.py` (extend), `tests/test_api.py`, `_OPENAPI_COMPONENTS` for spec
      accept: route returns 200 with full palette doc (name, roles=block-id-per-role, preview_colors); 404 for unknown name; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: route + OpenAPI `PaletteDetail` schema + first round of tests already shipped earlier in `ea80439` (the originally-planned scope); this cycle hardened the test coverage to exactly match the acceptance criteria — `test_api_palette_detail_ok` and `test_api_palette_detail_not_found` now assert `Content-Type` starts with `application/json`, and a new `test_api_palette_detail_listed_in_openapi_spec` pins `/api/palettes/{name}` (with `200` + `404` responses) directly in `/api/spec`'s `paths` dict so a refactor that drops the entry fails by name rather than via the generic `test_api_spec_lists_every_route` diff; response body returns `{name, roles, preview_colors}` (the `Palette` dataclass surface — no top-level `description` field exists on the dataclass, only in the YAML, so it's deliberately not exposed)

- [x] feat-docs-cli-reference: add `docs/cli.md` flag-reference catalog
      scope: `docs/cli.md` (new), one-line link from README
      accept: file lists every CLI flag with name, type, default, one-line description, in argparse declaration order; auto-extractable from `cli.py` parser is fine but a hand-written doc is also acceptable; CHANGELOG bullet
      notes: shipped this cycle; hand-written 4-column Markdown table (Flag | Type/Value | Default | Description) grouped into thematic sections (Identity, Seed, Palette, Style discovery, Presets, Shape params, Texture, Weapons, Repeat & fleet, Dry-run, Output, Preview, Verbosity, Diagnostics) following `add_argument` declaration order in `src/spaceship_generator/cli.py::build_parser`; one-line link added under existing `### Key flags` subsection in README (no restructure); style mirrors `docs/palettes.md`

- [x] feat-api-shape-styles: add `GET /api/shape-styles` mirror of CLI `--list-shape-styles`
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components
      accept: route returns `{hull_styles:[...], engine_styles:[...], wing_styles:[...]}` JSON; OpenAPI enumerates it; spec-validate test green; CHANGELOG bullet
      notes: shipped this cycle; narrower JSON sibling of `/api/styles` returning only the three core shape enums in enum-declaration order via the same `[s.value for s in HullStyle]` serialization used by `/api/styles` (asserted byte-identical for shared keys via `test_api_shape_styles_matches_styles_subset`); new `ShapeStyles` schema in `_OPENAPI_COMPONENTS` and `/api/shape-styles` path in `_OPENAPI_PATHS` so `/api/spec` enumerates it and `tests/test_api_spec_validate.py` stays green; three new tests in `tests/test_api.py` cover 200 + content-type + non-empty arrays, drift-vs-`/api/styles`, and presence in `/api/spec`

- [x] feat-bench-full-pipeline: add `scripts/bench_full_pipeline.py` end-to-end generate() micro-bench
      scope: `scripts/bench_full_pipeline.py` (new), `tests/test_bench_smoke.py` (extend with N=2 smoke)
      accept: script runs N iterations of `generate()` (full pipeline including .litematic write to tmpdir), prints mean/p95/total ms, exits 0; smoke test runs N=2 to guard against import/argparse regressions; CHANGELOG bullet
      notes: shipped 2026-04-28 in `83521c4`; mirrors `bench_shape.py` schema (argparse, fixed-width table); single `pipeline` row + `TOTAL`; `tests/test_bench_smoke.py::test_bench_full_pipeline_runs_with_two_iterations` smoke test added

- [x] feat-api-health: add `GET /api/health` endpoint returning `{status, version, uptime_s}`
      scope: `src/spaceship_generator/web/blueprints/` (extend an existing blueprint or add new), `tests/test_api*.py`
      accept: route returns 200 with `application/json`; body has `status:"ok"`, `version` from package metadata, `uptime_s` integer; test asserts shape; CHANGELOG bullet
      notes: shipped 2026-04-28 in `d3a80cb`; existing `api_health` view extended additively (kept legacy `palette_count`/`preset_count` keys); `_START_MONOTONIC` captured at blueprint import; OpenAPI Health schema in `_OPENAPI_COMPONENTS` updated to declare `uptime_s`; `tests/test_api.py::test_api_health_ok` + `test_api_health_no_store_cache_control` cover the contract

- [x] feat-cli-quiet: add `--quiet` flag suppressing all stdout on success (errors still go to stderr)
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--quiet` on a successful generate produces zero stdout bytes; exits 0; errors still print to stderr; mutually compatible with all other flags; CHANGELOG bullet
      notes: shipped 2026-04-28 in `deae5e7`; `_emit(args, msg)` helper funnels every success-path emitter; silences `--list-*`, `--dry-run`, `--stats`, `--block-summary`, `--palette-info`; `--output-json` deliberately exempt to keep four pre-existing `--quiet --output-json` tests green (documented in help text); 3 new tests cover empty-stdout, regression guard, `-q` short alias + argparse-error path

- [x] feat-docs-palette-catalog: add `docs/palettes.md` listing all palettes with one-line descriptions
      scope: `docs/palettes.md` (new file)
      accept: file lists every palette in `palettes/` (currently 46) with one-line description sourced from yaml comment or theme; alphabetical order; CHANGELOG bullet; one-line link from README
      notes: shipped 2026-04-28 in `36da455`; actual palette count is 49 (todo's "46" was stale); 2-column Markdown table sourced from each yaml's `description:` field; one-line link added to README's `Palettes` section; references `docs/palette_authoring.md` (no `CONTRIBUTING.md` exists in repo)

- [x] feat-palettes-biome-pack-2026-04-28: add 2 new biome palettes (cherry_grove, sparse_jungle)
      scope: `palettes/cherry_grove.yaml`, `palettes/sparse_jungle.yaml`
      accept: both pass `test_palette_lint`; hull/wing/glow blocks valid; loadable via `--palette NAME`; CHANGELOG bullet
      notes: shipped 2026-04-28 in `8fde3c8`; cherry_grove = cherry-planks hull / pink-petals wings / shroomlight glow / lantern lights; sparse_jungle = jungle-log hull / jungle-leaves wings / ochre-froglight glow / lantern lights; both pass strict lint (WINDOW luminance, HULL/HULL_DARK contrast, ENGINE_GLOW emissive)

- [x] bug-weapon-count-decreases-cells-2026-04-27: weapon writer can REMOVE LIGHT/HULL_DARK cells at certain seeds (Hypothesis: seed=93 weapon_count=4 → variant has 11 vs baseline 12)
      scope: `src/spaceship_generator/generator.py` weapon write loop; `tests/test_generator.py` regression test
      accept: invariant `var_weapon_cells >= base_weapon_cells` holds for all (seed, weapon_count) — shipped as fix path (a), weapon writer now truly additive end-to-end
      notes: shipped 2026-04-28 in `921e0b1`; root cause was weapons stamping legitimately-EMPTY cells directly above the centerline nose-tip, which then caused `texture._paint_nose_tip_light` to bail (top cell was a `_PROTECTED_ROLES` member) and silently drop the nose-tip LIGHT; fix added a `_nose_tip_anchor_cells()` helper + shadow-check in the weapon write loop; new regression test `test_generate_weapon_writer_does_not_shadow_nose_tip_light` pinned to seed=93 wc=4

- [x] feat-api-spec-schema-validate: add CI test that validates `/api/spec` response against an OpenAPI 3.0 schema
      scope: `tests/test_api.py` (or new `tests/test_api_spec_validate.py`), `requirements-dev.txt` if a validator is added
      accept: test fetches `/api/spec`, validates with `openapi-schema-validator` or `jsonschema` against OAS 3.0 meta-schema; passes; CHANGELOG bullet
      notes: shipped 2026-04-27 (this commit); uses `jsonschema.Draft4Validator` against the official OAS 3.0 meta-schema (2021-09-28 release) vendored at `tests/fixtures/openapi-3.0-schema.json` so the test runs offline; `pytest.importorskip("jsonschema")` keeps the suite green if the dep is missing; `requirements-dev.txt` declares `jsonschema>=4.0`

- [x] feat-bench-shape-pipeline: add `scripts/bench_shape.py` micro-bench timing each shape stage (hull/cockpit/wings/engines/greebles)
      scope: `scripts/bench_shape.py` (new), no src changes required
      accept: script runs N iterations, prints per-stage mean/p95 ms, exits 0 on dev box; `tests/test_bench_smoke.py` runs N=2 to ensure script is syntactically healthy
      notes: shipped 2026-04-27 in `713e374`; numpy + stdlib only (no matplotlib/pandas); wraps each public stage helper in `time.perf_counter()` and prints a single mean/p95/total table; assembly stage covers the `_enforce_x_symmetry` -> `_connect_floaters` -> `_enforce_x_symmetry` post-pass; foundation for `shapes-A`..`shapes-E` perf work

- [x] feat-cli-list-shape-styles: add `--list-shape-styles` flag enumerating HullStyle/EngineStyle/WingStyle in one shot
      scope: `src/spaceship_generator/cli/*.py`, `tests/test_cli.py`
      accept: `--list-shape-styles` prints all three style enums grouped, exits 0; deterministic order; test asserts membership; CHANGELOG bullet
      notes: shipped 2026-04-27 (this commit); emits `Hull styles:` / `Engine styles:` / `Wing styles:` sections in enum-declaration order, indent-by-two members; narrower sibling of `--list-styles` (skips cockpit + weapon types); existing `--list-styles` output unchanged

- [x] shapes-E-noise: procedural-noise hull distortion (asteroid-like / battle-damaged / organic irregularity)
      scope: `shape/hull.py` post-pass, `texture.py` (optional rivet/panel interplay), CLI flag
      accept: `--hull-noise AMPLITUDE` toggles 3D-noise displacement on the hull membrane; deterministic per seed; tests; gallery sample
      notes: shipped 2026-04-27 (this commit); deterministic hash-noise post-pass with ±2 cell silhouette clamp; amplitude=0 byte-identical to legacy; gallery sample still pending

- [x] feat-palettes-biome-pack-2026-04-27: add two new biome palettes (soul_sand_valley, savanna_acacia)
      scope: `palettes/*.yaml`, no test changes required
      accept: two new YAML palettes pass `test_palette_lint`, hull/wing/glow blocks valid; loadable via `--palette NAME`; CHANGELOG bullet
      notes: shipped 2026-04-27 in `813c768`; fills remaining vanilla-biome gaps (soul-sand-valley nether + savanna acacia)

- [x] shapes-B-hull-blend: blend two hull profiles along Z (e.g. front=arrow + rear=saucer)
      scope: `structure_styles.py` (blend helper), `shape/hull.py`, `shape/core.py` (params), CLI
      accept: `--hull-style-front X --hull-style-rear Y` flag, deterministic per seed, smooth crossover region; tests cover blend boundaries; gallery example
      notes: shipped 2026-04-26 in `efbf3b3`; cosine-weighted 25% midband; partial pair falls back to single-style; gallery sample still pending

- [x] feat-palettes-biome-pack-2026-04-26: add three new biome palettes (lush_caves, mangrove_swamp, pale_garden)
      scope: `palettes/*.yaml`, `tests/test_palette.py` or `tests/test_palette_lint.py` (count update only)
      accept: three new YAML palettes pass `test_palette_lint`, hull/wing/glow blocks valid; palette count test updated; loadable via `--palette NAME`
      notes: shipped 2026-04-26 in `277416f`; no count-test update needed (dynamic enumeration)

- [x] feat-api-openapi-spec: add `GET /api/spec` endpoint returning OpenAPI 3.0 JSON schema
      scope: `src/spaceship_generator/web/` (new endpoint), `tests/test_api.py` or `tests/test_web.py`
      accept: route `/api/spec` returns `application/json` with valid OpenAPI 3.0 doc enumerating all current endpoints; test asserts shape and content-type
      notes: shipped 2026-04-26 in `4d88bc9`; 14 paths enumerated; drift-protection test walks `app.url_map`

- [x] feat-docs-shape-pipeline: write architecture doc for the shape pipeline as foundation for shapes-A..E
      scope: `docs/architecture.md` only (extend existing file; do not create a new one)
      accept: new section "Shape pipeline" describes `shape/core.py`, `shape/hull.py`, `shape/assembly.py`, `shape/cockpit.py`, `shape/wings.py`, `shape/engines.py`, `shape/greebles.py` with one paragraph per module + a Mermaid or ASCII flow diagram of the build order; CHANGELOG bullet
      notes: shipped 2026-04-26 in `718275f`; Mermaid diagram + per-module subsections
