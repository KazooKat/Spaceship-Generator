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

- [ ] feat-tests-property-greeble-style-x-density-grid: add (greeble_style × greeble_density × seed) cross-axis property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 greeble_style × 3 density × 3 seed = 27 nodes); pure stability check; CHANGELOG bullet
      notes: extends cross-axis property test pack with greeble_style × density pair

- [ ] feat-docs-recipes-extension-5: extend `docs/recipes.md` with 4 new task-oriented recipes
      scope: `docs/recipes.md` (extend, not restructure)
      accept: 4 new recipes cover (composing palette_lint --json with --all in CI for diff-only fail), (cross-axis property test scaffolding template), (combining --meta-json + --output-json in pipelines), (mining the architecture cross-link table for tooling); ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [ ] feat-docs-troubleshooting-extension-4: extend `docs/troubleshooting.md` with 4-6 new entries
      scope: `docs/troubleshooting.md` (extend, not restructure)
      accept: 4-6 new rows covering (palette pack name collision), (cross-axis test parametrize id collisions), (palette_lint --json + jq quoting on Windows PowerShell), (architecture cross-link table drift), (greeble_density extreme values); ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit

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

- [x] feat-palettes-biome-pack-2026-05-12a: add 2 new biome palettes (obsidian_forge, prismatic_reef)
      scope: `palettes/obsidian_forge.yaml`, `palettes/prismatic_reef.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-glossary-extension-4: extend `docs/glossary.md` with 3-4 new entries
      scope: `docs/glossary.md` (extend, not restructure)
      accept: new entries for biome-palette-pack, cross-axis-test (extension), palette_lint-json-schema, cross-link-footer; alphabetized; ≤25 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-docs-faq-extension-4: extend `docs/faq.md` with 4 new Q&As covering recently-shipped surfaces
      scope: `docs/faq.md` (extend, not restructure)
      accept: 4 new Q&As cover (palette × greeble_density cross-axis test rationale), (arcane_library/mistwood_grove biome use-cases), (palette_lint --json schema fields), (cross-link footer in architecture.md); ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-palettes-biome-pack-2026-05-08e: add arcane_library, mistwood_grove biome palettes
      scope: `palettes/arcane_library.yaml`, `palettes/mistwood_grove.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-tests-property-palette-x-greeble-density-grid: add (palette × greeble_density × seed) cross-axis property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 palette × 3 density × 3 seed = 27 nodes); CHANGELOG bullet
      notes: extends cross-axis property test pack with palette × numeric-axis pair

- [x] feat-docs-faq-extension-3: extend `docs/faq.md` with 4 new Q&As covering recently-shipped surfaces
      scope: `docs/faq.md` (extend, not restructure)
      accept: 4 new Q&As cover (when to use --meta-json vs individual --list-*-json), (palette_lint --json for CI), (Texture pipeline at-a-glance), (hull × wing cross-axis test); ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-docs-troubleshooting-extension-3: extend `docs/troubleshooting.md` with 4-6 new entries
      scope: `docs/troubleshooting.md` (extend, not restructure)
      accept: 4-6 new rows covering --meta-json mutex errors, palette_lint --json schema mismatch, Texture pipeline param drift, --output-json + jq parse errors, fleet seed reproducibility; ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-docs-recipes-extension-4: extend `docs/recipes.md` with 4 new task-oriented recipes
      scope: `docs/recipes.md` (extend, not restructure)
      accept: 4 new recipes cover (palette_lint.py --json --all for CI gate scripting), (--meta-json piped to jq for tooling discovery), (Texture-pipeline tunables via --window-period / --stripe-period), (cross-axis property test debugging via -k); ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-docs-architecture-cross-link-footer: add cross-link footer table at end of `docs/architecture.md`
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new "## Cross-link footer" or similar appended after `## Related documentation` (or extending it) with a 2-column table mapping each per-component / pipeline-level section to its CLI flag(s) + web API endpoint(s); ≤40 added lines; CHANGELOG bullet
      notes: pure-docs unit; tightens the "where is X documented" navigation

- [x] feat-docs-architecture-texture: extend `docs/architecture.md` with a Texture pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new H2 "## Texture pipeline" between `## Fleet pipeline` and `## Related documentation` describing `texture.py` (role refinement: WINDOW → COCKPIT_GLASS / WINDOW dispatch, GLOW emissive selection, light placement); cross-link to `docs/cli.md` and `docs/architecture.md#shape-pipeline`; ≤80 added lines; CHANGELOG bullet
      notes: covers texture.py — last major module without per-component section; consider whether texture is per-component (it operates on roles not styles) or pipeline-level

- [x] feat-docs-glossary-extension-3: extend `docs/glossary.md` with 3-4 new entries
      scope: `docs/glossary.md` (extend, not restructure)
      accept: new entries for `--meta-json`, hull×wing cross-axis test, Reading the output (bench), output-formats Consumer examples; alphabetized; ≤25 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-scripts-palette-lint-json: add `--json` flag to `scripts/palette_lint.py` emitting structured lint result
      scope: `scripts/palette_lint.py`, `tests/test_palette_lint.py` (extend)
      accept: `palette_lint.py --json palettes/X.yaml` emits `{"palette":"X","ok":true|false,"errors":[...],"warnings":[...]}` to stdout; `--all --json` emits a JSON array of these objects; exit codes preserved (0 clean / 1 dirty); smoke tests for both single and `--all` modes; CHANGELOG bullet
      notes: tooling-friendly companion to existing fixed-width output

- [x] feat-docs-recipes-extension-3: extend `docs/recipes.md` with 4 new task-oriented recipes
      scope: `docs/recipes.md` (extend, not restructure)
      accept: 4 new recipes cover (using `--meta-json` in tooling), (running --fleet-count for batch ships), (consuming --output-json with jq), (palette_lint --json --all for CI gates); ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-palettes-biome-pack-2026-05-08d: add abyssal_trench, sunset_horizon biome palettes
      scope: `palettes/abyssal_trench.yaml`, `palettes/sunset_horizon.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-cli-meta-json: document `--meta-json` flag in `docs/cli.md`
      scope: `docs/cli.md` (extend, not restructure)
      accept: new row in the existing machine-readable list-flag block describing `--meta-json`'s combined payload (cross-link to `/api/meta`); ≤30 added lines; CHANGELOG bullet
      notes: pure-docs follow-up to feat-cli-meta-json

- [x] feat-palettes-biome-pack-2026-05-08c: add ember_forge, twilight_glade biome palettes
      scope: `palettes/ember_forge.yaml`, `palettes/twilight_glade.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-tests-property-hull-x-wing-style-grid: add (hull_style × wing_style × seed) cross-axis property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 hull × 3 wing × 3 seed = 27 nodes); CHANGELOG bullet
      notes: complements existing cross-axis pack — fresh hull×wing pair

- [x] feat-cli-meta-json: add `--meta-json` CLI flag emitting combined enum/palette/preset/version JSON document
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--meta-json` emits a single JSON document combining `presets`, `palettes`, `hull_styles`, `engine_styles`, `wing_styles`, `cockpit_styles`, `structure_styles`, `greeble_types`, `weapon_types`, `roles`, `version` keys (matching prior `--list-*-json` siblings); not silenced by `--quiet`; mutually exclusive with `--output` / `--output-json` / `--output-json-schema` / `--config-dump`; tests; CHANGELOG bullet
      notes: CLI mirror of `/api/meta` — single-call discovery for tooling that doesn't want N round-trips through individual `--list-*-json` flags

- [x] feat-docs-output-formats-extension: extend `docs/output-formats.md` with consumer examples
      scope: `docs/output-formats.md` (extend, not restructure)
      accept: new section showing 1-2 consumer snippets — Python reading `.litematic` block_count, jq parsing `--output-json` payload — cross-link to `docs/cli.md`; ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit; concrete copy-paste examples

- [x] feat-docs-quickstart-extension: extend `docs/quickstart.md` with a "Running a fleet" section
      scope: `docs/quickstart.md` (extend, not restructure)
      accept: new section showing `--fleet-count N` invocation, output dir convention, cross-link to `docs/architecture.md#fleet-pipeline` and `docs/cli.md`; ≤40 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-docs-bench-extension: extend `docs/bench.md` with a "Reading the output" examples section
      scope: `docs/bench.md` (extend, not restructure)
      accept: new section with concrete bench_summary fixed-width-table example output, mean_ms / p95_ms / TOTAL semantics; cross-link `docs/bench-ci.md`; ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-docs-glossary-extension-2: extend `docs/glossary.md` with 4-5 new entries
      scope: `docs/glossary.md` (extend, not restructure)
      accept: new entries for `palette_search`, Structure pipeline (anchor link), Common pitfalls (palette_authoring), cross-axis property test, alphabetized correctly; ≤30 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-docs-troubleshooting-extension-2: extend `docs/troubleshooting.md` with 4-6 new entries
      scope: `docs/troubleshooting.md` (extend, not restructure)
      accept: 4-6 new rows cover palette_search no-hits / hits-many, FAQ / glossary navigation gaps, palette_authoring.md common pitfalls cross-link, structure pipeline missing override, fleet output dir collision; ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-tests-property-cockpit-x-engine-style-grid: add (cockpit_style × engine_style × seed) cross-axis property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 cockpit × 3 engine × 3 seed = 27 nodes); CHANGELOG bullet
      notes: complements existing cross-axis pack

- [x] feat-palettes-biome-pack-2026-05-08b: add scarlet_oasis, frostbite_tundra biome palettes
      scope: `palettes/scarlet_oasis.yaml`, `palettes/frostbite_tundra.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-recipes-extension-2: extend `docs/recipes.md` with 4 new task-oriented recipes
      scope: `docs/recipes.md` (extend, not restructure)
      accept: 4 new recipes cover (palette_search by block id), (cockpit×engine cross-axis test running), (Structure pipeline doc navigation), (validating an authored palette via --strict + --all); ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-docs-architecture-fleet: extend `docs/architecture.md` with a Fleet pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new H2 "## Fleet pipeline" section describing `fleet.py` (batch ship-build driver, `build_fleet`/equivalent), how `--fleet-count` plumbs from CLI into per-ship `generate()` calls, deterministic per-ship seed offsetting, output dir conventions; cross-link to `docs/cli.md` (`--fleet-count`); ≤80 added lines; CHANGELOG bullet
      notes: complements per-component pipeline series — fleet is a pipeline-level driver not per-component

- [x] feat-docs-palette-authoring-pitfalls: extend `docs/palette_authoring.md` with a "Common pitfalls" section
      scope: `docs/palette_authoring.md` (extend, not restructure)
      accept: new "Common pitfalls" section with 4-5 entries (e.g. missing namespace prefix, role typos, non-existent block ids, indent/yaml errors, role-coverage gaps); cross-link to `scripts/palette_lint.py --strict`; ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing content

- [x] feat-docs-faq-extension-2: extend `docs/faq.md` with 4 new Q&As covering recently-shipped surfaces
      scope: `docs/faq.md` (extend, not restructure)
      accept: 4 new Q&As cover (palette tooling family — diff/stats/merge/to_json/search), (cross-axis property tests — what they catch), (architecture pipeline doc index — how to navigate), (--config-dump for repro); ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit; do not duplicate existing entries

- [x] feat-docs-architecture-structure: extend `docs/architecture.md` with a Structure pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Structure pipeline" describes `structure_styles.py` (`StructureStyle` + `apply_hull_style` + `default_cockpit_for` + style-specific overrides), the role of `structure_style` in the assembly pipeline; cross-link to `docs/cli.md --list-structure-styles` and `docs/web_ui.md /api/structure-styles`; ≤80 lines; ALSO add `[Structure pipeline](#structure-pipeline)` bullet to the per-component pipeline index near top; CHANGELOG bullet
      notes: completes the per-component pipeline series — existing sections cover Hull, Wing, Greeble, Weapon, Cockpit, Engine but not Structure

- [x] feat-scripts-palette-search: add `scripts/palette_search.py` searching palettes for a given MC block id
      scope: `scripts/palette_search.py` (new), `tests/test_palette_search.py` (new)
      accept: `palette_search.py --block minecraft:stone` prints `palette_name | role` rows for every palette using that block, exits 0 if any hit / 1 if none; `--csv` flag emits same as CSV; smoke test asserts exit 0 on a known-present block; CHANGELOG bullet
      notes: complements `palette_diff.py` / `palette_stats.py` / `palette_merge.py` / `palette_to_json.py` / `palette_lint.py`

- [x] feat-tests-property-engine-x-wing-style-grid: add (engine_style × wing_style × seed) cross-axis property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 engine × 3 wing × 3 seed = 27 nodes); CHANGELOG bullet
      notes: extends cross-axis pattern to engine × wing pair — last untested style cross combo

- [x] feat-palettes-biome-pack-2026-05-08: add meteor_shower, solar_corona biome palettes
      scope: `palettes/meteor_shower.yaml`, `palettes/solar_corona.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-architecture-pipeline-index: add a top-of-doc pipeline index in `docs/architecture.md`
      scope: `docs/architecture.md` (extend)
      accept: 7-bullet anchored index of per-component pipeline sections; ≤25 added lines; CHANGELOG bullet
      notes: pure-docs follow-up; closes navigation gap after the per-component series

- [x] feat-tests-property-palette-x-cockpit-style-grid: add (palette × cockpit_style × seed) property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 × 3 × 3 = 27 nodes) using dynamic palette enumeration; CHANGELOG bullet
      notes: cross-axis variant

- [x] feat-scripts-palette-to-json: add `scripts/palette_to_json.py` converting palette YAML to JSON
      scope: `scripts/palette_to_json.py` (new), `tests/test_palette_to_json.py` (new)
      accept: emits palette as JSON to stdout; `--out PATH` flag; 3 smoke tests; CHANGELOG bullet
      notes: useful for tooling that wants palettes in JSON

- [x] feat-palettes-biome-pack-2026-05-07e: add obsidian_shore, starlight_temple biome palettes
      scope: `palettes/obsidian_shore.yaml`, `palettes/starlight_temple.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-glossary-extension: extend `docs/glossary.md` with new terms shipped recently
      scope: `docs/glossary.md` (extend, not restructure)
      accept: new entries for palette_diff/stats/merge, --config-dump, --version-json, /api/version, alphabetized; ≤40 added lines; CHANGELOG bullet
      notes: pure-docs follow-up

- [x] feat-docs-cli-list-narrow-styles: document `--list-{engine,hull,wing}-styles[-json]` in `docs/cli.md`
      scope: `docs/cli.md` (extend, not restructure)
      accept: new rows in the existing machine-readable list-flag block; ≤30 added lines; CHANGELOG bullet
      notes: pure-docs follow-up

- [x] feat-scripts-palette-merge: add `scripts/palette_merge.py` merging two palettes into a new one
      scope: `scripts/palette_merge.py` (new), `tests/test_palette_merge.py` (new)
      accept: prefer-a/prefer-b/prefer-defined strategies; merged palette passes `palette_lint.py --strict`; smoke test green; CHANGELOG bullet
      notes: complements `palette_diff.py`

- [x] feat-docs-presets-extension: extend `docs/presets.md` with per-preset parameter breakdown table
      scope: `docs/presets.md` (extend, not restructure)
      accept: new section with table of all 9 named presets + key params; values verified against `--list-presets-json`; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-tests-property-greeble-density-x-weapon-count-grid: add (greeble_density × weapon_count × seed) property test
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over (3 × 3 × 3 = 27 nodes); CHANGELOG bullet
      notes: extends cross-axis pattern to numeric axes

- [x] feat-docs-bench-ci-extension: extend `docs/bench-ci.md` with concrete CI snippet examples
      scope: `docs/bench-ci.md` (extend, not restructure)
      accept: GitHub Actions + GitLab CI + regression-detection stanzas; ≤80 added lines; CHANGELOG bullet
      notes: pure-docs unit; no real workflow files added

- [x] feat-palettes-biome-pack-2026-05-07d: add autumn_canopy, glow_lagoon biome palettes
      scope: `palettes/autumn_canopy.yaml`, `palettes/glow_lagoon.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-cli-config-dump: document `--config-dump` flag in `docs/cli.md`
      scope: `docs/cli.md` (extend, not restructure)
      accept: new section documenting `--config-dump`; ≤30 added lines; CHANGELOG bullet
      notes: pure-docs unit; pair with `feat-cli-config-dump` implementation

- [x] feat-cli-config-dump: add `--config-dump` flag emitting effective config as JSON
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--config-dump` emits `{"effective_config":{...}}` to stdout; exits 0 without generating a ship; mutually exclusive with output-file flags; not silenced by `--quiet`; per-flag tests; CHANGELOG bullet
      notes: useful for debugging / reproducing weirdness

- [x] feat-scripts-palette-diff: add `scripts/palette_diff.py` printing role-by-role block diff between two palettes
      scope: `scripts/palette_diff.py` (new), `tests/test_palette_diff.py` (new, lightweight)
      accept: prints a fixed-width table `role | A_block | B_block | same?`; `--csv` flag emits the same as CSV; exits 0 if both palettes load cleanly, 1 if either fails to load; smoke test asserts exit 0 + non-empty stdout; CHANGELOG bullet
      notes: complements `palette_lint.py` and `palette_stats.py`

- [x] feat-docs-recipes-extension: extend `docs/recipes.md` with 4 new task-oriented recipes
      scope: `docs/recipes.md` (extend, not restructure)
      accept: 4 new recipes cover palette diff, palette stats, /api/version, CI bench; ≤50 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-tests-property-cross-axis-pack-2026-05-07: add (cockpit × wing) + (hull × engine) cross-axis property tests
      scope: `tests/test_properties.py` (extend)
      accept: TWO new tests, each parametrized over (3 × 3 × 3 = 27 nodes); CHANGELOG bullet
      notes: complements cockpit×hull cross-axis test from cycle 2

- [x] feat-docs-troubleshooting-extension: extend `docs/troubleshooting.md` with 6 new entries
      scope: `docs/troubleshooting.md` (extend, not restructure)
      accept: 6 new rows cover --list-engine-styles, CSV piping, palette_stats parse drops, /api/version fallback, palette_diff <missing>, cross-axis test failures; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-palettes-biome-pack-2026-05-07c: add enchanted_grove, asteroid_belt biome palettes
      scope: `palettes/enchanted_grove.yaml`, `palettes/asteroid_belt.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-cli-flags-pack-2026-05-07: add `--list-engine-styles[-json]`, `--list-hull-styles[-json]`, `--list-wing-styles[-json]`, `--version-json` flags
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: each `--list-<x>-styles` prints one enum-name per line in declaration order; each `-json` sibling emits `{"<x>_styles":[...]}`; `--version-json` emits `{"version":"<X.Y.Z>"}` matching `--version` value; siblings mutually exclusive with non-json variant; not silenced by `--quiet`; per-flag tests; CHANGELOG bullets
      notes: closes the engine/hull/wing CLI gap surfaced by the `feat-docs-architecture-engines` agent

- [x] feat-docs-bench-csv-format: document the `--csv` schema family in `docs/bench.md`
      scope: `docs/bench.md` (extend, not restructure)
      accept: new section "CSV output format" lists every `bench_*.py` script's `--csv` header columns + row semantics (per-stage / TOTAL / single-summary distinction); cross-link to `docs/bench-ci.md`; ≤80 added lines; CHANGELOG bullet
      notes: closes the operator gap left after shipping `--csv` across all 9 bench scripts; pure-docs unit, no code touched

- [x] feat-tests-property-cockpit-x-hull-style-grid: add property test asserting `generate()` succeeds for (`cockpit_style` × `hull_style` × seed) grid
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over a representative slice (3 cockpit styles × 3 hull styles × seed grid `[0, 1, 7]` = 27 nodes max); assert `.litematic` exists + non-empty; failure names offending pair + seed; CHANGELOG bullet
      notes: complements existing single-axis property tests by stress-testing CROSS-axis interaction

- [x] feat-scripts-palette-stats: add `scripts/palette_stats.py` printing global palette stats
      scope: `scripts/palette_stats.py` (new), `tests/test_palette_stats.py` (new, lightweight)
      accept: script enumerates `palettes/*.yaml`, prints (palette count, distinct MC blocks used, top-10 most-used blocks, role coverage histogram) as a fixed-width table; `--csv` flag emits same data as CSV; exits 0; one smoke test asserting exit 0 + non-empty stdout; CHANGELOG bullet
      notes: complements `palette_lint.py` (per-file validation) with cross-corpus stats

- [x] feat-docs-faq-extension: extend `docs/faq.md` with 4 new Q&As covering recently-shipped surfaces
      scope: `docs/faq.md` (extend, not restructure)
      accept: new Q&As cover versioning, palette/preset distinction, CI bench, CLI flag discovery; ≤60 added lines; CHANGELOG bullet
      notes: pure-docs unit

- [x] feat-palettes-biome-pack-2026-05-07b: add desert_oasis, foggy_marsh biome palettes
      scope: `palettes/desert_oasis.yaml`, `palettes/foggy_marsh.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-architecture-engines: extend `docs/architecture.md` with an Engine pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Engine pipeline" describes `engine_styles.py` (EngineStyle + per-style placers) and the role of `engine_style` in the assembly pipeline; cross-link to `docs/cli.md --list-engine-styles` and `docs/web_ui.md /api/engine-styles`; ≤80 lines; CHANGELOG bullet
      notes: completes the per-component pipeline series (greebles + weapons + cockpit + hull + wing already shipped; engines is the missing one)

- [x] feat-api-version: add `GET /api/version` JSON endpoint exposing the installed package version
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components, `docs/web_ui.md`
      accept: route returns `{"version":"<X.Y.Z>"}` JSON sourced from package metadata (`importlib.metadata.version("spaceship_generator")` with a fallback for editable installs); OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: useful for clients/tooling to detect server version without scraping HTML; mirrors the narrow-endpoint family pattern

- [x] feat-docs-glossary: add `docs/glossary.md` defining recurring terms
      scope: `docs/glossary.md` (new), one-line link from `README.md`
      accept: file defines key terms (HullStyle, EngineStyle, WingStyle, CockpitStyle, StructureStyle, GreebleType, WeaponType, Role, ShapeParams, .litematic, palette, preset, gen_id) one short paragraph each; cross-link to `docs/cli.md`, `docs/web_ui.md`, `docs/configuration.md`, `docs/architecture.md`; ≤140 lines; CHANGELOG bullet; one-line README link
      notes: complements `docs/recipes.md` / `docs/configuration.md` by giving an A-Z term reference for new contributors

- [x] feat-palettes-biome-pack-2026-05-07: add volcanic_island, crystal_caves biome palettes
      scope: `palettes/volcanic_island.yaml`, `palettes/crystal_caves.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-bench-greeble-density-csv: add `--csv` flag to `scripts/bench_greeble_density.py`
      scope: `scripts/bench_greeble_density.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits CSV header + per-density / TOTAL rows; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of every other prior `feat-bench-*-csv` unit (summary / palette / compare / fleet / shape / full_pipeline / generator); preserve the existing fixed-width default output

- [x] feat-bench-mem-csv: add `--csv` flag to `scripts/bench_mem.py`
      scope: `scripts/bench_mem.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits CSV header + a single mean/p95/max-MB summary row; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of `feat-bench-*-csv` family; bench_mem.py reports peak Python heap (one summary row, no per-stage breakdown) so the CSV payload is a single data row + header

- [x] feat-bench-generator-csv: add `--csv` flag to `scripts/bench_generator.py`
      scope: `scripts/bench_generator.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits CSV header + per-phase rows; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of every other prior `feat-bench-*-csv` unit (summary / palette / compare / fleet / shape / full_pipeline)

- [x] feat-docs-architecture-wing: extend `docs/architecture.md` with a Wing pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Wing pipeline" describes `wing_styles.py` (WingStyle + per-style placers) and the role of `wing_style` in the assembly pipeline; cross-link to `docs/cli.md` and `docs/web_ui.md`; ≤80 lines; CHANGELOG bullet
      notes: completes the per-component pipeline series (greebles + weapons + cockpit + hull shipped; wing is the last)

- [x] feat-palettes-biome-pack-2026-05-05e: add warm_savanna, frozen_river biome palettes
      scope: `palettes/warm_savanna.yaml`, `palettes/frozen_river.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-api-roles: add `GET /api/roles` JSON endpoint mirroring `--list-roles-json`
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components, `docs/web_ui.md`
      accept: route returns `{"roles":[{"name":"<NAME>","value":<int>},...]}` JSON in declaration order; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: mirror of just-shipped `feat-cli-list-roles` JSON variant; one agent owns ship.py + test_api.py + web_ui.md

- [x] feat-docs-output-formats: add `docs/output-formats.md` explaining `.litematic` + JSON output formats
      scope: `docs/output-formats.md` (new), one-line link from `README.md`
      accept: file documents the `.litematic` format (Litematica schematic, who can open it, version compatibility), the `--output-json` payload schema (point at `--output-json-schema`), the web `/api/generate` response shape, and the `gen_id` cache lifecycle; cross-link to `docs/cli.md`, `docs/web_ui.md`, `docs/configuration.md`; ≤120 lines; CHANGELOG bullet; one-line README link
      notes: gap in current docs — operators have to dig through `cli.py` `--output-json-schema` + `ship.py` route source to learn the output payload shapes

- [x] feat-tests-property-weapon-count-grid: add property test asserting `generate()` succeeds for (`weapon_count` × seed) grid
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over weapon_count `[0, 1, 2, 4, 8]` × seed grid `[0, 1, 7]` (= 15 nodes); assert `.litematic` exists + non-empty; failure names offending count + seed; CHANGELOG bullet
      notes: complements existing `test_property_weapon_count_scales_weapon_specific_roles` which checks scaling but not every-count stability

- [x] feat-docs-architecture-hull: extend `docs/architecture.md` with a Hull pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Hull pipeline" describes `hull_styles.py` (HullStyle + per-style placers in `shape/hull.py`), the role of `hull_style` and `ShapeParams.hull_style`; cross-link to `docs/cli.md` and `docs/web_ui.md`; ≤80 lines; CHANGELOG bullet
      notes: mirror of just-shipped greebles / weapons / cockpit pipeline sections

- [x] feat-cli-list-roles: add `--list-roles` and `--list-roles-json` flags exposing the `Role` enum
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-roles` prints one Role enum name per line in declaration order, exits 0; `--list-roles-json` emits `{"roles":[{"name":"<NAME>", "value":<int>}, ...]}` not silenced by `--quiet`; mutually exclusive with each other; tests; CHANGELOG bullet
      notes: mirror of `--list-shape-styles` / `--list-shape-styles-json` pattern; `Role` is the int8 enum in `shape/core.py`; payload includes both name and integer value since the value matters for shape_grid consumers

- [x] feat-palettes-biome-pack-2026-05-05d: add eroded_badlands, magma_chamber biome palettes
      scope: `palettes/eroded_badlands.yaml`, `palettes/magma_chamber.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-bench-full-pipeline-csv: add `--csv` flag to `scripts/bench_full_pipeline.py`
      scope: `scripts/bench_full_pipeline.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits CSV header + per-stage / TOTAL rows; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of `feat-bench-summary-csv` / `feat-bench-palette-csv` / `feat-bench-compare-csv` / `feat-bench-fleet-csv` / `feat-bench-shape-csv`

- [x] feat-docs-recipes: add `docs/recipes.md` — common usage recipes
      scope: `docs/recipes.md` (new), one-line link from `README.md`
      accept: file presents 6-10 recipes (e.g., "generate one ship with seed", "batch 5 ships", "lint every palette before commit", "compare two seeds visually", "use a preset", "spin the wheel via /api/random") each with a one-paragraph description + concrete CLI / curl / web command; cross-link to `docs/cli.md`, `docs/web_ui.md`, `docs/quickstart.md`; ≤120 lines; CHANGELOG bullet; one-line README link
      notes: complements `docs/quickstart.md` (single happy-path) with task-oriented snippets a user can copy-paste

- [x] feat-tests-property-greeble-density-grid: add property test asserting `generate()` succeeds for (`greeble_density` × seed) grid
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over greeble_density `[0.0, 0.25, 0.5, 0.75, 1.0]` × seed grid `[0, 1, 7]` (= 15 nodes); assert `.litematic` exists + non-empty; failure names offending density + seed; CHANGELOG bullet
      notes: complements existing `test_property_greeble_density_monotonic_in_block_count` which checks monotonicity but not every-density stability

- [x] feat-palette-lint-all-flag: add `--all` flag to `scripts/palette_lint.py` linting every `palettes/*.yaml` at once
      scope: `scripts/palette_lint.py`, `tests/test_palette_lint.py` (extend)
      accept: `python scripts/palette_lint.py --all [--strict]` lints every palette in `palettes/`, exits 0 if all clean / 1 if any error; per-palette OK/error summary lines printed; CHANGELOG bullet
      notes: convenience over invoking the script per-file; should reuse the existing `lint_palette` core; tested with both clean and dirty palette inputs

- [x] feat-docs-configuration: add `docs/configuration.md` overview of all CLI / web config knobs
      scope: `docs/configuration.md` (new), one-line link from `README.md`
      accept: file enumerates CLI flags / web form fields / `ShapeParams` knobs grouped by category (shape / palette / style / greeble / weapon / output); cross-link to `docs/cli.md`, `docs/web_ui.md`; ≤120 lines; CHANGELOG bullet; one-line README link
      notes: complements `docs/cli.md` (per-flag reference) with a config-by-category index

- [x] feat-palettes-biome-pack-2026-05-05c: add dawn_meadow, glacial_blue biome palettes
      scope: `palettes/dawn_meadow.yaml`, `palettes/glacial_blue.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-bench-shape-csv: add `--csv` flag to `scripts/bench_shape.py` emitting CSV row instead of fixed-width table
      scope: `scripts/bench_shape.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits header + per-stage / TOTAL rows; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of `feat-bench-summary-csv` / `feat-bench-palette-csv` / `feat-bench-compare-csv` / `feat-bench-fleet-csv`

- [x] feat-docs-architecture-cockpit: extend `docs/architecture.md` with a Cockpit pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Cockpit pipeline" describes `cockpit_styles.py` (CockpitStyle + placers), the role of `cockpit_style` in the assembly pipeline; cross-link to `docs/cli.md --list-cockpit-styles` and `docs/web_ui.md /api/cockpit-styles`; ≤80 lines; CHANGELOG bullet
      notes: mirror of just-shipped `feat-docs-architecture-greebles` / `feat-docs-architecture-weapons`

- [x] feat-tests-property-no-greebles-no-weapons-combos: add property test asserting `generate()` succeeds for every (no_greebles, no_weapons) combo × seed grid
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over the 4 boolean combos × seed grid `[0, 1, 7]` (= 12 nodes); assert `.litematic` exists + non-empty; failure names offending combo + seed; CHANGELOG bullet
      notes: catches regressions in the no-greebles / no-weapons code paths that single-flag tests miss

- [x] feat-cli-list-palettes-json: add `--list-palettes-json` flag — machine-readable variant of `--list-palettes`
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-palettes-json` emits a single JSON document `{"palettes":[...]}` to stdout in alphabetical order, exits 0; not silenced by `--quiet`; mutually exclusive with `--list-palettes`; tested; CHANGELOG bullet
      notes: mirror of `feat-cli-list-presets-json` / `feat-cli-list-shape-styles-json`

- [x] feat-bench-fleet-csv: add `--csv` flag to `scripts/bench_fleet.py` emitting CSV row instead of fixed-width table
      scope: `scripts/bench_fleet.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits a header row + one data row per measured iteration/group; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of `feat-bench-summary-csv` / `feat-bench-palette-csv` / `feat-bench-compare-csv`

- [x] feat-tests-property-preset-grid: add property test asserting `generate()` succeeds for every (preset × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each named preset × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending preset + seed; CHANGELOG bullet
      notes: mirror of palette / structure / cockpit / wing-style sibling property tests; enumerate presets via the existing presets module API

- [x] feat-palettes-biome-pack-2026-05-05b: add sunflower_plains, stony_peaks biome palettes
      scope: `palettes/sunflower_plains.yaml`, `palettes/stony_peaks.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs

- [x] feat-docs-architecture-weapons: extend `docs/architecture.md` with a Weapon pipeline section
      scope: `docs/architecture.md` (extend, not restructure)
      accept: new section "Weapon pipeline" describes `weapon_styles.py` (WeaponType + scatter_weapons), the role of `weapon_count` in the assembly pipeline, the relationship to `greeble_styles` (weapons stamp into Role.EMPTY only); cross-link to `docs/cli.md --list-weapon-types` and `docs/web_ui.md /api/weapon-types`; ≤80 lines; CHANGELOG bullet
      notes: mirror of just-shipped `feat-docs-architecture-greebles`

- [x] feat-docs-cli-list-json-flags: extend `docs/cli.md` with the newly-shipped `--list-*-json` flag family
      scope: `docs/cli.md` (extend, not restructure)
      accept: docs/cli.md documents the four new `--list-cockpit-styles-json`, `--list-structure-styles-json`, `--list-greeble-types-json`, `--list-weapon-types-json` flags + the existing `--list-presets-json`, `--list-shape-styles-json`, `--output-json-schema` siblings as a coherent "machine-readable list/output" block; CHANGELOG bullet
      notes: pure-docs unit; ≤40 added lines; do not duplicate flag-by-flag schemas (reference the JSON shape inline)

- [x] feat-cli-list-json-pack-2026-05-05: add `--list-cockpit-styles-json`, `--list-structure-styles-json`, `--list-greeble-types-json`, `--list-weapon-types-json` flags
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: each flag emits a single JSON document (e.g. `{"cockpit_styles":[...]}`) to stdout in enum-declaration order, exits 0; not silenced by `--quiet`; mutually exclusive with non-json sibling; tested per flag; CHANGELOG bullet
      notes: shipped 2026-05-05; mirror of `feat-cli-list-shape-styles-json` — four new `--list-<x>-json` flags (action `store_true`) declared in `src/spaceship_generator/cli.py::build_parser` immediately after each non-json sibling so the help-text grouping reads as sibling pairs; help text reads `"Machine-readable variant of --list-<x>: emits a single JSON document {\"<x>\":[...]} to stdout. Mutually exclusive with --list-<x>. NOT silenced by --quiet."` so the carve-out is documented inline; mutex check via `parser.error("--list-<x> and --list-<x>-json are mutually exclusive")` placed alongside the existing `--list-shape-styles` mutex; short-circuit handler in `cli.main` placed adjacent to the non-json sibling handler emits via `print(json.dumps({...}), file=sys.stdout)` directly rather than the `_emit` funnel so `--quiet --list-<x>-json` still prints — same carve-out as `--stats-json` / `--list-presets-json` / `--list-shape-styles-json`; the `--list-weapon-types-json` handler additionally guards on `_weapon_styles is None` (mirrors the non-json sibling) so the optional weapon module's absence yields exit 1 + diagnostic line on stderr rather than an `AttributeError`; 12 new tests in `tests/test_cli.py` (3 per flag) cover (a) `test_cli_list_<x>_json_emits_valid_json` — exit 0 + `json.loads(captured.out)` is a dict with the single expected key + value matches `[m.value for m in <Enum>]` exactly (declaration order, no hard-coded list, sourced from the enum directly so the two paths can never drift), (b) `test_cli_list_<x>_json_quiet_still_emits` — `--quiet --list-<x>-json` still emits the JSON document, and (c) `test_cli_list_<x>_and_json_mutually_exclusive` — passing both raises `SystemExit` with non-zero code + stderr contains both flag names + `mutually exclusive`; full `pytest -q` + `ruff check .` both green

- [x] feat-api-narrow-style-endpoints: add `GET /api/hull-styles`, `GET /api/engine-styles`, `GET /api/wing-styles` JSON endpoints
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components, `docs/web_ui.md`
      accept: each route returns `{"<name>_styles":[...]}` JSON in enum-declaration order; OpenAPI spec enumerates them; spec-validate test stays green; CHANGELOG bullet
      notes: mirror of `feat-api-cockpit-styles` / `feat-api-structure-styles`; one agent owns ship.py + test_api.py

- [x] feat-bench-compare-csv: add `--csv` flag to `scripts/bench_compare.py` emitting CSV row instead of fixed-width table
      scope: `scripts/bench_compare.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits a header row + one row per compared variant; exits 0; smoke test runs `--csv --iterations 2`; CHANGELOG bullet
      notes: mirror of `feat-bench-summary-csv` / `feat-bench-palette-csv`

- [x] feat-palettes-biome-pack-2026-05-05: add bamboo_jungle, flower_forest biome palettes
      scope: `palettes/bamboo_jungle.yaml`, `palettes/flower_forest.yaml`
      accept: both palettes pass `scripts/palette_lint.py --strict`; `--list-palettes` enumerates them; CHANGELOG bullet
      notes: standard new-biome-palette pattern matching prior packs (deep_dark, jagged_peaks, swamp, etc.)

- [x] feat-docs-contributing: add `docs/contributing.md` short development guide
      scope: `docs/contributing.md` (new), one-line link from `README.md`
      accept: file documents repo layout, dev install (`pip install -e .[dev]`), test/ruff commands, branch naming convention, "where to file bugs"; ≤100 lines; CHANGELOG bullet; one-line README link
      notes: shipped 2026-05-05; new `docs/contributing.md` (99 lines under the 100-line cap) with H1 `# Contributing`, intro paragraph naming "anyone working on the codebase, including the dev-swarm tick" as the audience; `## Repo layout` bullets for `src/spaceship_generator/`, `tests/` (notes 2116-test count + property tests in `tests/test_properties.py` + bench smoke in `tests/test_bench_smoke.py`), `scripts/`, `palettes/`, `docs/` (one-sentence per-directory description sourced from `ls`); `## Local setup` documents `python -m venv .venv` + `pip install -e .[dev]` (the dev extra declared in `pyproject.toml`); `## Tests & lint` documents `python -m pytest -q` and `ruff check .`; `## Benchmarks` cross-links to `docs/bench.md` and `docs/bench-ci.md` and notes `scripts/bench_summary.py` for one-shot perf snapshots; `## Adding a palette` cross-links to `docs/palette_authoring.md` + `scripts/palette_lint.py --strict`; `## Branch / commit / PR convention` documents Conventional Commits (feat / fix / docs / chore / test) with a CHANGELOG-bullet reminder; `## Where to file bugs` links to GitHub issues with a "include seed + palette + CLI args" repro tip; `## Cross-links` bullet list to quickstart / architecture / cli / web_ui / release / troubleshooting / faq / bench / palette_authoring; one-line README link added immediately after the existing `docs/bench.md` link in the intro paragraph (no restructure, mirrors the `docs/faq.md` / `docs/bench.md` pattern); CHANGELOG bullet added at top of `## [Unreleased]`; `pytest -q` (2040 tests) + `ruff check .` both green on docs-only change

- [x] feat-tests-property-palette-grid: add property test asserting `generate()` succeeds for every (palette × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each palette in `palettes/` × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending palette + seed; CHANGELOG bullet
      notes: mirror of the structure/cockpit/wing-style sibling property tests but parametrized over palette filenames

- [x] feat-cli-output-json-schema: add `--output-json-schema` flag — emits the JSON Schema for the `--output-json` payload to stdout
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--output-json-schema` prints a single JSON Schema document describing the `--output-json` ship payload (top-level type, `properties` for `seed`, `palette`, `shape`, `blocks`, `download_url`?, `gen_id`?), exits 0; not silenced by `--quiet`; tested with `jsonschema.Draft7Validator.check_schema` for validity; CHANGELOG bullet
      notes: shipped 2026-05-05; new `--output-json-schema` flag (action `store_true`) in `src/spaceship_generator/cli.py::build_parser` placed immediately after `--output-json` so the sibling pair stays adjacent in `build_parser` and the help-text grouping reads as a sibling pair; help text reads `"Print the JSON Schema for the --output-json payload to stdout. Useful for downstream consumers validating output payloads. NOT silenced by --quiet."` so the carve-out is documented inline; new module-level `_OUTPUT_JSON_SCHEMA` Draft-7 dict declared adjacent to `_print_json_summary` in `cli.py` so both paths stay co-located and a future field added to one forces a sibling update to the other; schema is a top-level `type: object` with `required: ["seed","palette","shape","blocks","path"]` and `properties` covering exactly the key set `_print_json_summary` emits — `seed: integer`, `palette: string`, `shape: array of 3 integers (minItems/maxItems=3)`, `blocks: integer`, `path: string`; structurally aligned with `_OPENAPI_COMPONENTS["GenerateResult"]` (the canonical web-API schema in `src/spaceship_generator/web/blueprints/ship.py`) — both share `seed/palette/shape/blocks` keys with matching JSON types — but the CLI payload diverges on the file-output keys (`path` for the local `.litematic` filesystem path vs. the web API's `download_url` / `preview_url` / `gen_id` URL endpoints), so the schema is hand-written rather than derived (importing the web blueprint's component dict would couple `cli.py` to the optional `flask` web blueprint, which the CLI deliberately doesn't import); short-circuit handler in `cli.main` placed immediately after the `--list-shape-styles-json` handler (alongside the other `--*-json` short-circuits) emits via `print(json.dumps(_OUTPUT_JSON_SCHEMA), file=sys.stdout)` directly rather than the `_emit` funnel that gates on `--quiet` so `--quiet --output-json-schema` still prints — same carve-out as `--stats-json` / `--output-json` / `--list-presets-json` / `--list-shape-styles-json`; two new tests in `tests/test_cli.py` cover (a) `test_cli_output_json_schema_is_valid_jsonschema` — `pytest.importorskip("jsonschema")`, then `json.loads(captured.out)` returns a dict with a `$schema` containing `draft-07` (or `draft/2020`+ for forward-compatibility), `type: "object"`, a `properties` dict whose keys are a superset of `_REQUIRED_KEYS = {"seed","palette","shape","blocks","path"}` (sourced from the existing module-level constant in `tests/test_cli.py` so the two paths can never drift), plus `jsonschema.Draft7Validator.check_schema(schema)` to verify the schema itself is well-formed (catches malformed type names, broken `$ref`, etc.), and (b) `test_cli_output_json_schema_quiet_still_emits` — `--quiet --output-json-schema` still emits the JSON Schema document (carve-out parallels `--quiet --output-json` / `--quiet --stats-json` / `--quiet --list-presets-json` / `--quiet --list-shape-styles-json`); full `pytest -q` + `ruff check .` both green

- [x] feat-docs-architecture-greebles: extend `docs/architecture.md` with a Greeble pipeline section
      scope: `docs/architecture.md` (extend, do not create new doc), `docs/CHANGELOG.md`
      accept: new section "Greeble pipeline" describes `greeble_styles.py` (GreebleType + scatter_greebles), `shape/greebles.py`, the role of `greeble_density` in the assembly pipeline, the relationship to `weapon_styles` (weapons stamp into Role.EMPTY only); cross-link to `docs/cli.md --list-greeble-types` and `docs/web_ui.md /api/greeble-types`; ≤80 lines; CHANGELOG bullet
      notes: shipped 2026-05-05; new `## Greeble pipeline` h2 section inserted in `docs/architecture.md` immediately after the existing Shape-pipeline section's `### assembly.py (final pass)` subsection and before the `## Related documentation` footer so the two pipeline sections sit visually adjacent at the same h2 depth; matches the Shape-pipeline section's heading depth (h2 / h3) and per-module subsection convention (companion shipped in `feat-docs-shape-pipeline`); covers (1) `greeble_styles.py` with the 11-member `GreebleType` `StrEnum` (`TURRET`, `DISH`, `VENT`, `ANTENNA`, `PANEL_LINE`, `SENSOR_POD`, `CIRCUIT_BOARD`, `BATTLE_DAMAGE`, `PIPE_CLUSTER`, `ORGANIC_GROWTH`, `NANO_MESH`) and the `scatter_greebles(shape, rng, density, *, types=None) -> list[Placement]` entry point that samples surface anchors via `_surface_anchors_from_grid` (true top-facing skin when `shape` is the live numpy grid) or `_surface_anchors` (bounding-box approximation when `shape` is a `(W, H, L)` tuple), draws a Bernoulli mask whose draw is independent of the `types` allow-list size (so changing the allow-list never reshuffles which anchors fire), and concatenates per-anchor placements; (2) `shape/greebles.py` with the in-shape `_place_greebles` 1-voxel-bump pass + vectorized `_surface_mask` helper that runs *before* the final mirror so bumps are bilaterally symmetric in the returned grid; (3) the role of `greeble_density` (capped at `0.5` on `ShapeParams.greeble_density` in `__post_init__` for the in-shape bump pass, full `[0.0, 1.0]` range on `generate(greeble_density=...)` for the multi-cell scatter pass, plumbed from CLI `--greeble-density` and the web `greeble_density` form/JSON field in `web/blueprints/ship.py`) and `greeble_types` (optional allow-list eagerly validated in `generator.py`, `None` = all 11 types); (4) the relationship to `weapon_styles` — greebles run **before** weapons in `generator.generate`'s assembly order (`scatter_greebles` first, then `scatter_weapons`), and both passes share the no-overwrite invariant via the per-cell `if shape_grid[x, y, z] == Role.EMPTY` gate at the call site (sourced verbatim from `src/spaceship_generator/generator.py`'s scatter call sites) so greebles are immune to weapon overwrites and weapons reliably anchor on top of the now-greebled silhouette; one Mermaid `flowchart LR` diagram mirrors the existing Shape-pipeline diagram's style (`generate_shape → _place_greebles bumps → mirror+connect+mirror → engine_style override → scatter_greebles → scatter_weapons → assign_roles`) so the two pipeline diagrams read as siblings; cross-link footer points to `docs/cli.md` (`--list-greeble-types` / `--no-greebles` / `--greeble-density`) and `docs/web_ui.md` (`GET /api/greeble-types`); section spans 79 lines (under the 80-line cap); CHANGELOG bullet added at top of `## [Unreleased]`; `pytest -q` + `ruff check .` both green on docs-only change

- [x] feat-bench-palette-csv: add `--csv` flag to `scripts/bench_palette.py` emitting CSV row instead of fixed-width table
      scope: `scripts/bench_palette.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits header `palette,mean_ms,p95_ms` followed by one row per palette + a TOTAL row; exits 0; smoke test runs `--csv --iterations 2 --limit 2`; CHANGELOG bullet
      notes: shipped 2026-05-05; mirror of `feat-bench-summary-csv` — new `--csv` argparse flag in `scripts/bench_palette.py::parse_args` (action `store_true`, default `False`) declared adjacent to the existing `--iterations` / `--limit` / `--seed` flags with help text `"Emit CSV (palette,mean_ms,p95_ms) instead of fixed-width table; useful for CI / spreadsheet ingest."`; new `print_csv(rows, all_samples_ms)` helper writes through the stdlib `csv.writer(sys.stdout, lineterminator="\n")` so future palette names containing commas / quotes / newlines are escaped correctly without us reinventing it; the helper is a thin sibling of `print_table()` that re-uses the exact same per-iter aggregation (`all_samples_ms.mean()` and `np.percentile(all_samples_ms, 95)`) for the `TOTAL` row so the two output paths can never drift on the summary numbers; in `--csv` mode the run-banner (`bench_palette: palettes=... iterations=... seed=... ...`) is routed to stderr (via a single `progress_stream = sys.stderr if args.csv else sys.stdout` hoist) so the stdout stream stays a clean parseable CSV document an operator can pipe straight into a spreadsheet / CI parser without filtering noise out (in default fixed-width-table mode it stays on stdout where it's always been); absent-flag behavior is byte-identical to the legacy fixed-width formatter (preserved verbatim by routing through the unchanged `print_table()` + `print_total()` pair); new `tests/test_bench_smoke.py::test_bench_palette_csv_emits_csv` runs the script with `--csv --iterations 2 --limit 2 --seed 0` via `subprocess.run` and asserts exit 0 + first stdout line is exactly `palette,mean_ms,p95_ms` + at least one per-palette row appears in the CSV body + a `TOTAL,...` row appears in the body (catches a regression where the header emits but the body / TOTAL row is dropped); existing `tests/test_bench_smoke.py::test_bench_palette_runs_with_two_palettes_two_iterations` still asserts the fixed-width-table contract with `--csv` absent so the no-flag path is also pinned; full `pytest -q` + `ruff check .` both green

- [x] feat-cli-validate-palette: add `--validate-palette PATH` flag — runs strict lint against a single palette YAML and exits 0/1
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--validate-palette PATH` invokes the lint logic from `scripts/palette_lint.py::lint_palette` in-process, prints OK or per-error diagnostic lines, exits 0 on clean / 1 on error; tested with both passing and failing palette inputs; CHANGELOG bullet
      notes: shipped 2026-05-05; new `--validate-palette PATH` argparse flag (`metavar="PATH"`, `type=pathlib.Path`) in `src/spaceship_generator/cli.py::build_parser` placed immediately after `--palette-info` so the three palette-related flags (`--list-palettes`, `--palette-info`, `--validate-palette`) stay adjacent in the help-text grouping; short-circuit handler in `cli.main` placed immediately after the `--palette-info` handler for the same visual adjacency; the lint module isn't part of the installed package (it lives under `scripts/`), so the handler loads it lazily via `importlib.util.spec_from_file_location` from a path computed relative to the package root (`Path(__file__).resolve().parent.parent.parent / "scripts" / "palette_lint.py"`) — chosen over `sys.path` mutation as the safer one-shot import pattern; the loaded module is registered in `sys.modules` *before* `exec_module` so Python's `@dataclass` annotation resolution (which looks up `cls.__module__` in `sys.modules`) succeeds for the `LintResult` dataclass — without this, dataclass construction raises `AttributeError: 'NoneType' object has no attribute '__dict__'` (caught and fixed during initial implementation); on a clean palette (no errors AND no warnings — strict mode, matches `scripts/palette_lint.py --strict`) prints `OK` to stdout via the existing `_emit(args, ...)` funnel so `--quiet` silences it on the success path; on a dirty palette emits one `error: <msg>` line per error and one `warn: <msg>` line per warning to `sys.stderr` so diagnostics always surface (even paired with `--quiet`) and exits 1; defensive checks: missing target file → `--validate-palette: file not found: <path>` to stderr + exit 1; missing lint module → `--validate-palette: lint module not found at <path>` to stderr + exit 1; two new tests in `tests/test_cli.py` cover (a) `test_cli_validate_palette_clean` runs against the strict-clean `palettes/sci_fi_industrial.yaml` (the canonical default palette) and asserts exit 0 + `OK` in stdout (without `--quiet`), and (b) `test_cli_validate_palette_dirty` writes a deliberately-broken palette YAML to `tmp_path` (every required role mapped to `"not a block"` — invalid block id format, no `namespace:id` colon and contains a space) and asserts exit 1 + at least one `error:`-prefixed diagnostic line on stderr (without pinning the exact wording, which is owned by `scripts/palette_lint.py::lint_palette`); full `pytest -q` (2115 tests) + `ruff check .` both green

- [x] feat-tests-property-structure-styles: add property test asserting `generate()` succeeds for every (`StructureStyle` × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each `StructureStyle` enum member × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending structure-style + seed; CHANGELOG bullet
      notes: shipped 2026-05-05; new `tests/test_properties.py::test_property_structure_style_seed_grid_generates_non_empty_litematic` deterministically pins every `StructureStyle` enum member (6 members: FRIGATE, FIGHTER, DREADNOUGHT, SHUTTLE, HAMMERHEAD, CARRIER) crossed with the small fixed seed grid `[0, 1, 7]` (3 seeds — matches the hull/engine/wing/cockpit/greeble/weapon-type sibling parametrize tests), asserting `generate()` writes a `.litematic` file with `os.path.getsize(...) > 0` and `block_count > 0`; mirror of the wing-style and cockpit-style parametrize tests in `feat-tests-property-wing-styles` / `feat-tests-property-cockpit-styles`, threaded via `ShapeParams.structure_style` (constructed fresh per param pair) rather than a top-level `generate()` kwarg since `StructureStyle` is plumbed through `ShapeParams` rather than `generate()`'s public signature — completes deterministic every-member coverage for the last public shape-style enum so a regression in any single structure profile (silhouette taper / engine override / wing override / hull rx-ry scale in `src/spaceship_generator/structure_styles.py`) surfaces deterministically as a self-named failure node rather than relying on Hypothesis sampling; uses `pytest.mark.parametrize` (chosen over Hypothesis for the same reasons as the sibling tests — deterministic, faster, parametrize IDs self-name failures as `[seed-structure_style]`) with `ids=lambda s: s.value` so failure node IDs read e.g. `[7-frigate]` rather than the noisy `<StructureStyle.FRIGATE: 'frigate'>` repr; complements the existing Hypothesis-based `test_property_structure_x_hull_cross_product_no_crash` which samples 20 random `(StructureStyle, HullStyle)` pairs and may legitimately skip individual `StructureStyle` members on any given run; placed immediately after the cockpit-style parametrize sibling and before the greeble-type comment block to keep the five shape-style siblings (hull / engine / wing / cockpit / structure) visually adjacent in the file; total of 18 new test nodes (6×3) run in ~1.0 s on the dev box at `length=16/width=8/height=6`; full `pytest -q` (2110 tests) + `ruff check .` both green

- [x] feat-bench-summary-csv: add `--csv` flag to `scripts/bench_summary.py` emitting CSV row instead of fixed-width table
      scope: `scripts/bench_summary.py`, `tests/test_bench_smoke.py` (extend)
      accept: `--csv` emits header `bench,metric,iterations` followed by one row per bench (no fixed-width padding); exits 0; smoke test runs `--csv --iterations 2 --limit 2`; CHANGELOG bullet
      notes: shipped 2026-05-05; new `--csv` argparse flag in `scripts/bench_summary.py::parse_args` (action `store_true`, default `False`) declared adjacent to the existing `--iterations` / `--limit` / `--seed` / `--fleet-count` flags with help text `"Emit CSV (bench,metric,iterations) instead of fixed-width table; useful for CI / spreadsheet ingest."`; new `print_csv(results)` helper writes through the stdlib `csv.writer(sys.stdout, lineterminator="\n")` so future bench names containing commas / quotes / newlines are escaped correctly without us reinventing it; in `--csv` mode the run-banner (`bench_summary: iterations=... seed=... ...`) and the per-bench `running <name> ...` progress lines are routed to stderr (via a single `progress_stream = sys.stderr if args.csv else sys.stdout` hoist) so the stdout stream stays a clean parseable CSV document an operator can pipe straight into a spreadsheet / CI parser without filtering noise out (in default fixed-width-table mode they stay on stdout where they've always been); failed benches in CSV mode emit a row with `metric=FAIL` and `iterations=0` matching the existing fixed-width FAIL handling so the row count stays stable across invocations; absent-flag behavior is byte-identical to the legacy fixed-width formatter (preserved verbatim by routing through the unchanged `print_table()` path); new `tests/test_bench_smoke.py::test_bench_summary_csv_emits_csv` runs the umbrella with `--csv --iterations 2 --limit 2 --fleet-count 2 --seed 0` via `subprocess.run` and asserts exit 0 + first stdout line is exactly `bench,metric,iterations` + at least one bench name appears in the subsequent rows (catches a regression where the header emits but the body is dropped); existing `tests/test_bench_smoke.py::test_bench_summary_runs_minimal` still asserts the fixed-width-table contract with `--csv` absent so the no-flag path is also pinned; full `pytest -q` + `ruff check .` both green

- [x] feat-cli-list-structure-styles: add `--list-structure-styles` flag — prints every `StructureStyle` enum value, exits 0
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-structure-styles` prints one structure style per line in enum-declaration order, exits 0; `--quiet` carve-out preserved (silenced when paired); tested; CHANGELOG bullet
      notes: shipped 2026-05-05; mirror of `--list-cockpit-styles` — argparse declaration in `src/spaceship_generator/cli.py::build_parser` placed immediately after `--list-cockpit-styles` so the structural sibling `--list-*-styles` flags stay adjacent in `build_parser` and the help-text grouping reads as a sibling pair; short-circuit handler in `cli.main` placed immediately after the existing `--list-cockpit-styles` handler for visual adjacency; uses the existing `_emit(args, ...)` helper so the `--quiet` carve-out keeps working without a special case (silenced when paired with `--quiet` like the other `--list-*` flags); same no-header/no-indent output, same short-circuit pattern returning `0`; handler iterates `StructureStyle` directly (StrEnum natural iteration = declaration order, deterministic and stable across runs) so callers can pipe straight into another tool without parsing grouped output; `StructureStyle` was already imported from `.shape` at the top of `cli.py` (used by `--structure-style` choices), so no new import was needed; new `tests/test_cli.py::test_cli_list_structure_styles` covers exit 0 + every member's `.value` present + deterministic enum-declaration order via `[line for line in lines if line] == [s.value for s in StructureStyle]` (no hard-coded list, so the test doesn't drift when a new structure style is added) + asserts none of the `--list-styles` group headers (`Hull styles:` / `Engine styles:` / `Wing styles:` / `Cockpit styles:` / `Weapon types:`) leak into the output; full `pytest -q` + `ruff check .` both green

- [x] feat-docs-bench: add `docs/bench.md` cataloging every `scripts/bench_*.py` script with one-line description + run command
      scope: `docs/bench.md` (new), one-line link from README
      accept: file lists every `scripts/bench_*.py` script (currently 9: bench_compare, bench_fleet, bench_full_pipeline, bench_generator, bench_greeble_density, bench_mem, bench_palette, bench_shape, bench_summary) with one-line description + `python scripts/<name>.py --help` invocation; CHANGELOG bullet; one-line README link
      notes: shipped 2026-05-05; new `docs/bench.md` is a 42-line catalog (well under the 100-line cap, no fenced code-block delimiters) of every `scripts/bench_*.py` script (9 scripts: `bench_compare`, `bench_fleet`, `bench_full_pipeline`, `bench_generator`, `bench_greeble_density`, `bench_mem`, `bench_palette`, `bench_shape`, `bench_summary`) rendered as a 3-column Markdown table (`Script | What it measures | Example invocation`) matching the table style of `docs/palettes.md` / `docs/cli.md` / `docs/troubleshooting.md` for visual consistency; descriptions and example invocations are sourced from each script's module docstring + `argparse --help` output and the smoke-test invocation pattern in `tests/test_bench_smoke.py` so the doc and the actual scripts stay in lockstep; top-of-file cross-link header points to `quickstart.md` (5-minute walk), `cli.md` (CLI flag reference), `troubleshooting.md` (common errors), and `faq.md` ("how do I...?" reference) so an operator can hop between the four "operator-facing" docs in one click; "How to read the output" footer paragraph documents the shared `mean_ms` / `p95_ms` / `TOTAL` table convention used by every wall-clock bench, the `mean_mb` / `p95_mb` / `max_mb` substitution for `bench_mem.py`, and the cProfile-attributed `phase | total_s | mean_s | pct` shape for `bench_generator.py`; "Aggregate snapshot" footer documents `bench_summary.py` as the one-shot driver that runs every sibling bench in sequence and prints their TOTAL rows in a single consolidated table — the canonical "perf snapshot before/after a refactor" command; one-line README link added immediately after the existing `docs/faq.md` link in the intro paragraph (no restructure — the line now reads "Wondering 'how do I...?' See [docs/faq.md](docs/faq.md) for the common-question reference. Profiling a refactor? See [docs/bench.md](docs/bench.md) for the bench-script catalog."); CHANGELOG bullet added at the top of `## [Unreleased]`; full `pytest -q` + `ruff check .` both green (docs-only change but run for safety per the brief)

- [x] feat-cli-list-shape-styles-json: add `--list-shape-styles-json` flag — machine-readable variant of `--list-shape-styles`
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-shape-styles-json` emits a single JSON document `{"hull_styles":[...],"engine_styles":[...],"wing_styles":[...]}` to stdout in enum-declaration order, exits 0; not silenced by `--quiet`; mutually exclusive with `--list-shape-styles`; tested; CHANGELOG bullet
      notes: shipped 2026-05-05; new `--list-shape-styles-json` flag in `src/spaceship_generator/cli.py::build_parser` placed immediately after `--list-shape-styles` so the sibling pair stays adjacent in `build_parser` and the help-text grouping reads as a sibling pair (mirrors the `--list-presets` / `--list-presets-json` adjacency from `feat-cli-list-presets-json`); short-circuit handler in `cli.main` placed immediately after the existing `--list-shape-styles` handler for visual adjacency; emits via `print(json.dumps({...}), file=sys.stdout)` directly rather than the `_emit` funnel that gates on `--quiet` so `--quiet --list-shape-styles-json` still prints — same carve-out as `--stats-json` / `--output-json` / `--list-presets-json`, documented in the help text; payload shape `{"hull_styles":[...],"engine_styles":[...],"wing_styles":[...]}` is byte-identical to `GET /api/shape-styles` (same `[s.value for s in HullStyle]` etc. serialization and key set), so a CLI-driven discovery client and a web client see the exact same enumeration; mutex check via `parser.error("--list-shape-styles and --list-shape-styles-json are mutually exclusive")` (exit 2 + `mutually exclusive` stderr) placed immediately after the `--list-presets` vs `--list-presets-json` mutex check so the two pairs stay visually adjacent in the validation block; three new tests in `tests/test_cli.py` cover (a) `test_cli_list_shape_styles_json_emits_valid_json` — `json.loads(captured.out)` returns a dict with keys `{"hull_styles","engine_styles","wing_styles"}`, each a list, contents matching `[s.value for s in HullStyle]` / `[s.value for s in EngineStyle]` / `[s.value for s in WingStyle]` exactly (declaration order, no hard-coded list so the test doesn't drift when a new style is added), (b) `test_cli_list_shape_styles_json_quiet_still_emits` — `--quiet --list-shape-styles-json` still emits the JSON document (carve-out parallels `--quiet --list-presets-json` / `--quiet --stats-json` / `--quiet --output-json`), and (c) `test_cli_list_shape_styles_and_json_mutually_exclusive` — passing both raises `SystemExit` with non-zero code and stderr containing both flag names + `mutually exclusive`; full `pytest -q` + `ruff check .` both green

- [x] feat-api-structure-styles: add `GET /api/structure-styles` JSON endpoint
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components
      accept: route returns `{"structure_styles":[...]}` JSON in enum-declaration order; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: shipped 2026-05-05; new `api_structure_styles` view in `src/spaceship_generator/web/blueprints/ship.py` placed immediately after `api_cockpit_styles` — same `[s.value for s in StructureStyle]` serialization (declaration order, deterministic across runs) so the endpoint stays byte-identical with the matching slice of `/api/meta`'s `structure_styles` array; `StructureStyle` was already imported at the top of `ship.py` (used by `index()` / `do_generate()` / `api_meta()` view functions), so no new import was needed; new `StructureStyles` schema (with `required: ["structure_styles"]`, mirroring the `CockpitStyles` / `GreebleTypes` / `WeaponTypes` siblings) added to `_OPENAPI_COMPONENTS` immediately after `CockpitStyles`, and `/api/structure-styles` path added to `_OPENAPI_PATHS` immediately after `/api/cockpit-styles` so `/api/spec` enumerates the route and `tests/test_api_spec_validate.py` stays green; two new tests in `tests/test_api.py` cover (a) `test_api_structure_styles_ok` — 200 + `application/json` content-type + non-empty array + every `StructureStyle.value` present + exact enum-declaration-order match, and (b) `test_api_structure_styles_listed_in_openapi_spec` — path appears in `/api/spec` with a `summary` and `200` response; one row added to the `/api/*` discovery table in `docs/web_ui.md` immediately after the `/api/cockpit-styles` row; full `pytest -q` + `ruff check .` both green

- [x] feat-tests-property-wing-styles: add property test asserting `generate()` succeeds for every (`WingStyle` × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each `WingStyle` enum member × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending wing-style + seed; CHANGELOG bullet
      notes: shipped 2026-05-05; new `tests/test_properties.py::test_property_wing_style_seed_grid_generates_non_empty_litematic` deterministically pins every `WingStyle` enum member (6 members: STRAIGHT, SWEPT, DELTA, TAPERED, GULL, SPLIT) crossed with the small fixed seed grid `[0, 1, 7]` (3 seeds — matches the hull/engine/greeble-type sibling parametrize tests), asserting `generate()` writes a `.litematic` file with `os.path.getsize(...) > 0` and `block_count > 0`; mirror of the hull/engine-style parametrize tests in `feat-tests-property-shape-styles`, but plumbed via `ShapeParams.wing_style` (constructed fresh per param pair) rather than a top-level `generate()` kwarg since `WingStyle` is exposed via `ShapeParams` rather than `generate()`'s public signature — closes the explicit carve-out in the prior CHANGELOG note for the hull/engine sibling ("WingStyle is intentionally not duplicated here since it flows only via `ShapeParams`") so every public shape-style enum now has identical deterministic every-member coverage; uses `pytest.mark.parametrize` (chosen over Hypothesis for the same reasons as the sibling tests — deterministic, faster, parametrize IDs self-name failures as `[seed-wing_style]`) with `ids=lambda s: s.value` so failure node IDs read e.g. `[7-swept]` rather than the noisy `<WingStyle.SWEPT: 'swept'>` repr; covers a regression in any single wing placer (`_place_straight` / `_place_swept` / `_place_delta` / `_place_tapered` / `_place_gull` / `_place_split` in `src/spaceship_generator/wing_styles.py`) one tick earlier than the Hypothesis-sampled `test_property_all_style_combos_symmetric` would since this explicitly visits every member rather than sampling; placed immediately after the engine-style parametrize sibling and before the greeble-type comment block to keep the three shape-style siblings (hull / engine / wing) visually adjacent in the file; total of 18 new test nodes (6×3) run in ~0.9 s on the dev box at `length=16/width=8/height=6`; full `pytest -q` + `ruff check .` both green

- [x] feat-tests-property-weapon-types: add property test asserting `generate()` succeeds for every (`WeaponType` × seed) pair
      scope: `tests/test_properties.py` (extend)
      accept: parametrize over each `WeaponType` enum member × seed grid `[0, 1, 7]`; assert `.litematic` exists + non-empty; failure names offending weapon-type + seed; CHANGELOG bullet
      notes: shipped 2026-05-05; new `tests/test_properties.py::test_property_weapon_type_seed_grid_generates_non_empty_litematic` deterministically pins every `WeaponType` enum member (5 members: TURRET_LARGE, MISSILE_POD, LASER_LANCE, POINT_DEFENSE, PLASMA_CORE) crossed with the small fixed seed grid `[0, 1, 7]` (3 seeds — matches the hull/engine/greeble-type sibling parametrize tests), asserting `generate()` writes a `.litematic` file with `os.path.getsize(...) > 0` and `block_count > 0`; mirrors how the `--weapon-type TYPE` CLI flag plumbs into `generate()` (`[WeaponType(args.weapon_type)]` → `generate(..., weapon_types=[that_type])`) so the per-type CLI plumbing is exercised end-to-end per enum member; `weapon_count=4` is set on `generate()` so the scatter actually fires and the restricted-type list has a chance to matter (the writer no-ops at `weapon_count=0`); uses `pytest.mark.parametrize` (chosen over Hypothesis for the same reasons as the hull/engine/greeble companions — deterministic, faster, parametrize IDs self-name failures as `[seed-weapon_type]`) with `ids=lambda t: t.value` so failure node IDs read e.g. `[7-turret_large]` rather than the noisy `<WeaponType.TURRET_LARGE: 'turret_large'>` repr; placed immediately after the greeble-type parametrize sibling and before the palette-parse test to keep the per-type/per-style siblings (hull / engine / greeble / weapon) visually adjacent in the file; total of 15 new test nodes (5×3) run in ~1.1 s on the dev box at `length=16/width=8/height=6`; complements the Hypothesis-based `test_property_weapon_count_scales_weapon_specific_roles` which samples weapon count but never restricts to a single `WeaponType`, so a regression in any single weapon builder now surfaces deterministically as a self-named failure node; full `pytest -q` + `ruff check .` both green

- [x] feat-bench-greeble-density: add `scripts/bench_greeble_density.py` per-density `generate()` micro-bench
      scope: `scripts/bench_greeble_density.py` (new), `tests/test_bench_smoke.py` (extend)
      accept: script iterates densities `[0.0, 0.25, 0.5, 0.75, 1.0]` (or `--densities` override) running N `generate()` calls each, prints fixed-width `density | mean_ms | p95_ms` table + TOTAL, exits 0; smoke test runs `--iterations 2 --densities 0.0,0.5`; CHANGELOG bullet
      notes: shipped 2026-05-05; new `scripts/bench_greeble_density.py` mirrors `scripts/bench_palette.py`'s schema (warm-up iter, per-axis fixed-width table, TOTAL aggregating per-iter samples across all densities, numpy + stdlib only); argparse `--iterations N` (default 3), `--densities CSV` (default `0.0,0.25,0.5,0.75,1.0`, parsed via custom `_parse_densities` argparse type that rejects unparseable tokens / out-of-range values with a clean `error:` line), `--seed S` (default 0); palette pinned to `sci_fi_industrial` (matches `bench_full_pipeline.py` default) and ship footprint fixed at `length=16/width_max=8/height_max=6` so a 5-density × 3-iter sweep finishes in seconds; `greeble_density` passed directly to `generate()` (which accepts `[0.0, 1.0]`) rather than via `ShapeParams.greeble_density` (capped at `0.5`) so the upper-bound `1.0` sample is reachable; smoke test `tests/test_bench_smoke.py::test_bench_greeble_density_runs_minimal` runs `--iterations 2 --densities 0.0,0.5 --seed 0` via `subprocess.run` and asserts exit 0 + presence of `density`/`mean_ms`/`p95_ms`/`TOTAL` in stdout

- [x] feat-api-cockpit-styles: add `GET /api/cockpit-styles` JSON endpoint
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components
      accept: route returns `{cockpit_styles:[...]}` JSON in enum-declaration order; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: shipped 2026-05-05; new `api_cockpit_styles` view in `src/spaceship_generator/web/blueprints/ship.py` placed immediately after `api_weapon_types` — same `[c.value for c in CockpitStyle]` serialization (declaration order, deterministic across runs) so the endpoint stays byte-identical with the matching slice of `/api/meta`'s `cockpit_styles` array; `CockpitStyle` was already imported at the top of `ship.py` (used by `index()` / `do_generate()` / `api_meta()` view functions), so no new import was needed; new `CockpitStyles` schema (with `required: ["cockpit_styles"]`, mirroring the `GreebleTypes` and `WeaponTypes` siblings) added to `_OPENAPI_COMPONENTS` immediately after `GreebleTypes`, and `/api/cockpit-styles` path added to `_OPENAPI_PATHS` immediately after `/api/greeble-types` so `/api/spec` enumerates the route and `tests/test_api_spec_validate.py` stays green; two new tests in `tests/test_api.py` cover (a) `test_api_cockpit_styles_ok` — 200 + `application/json` content-type + non-empty array + every `CockpitStyle.value` present + exact enum-declaration-order match, and (b) `test_api_cockpit_styles_listed_in_openapi_spec` — path appears in `/api/spec` with a `summary` and `200` response; one row added to the `/api/*` discovery table in `docs/web_ui.md` immediately after the `/api/weapon-types` row; full `pytest -q` + `ruff check .` both green

- [x] feat-docs-faq: add `docs/faq.md` covering common usage questions
      scope: `docs/faq.md` (new), one-line link from README
      accept: file covers ≥6 Q&A entries (e.g. how do I pick a random palette? how do I install preview deps? how do I build a fleet? how do I add a custom palette? how do I start the web UI? where does the .litematic open in Minecraft?) sourced from CLI help / docs/quickstart.md / docs/web_ui.md; CHANGELOG bullet; one-line README link
      notes: shipped 2026-05-05; new `docs/faq.md` is a 43-line "How do I X?" reference doc with 10 Q&A entries (each `### Question?` h3 + 1-3 sentence answer) covering the brief's required topics (`--palette random`, dev/preview deps, `--fleet-count` / `--seeds`, custom palette via `palettes/<name>.yaml`, web UI launch via `flask --app spaceship_generator.web.app run`, Litematica mod load) plus four discretion entries (the `--list-*` short-circuit family, `--output-json` / `--stats-json` / `--export-manifest` JSON paths, `--no-weapons` / `--no-greebles` shorthands, `scripts/bench_*.py` benchmarking); top-of-file cross-link header points to `quickstart.md`/`troubleshooting.md`/`cli.md`/`palettes.md`/`web_ui.md`; every answer cross-links the canonical source doc so the FAQ stays a thin orchestrator rather than duplicating content; one-line README link added immediately after the existing `docs/troubleshooting.md` link (no restructure); CHANGELOG bullet under `## [Unreleased]`; `pytest -q` and `ruff check .` both green (docs-only change)

- [x] feat-cli-list-cockpit-styles: add `--list-cockpit-styles` flag — prints every `CockpitStyle` enum value, exits 0
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-cockpit-styles` prints one cockpit style per line in enum-declaration order, exits 0; `--quiet` carve-out preserved (silenced when paired); tested; CHANGELOG bullet
      notes: shipped 2026-05-05; argparse declaration placed immediately after `--list-weapon-types` in `build_parser` so the three `--list-*-types`/`--list-*-styles` sibling flags stay adjacent; short-circuit handler in `cli.main` placed directly after the `--list-weapon-types` handler — iterates `CockpitStyle` (StrEnum natural iteration = declaration order, deterministic and stable) and emits each `.value` on its own line via the existing `_emit(args, ...)` helper so the `--quiet` carve-out keeps working without a special case (silenced when paired with `--quiet` same as the other `--list-*` flags); `CockpitStyle` is already imported from `spaceship_generator.shape` at module top (used by the `--cockpit` choices argument) so no new import needed; no header/no indent — bare values per line so callers can pipe straight into another tool; new `tests/test_cli.py::test_cli_list_cockpit_styles` covers exit 0 + every member's `.value` present + deterministic enum-declaration order via direct `[line for line in lines if line] == [c.value for c in CockpitStyle]` list comparison (no hard-coded string list, so the test doesn't drift when a new cockpit style is added) + asserts none of the `--list-styles` group headers leak into the output; full `pytest -q` + `ruff check .` both green

- [x] feat-api-weapon-types: add `GET /api/weapon-types` JSON endpoint mirroring weapon enum discovery
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components
      accept: route returns `{weapon_types:[...]}` JSON in enum-declaration order; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: shipped 2026-04-30 in `4d4af79`; flipped to closed in cycle1 of 2026-05-05 tick (todo entry was stale — code, tests, OpenAPI schema, and CHANGELOG bullet all already on `main`)

- [x] feat-cli-list-presets-json: add `--list-presets-json` flag — machine-readable variant of `--list-presets`
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-presets-json` emits a single JSON array of `{name, description, ...}` entries to stdout in alphabetical order, exits 0; not silenced by `--quiet`; mutually exclusive with `--list-presets`; tested; CHANGELOG bullet
      notes: shipped 2026-04-30; new `--list-presets-json` argparse flag emits one JSON array via `print(json.dumps(entries, default=str), file=sys.stdout)` directly (NOT through `_emit`) so the carve-out from `--quiet` matches `--stats-json` and `--output-json`; declared adjacent to `--list-presets` in `build_parser` so the help-text grouping reads as a sibling pair; entries are built by iterating `_presets.list_presets()` (alphabetical) and merging `{"name": n}` with every public top-level field of `SHIP_PRESETS[n]` (private `_*` keys defensively skipped — none today, but mirrors the brief's "every public field" contract so a future internal field doesn't leak via stdout); `json.dumps(..., default=str)` is a belt-and-braces guard for any future non-trivially-JSON-serializable value (every preset field today is already a StrEnum / float / int / tuple-of-StrEnums so `default=str` is never actually invoked, but cheap insurance); mutex check (`if list_presets and list_presets_json: parser.error(...)`) added next to the existing `--stats` vs `--stats-json` mutex so both share the parser.error → exit 2 + `mutually exclusive` stderr-message contract; defensive `_presets is None` partial-rollout fallback still emits a valid empty JSON array on stdout (so downstream parsers don't fault on a malformed payload) plus the `presets unavailable: <reason>` breadcrumb on stderr — parallels how `--list-presets` handles the same case but with empty `[]` instead of silent return; help-text documents the `--quiet` carve-out explicitly ("NOT silenced by --quiet so scripts can pair --quiet --list-presets-json"); three new tests in `tests/test_cli.py` cover (a) `test_cli_list_presets_json_emits_valid_json` — `json.loads(captured.out)` returns a `list` of length `len(list_presets())` with each entry carrying non-empty `name` + `description` keys, alphabetical order pinned by `actual_names == expected_names` direct comparison, (b) `test_cli_list_presets_json_quiet_still_emits` — `--quiet --list-presets-json` still produces a parseable JSON array of the right length, and (c) `test_cli_list_presets_and_json_mutually_exclusive` — passing both raises `SystemExit` with non-zero code and stderr containing both flag names + `mutually exclusive`; full `pytest -q` (2029 tests) + `ruff check .` both green

- [x] feat-api-greeble-types: add `GET /api/greeble-types` JSON endpoint mirroring `--list-greeble-types`
      scope: `src/spaceship_generator/web/blueprints/ship.py`, `tests/test_api.py`, OpenAPI components
      accept: route returns `{greeble_types:[...]}` JSON in enum-declaration order; OpenAPI spec enumerates it; spec-validate test stays green; CHANGELOG bullet
      notes: shipped 2026-04-30; new `api_greeble_types` route in `src/spaceship_generator/web/blueprints/ship.py` mirrors the `api_shape_styles` sibling structurally — same `[t.value for t in GreebleType]` serialization (declaration order, deterministic across runs) so the two endpoints stay byte-identical with the matching slice of `/api/styles`; new `GreebleTypes` schema (with `required: ["greeble_types"]`) added to `_OPENAPI_COMPONENTS` and `/api/greeble-types` path added to `_OPENAPI_PATHS` so `/api/spec` enumerates the route and `tests/test_api_spec_validate.py` stays green; two new tests in `tests/test_api.py` cover (a) `test_api_greeble_types_ok` — 200 + `application/json` content-type + non-empty array + every `GreebleType.value` present + exact enum-declaration-order match, and (b) `test_api_greeble_types_listed_in_openapi_spec` — path appears in `/api/spec` with a `summary` and `200` response; one row added to the `/api/*` discovery table in `docs/web_ui.md` between `/api/shape-styles` and `/api/presets`; full `pytest -q` + `ruff check .` both green

- [x] feat-cli-list-weapon-types: add `--list-weapon-types` flag — prints every `WeaponType` enum value, exits 0
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-weapon-types` prints one weapon type per line in enum-declaration order, exits 0; tested; CHANGELOG bullet
      notes: shipped 2026-04-30; argparse declaration moved from its old orphaned spot under `--list-presets` up to sit immediately after `--list-greeble-types` (mirrors the structural sibling so the two `--list-*-types` flags are declared adjacently); short-circuit handler in `cli.main` placed directly after the `--list-greeble-types` handler — iterates `WeaponType` (StrEnum natural iteration = declaration order, deterministic and stable) and emits each `.value` on its own line via the existing `_emit(args, ...)` helper so the `--quiet` carve-out keeps working without a special case (suppresses stdout same as the other `--list-*` flags); replaces the older `--list-weapon-types` handler that emitted indented `  weapon_name` lines and called `raise SystemExit(0)` — the new handler drops the indent so callers can pipe straight into another tool (no leading-whitespace strip needed) and uses `return 0` matching every other `--list-*` short-circuit; when the optional `weapon_styles` module is unavailable the handler still prints the `weapon_styles unavailable: <reason>` fallback to stderr and returns exit 1 (preserved from the old handler so a partial rollout keeps a clear error path); new `tests/test_cli.py::test_cli_list_weapon_types` covers exit 0 + every member's `.value` present + deterministic enum-declaration order via direct `[line for line in lines if line] == [w.value for w in WeaponType]` list comparison (no hard-coded string list, so the test doesn't drift when a new weapon type is added) + asserts none of the `--list-styles` group headers leak into the output; existing `tests/test_cli_extra.py::test_list_weapon_types` (substring assertions on `turret_large` / `missile_pod`) stays green under the new bare-line output; full `pytest -q` (2028 tests) + `ruff check .` both green

- [x] feat-docs-troubleshooting: add `docs/troubleshooting.md` covering common errors and fixes
      scope: `docs/troubleshooting.md` (new), one-line link from README
      accept: file documents at least 5 common failure modes (palette not found, invalid hull style, weapon-count mutex collision, web rate-limit hit, missing optional deps) with one-line cause + one-line fix each; CHANGELOG bullet; one-line README link
      notes: shipped 2026-04-30; new `docs/troubleshooting.md` is a 29-line single-table reference (Symptom | Cause | Fix) followed by a "Where to find more" cross-link footer pointing to `quickstart.md`/`cli.md`/`palettes.md`/`web_ui.md` — well under the 80-line acceptance cap; covers 14 distinct failure modes (more than the 5-row floor) sourced verbatim from the actual `parser.error(...)` / `argparse.ArgumentTypeError` / `raise FileNotFoundError(...)` call sites in `src/spaceship_generator/cli.py` and `src/spaceship_generator/palette.py` so the doc and the user-visible stderr never drift: palette-not-found (`Palette 'NAME' not found at .../palettes/NAME.yaml` from `palette.load_palette` at `palette.py:163`), `argparse` `invalid choice:` errors for the six enum-bound flags (`--hull-style` / `--engine-style` / `--wing-style` / `--cockpit` / `--greeble-style` / `--weapon-type`), the four `parser.error` mutually-exclusive-flag pairs (`--no-weapons` vs `--weapon-count`, `--no-greebles` vs `--greeble-density`, `--stats` vs `--stats-json`, `--output -` vs `--repeat`/`--fleet-count`/`--seeds`), the `--ship-size W>=4 H>=4 L>=8` floor (line 70 of `cli.py`) and `--greeble-density [0.0, 1.0]` range (line 211), the three `--seeds` parse modes with their canonical error text from `_parse_seeds` (lines 106/118/138/143), the web `HTTP 429 {"error": "rate_limited"}` path with the `SHIPFORGE_RATE_LIMIT` (default 30) / `SHIPFORGE_RATE_WINDOW` (default 60s) env tunables read from `web/blueprints/ratelimit.py` (lines 164/168), and the optional-dep `ModuleNotFoundError` paths (`flask`, `jsonschema`, `Pillow`) with the `pip install -e .[dev]` / `requirements-dev.txt` fixes plus the `presets unavailable` / `weapon_styles unavailable` stderr-warning fallbacks from the `try/except ImportError` guards at lines 25/33/41 of `cli.py`; each row of the table cross-references the relevant `--list-*` discovery flag (`--list-palettes` / `--list-shape-styles` / `--list-greeble-types` / `--list-weapon-types`) so users land on the right next command in one click; deliberately uses the table layout (rather than per-error subsections) for compactness — the entire reference fits on one screen scroll and stays under the 80-line cap with room for future entries; one-line README link added directly after the existing `docs/quickstart.md` link in the intro paragraph (no restructure — the line now reads "New here? See [docs/quickstart.md](docs/quickstart.md) for a 5-minute getting-started guide. Hit an error? See [docs/troubleshooting.md](docs/troubleshooting.md) for common failures and one-line fixes."); CHANGELOG bullet added at the top of `## [Unreleased]`; full `pytest -q` (2028 tests) + `ruff check .` both green (docs-only change but run for safety per the brief)

- [x] feat-palettes-biome-pack-2026-04-30: add 2 more biome palettes (`deep_dark`, `jagged_peaks`)
      scope: `palettes/deep_dark.yaml`, `palettes/jagged_peaks.yaml`, `docs/palettes.md`, `docs/CHANGELOG.md`
      accept: both pass `test_palette_lint --strict`; loadable via `--palette NAME`; alphabetical row insert in `docs/palettes.md`; CHANGELOG bullet
      notes: shipped 2026-04-30; rounds palette count to 57; `deep_dark` = Minecraft 1.19 deep dark sculk biome (sculk hull / deepslate HULL_DARK accent / cyan-stained-glass windows / deepslate-tile engines / soul-lantern ENGINE_GLOW (chose `soul_lantern` because `sculk_catalyst` is not in the strict-lint known-emissive list — `ancient_city` already ships with that warning under strict, so `deep_dark` deliberately diverges to stay strict-clean) / tinted-glass cockpit / cobbled-deepslate wings / chiseled-deepslate greebles / soul-torch running lights (distinct from soul-lantern ENGINE_GLOW) / polished-deepslate interior); `jagged_peaks` = Minecraft 1.18 snowy mountain peaks biome (snow-block hull / blue-ice HULL_DARK accent (chose `blue_ice` over `packed_ice` because canonical packed-ice preview hex is too close to snow-block to clear the 1.5 contrast floor — preview hex `#5a90b8` gives Y≈0.520, contrast vs HULL Y≈0.97 ≈ 1.79 well above the 1.5 floor) / light-blue-stained-glass windows (preview hex `#a8d4f0`, Y≈0.78 well above the 0.35 floor) / polished-diorite engines / sea-lantern ENGINE_GLOW (known-emissive list) / glass cockpit / powder-snow wings / stone greebles / lantern running lights (distinct from sea-lantern ENGINE_GLOW so no duplicate-mapping warning) / gravel interior); every role maps to a distinct block id in both palettes so no duplicate-role warnings; both `--strict` lint clean (WINDOW luminance ≥ 0.35, HULL/HULL_DARK contrast ≥ 1.5, ENGINE_GLOW emissive) — verified via `.venv/Scripts/python scripts/palette_lint.py --file palettes/deep_dark.yaml --strict` and same for `jagged_peaks.yaml` (both print `OK`); both load via `--palette deep_dark` / `--palette jagged_peaks` (verified via end-to-end `--seed 0 --output-json` round-trip); catalog rows inserted alphabetically in `docs/palettes.md` (`deep_dark` between `dark_forest`/`deepslate_drone`, `jagged_peaks` between `ice_spikes`/`jungle_canopy`); header count bumped from 55 to 57; full `pytest -q` + `ruff check .` both green

- [x] feat-palettes-biome-pack-2026-04-29b: add 2 more biome palettes (`swamp` + `dark_forest`)
      scope: `palettes/swamp.yaml`, `palettes/dark_forest.yaml`, `docs/palettes.md`, `docs/CHANGELOG.md`
      accept: both pass `test_palette_lint`; loadable via `--palette NAME`; alphabetical row insert in `docs/palettes.md`; CHANGELOG bullet
      notes: shipped 2026-04-29; rounds palette count to 55; `swamp` = mossy-cobblestone hull / oak-log HULL_DARK accent / lime-stained-glass windows (preview hex `#a8d870`, Y≈0.74 well above the 0.35 floor) / stripped-oak-log engines / ochre-froglight ENGINE_GLOW (known-emissive list) / tinted-glass cockpit / oak-leaves vine-canopy wings (chose `oak_leaves` over `lily_pad`/`vine` since both of the latter render as flat sprite rather than a solid block — `oak_leaves` reads as the dense canopy-and-vine mass that swamp biomes are known for and is the same WING family `sparse_jungle` ships with) / stripped-oak-wood greebles / lantern running lights / moss-block interior — every role maps to a distinct block id so no duplicate warnings; HULL/HULL_DARK contrast = (0.496)/(0.221) ≈ 2.24 well above the 1.5 floor; `dark_forest` = dark-oak-log hull / dark-oak-planks HULL_DARK accent / yellow-stained-glass canopy-shaft windows (preview hex `#e5e533`, Y≈0.82 — chose yellow over `brown_stained_glass` because brown's canonical hex `#664c33` falls under the 0.35 luminance floor; thematically reads as shafts of sunlight cutting through the dense roofed-forest canopy) / stripped-dark-oak-log engines / shroomlight ENGINE_GLOW (known-emissive list, fits the dark-forest "huge mushroom" sub-feature) / tinted-glass cockpit / brown-mushroom-block wings (the giant brown mushrooms are the dark-forest signature feature and the brief explicitly calls for them) / stripped-dark-oak-wood greebles / lantern running lights / moss-block interior — every role maps to a distinct block id so no duplicate warnings; HULL/HULL_DARK contrast = (0.215)/(0.116) ≈ 1.85 above the 1.5 floor (achieved by picking distinct preview hexes for log vs planks even though the canonical block colors `#3b2812`/`#422b14` are too close to pass strict lint as-is — the YAML preview hex is freely chosen and only used for the strict-lint contrast check); both `--strict` lint clean (WINDOW luminance ≥ 0.35, HULL/HULL_DARK contrast ≥ 1.5, ENGINE_GLOW emissive, no role duplicates) — verified via `.venv/Scripts/python scripts/palette_lint.py --file palettes/swamp.yaml --strict` and same for `dark_forest.yaml` (both print `OK`); both load via `--palette swamp` / `--palette dark_forest` (verified via `--palette-info NAME` round-trip); catalog rows inserted alphabetically in `docs/palettes.md` between `cyberpunk_neon`/`deepslate_drone` (for `dark_forest`) and between `steampunk_brass`/`swamp_bog` (for `swamp` — `swamp` sorts before `swamp_bog` since `swamp` is a prefix and ASCII-shorter); header count bumped from 53 to 55; full `pytest -q` (1999 tests) + `ruff check .` both green

- [x] feat-bench-summary: add `scripts/bench_summary.py` umbrella driver running all bench scripts and tabulating results
      scope: `scripts/bench_summary.py` (new), `tests/test_bench_smoke.py` (extend with N=2 smoke)
      accept: script invokes `bench_full_pipeline.py`, `bench_shape.py`, `bench_palette.py`, `bench_mem.py`, `bench_fleet.py` via subprocess (each with `--iterations 2 --limit 2` where applicable), captures their TOTAL row, prints an aggregate fixed-width table; exits 0; CHANGELOG bullet
      notes: shipped 2026-04-29; new `scripts/bench_summary.py` spawns each sibling bench via `subprocess.run([sys.executable, script_path, ...])` (using `sys.executable` so the active venv interpreter is shared with children — avoids the `.venv` path-on-Windows headache that a hard-coded `python` would hit); argparse `--iterations N` (default 2), `--limit N` (default 2, forwarded only to `bench_palette --limit`), `--seed S` (default 0), `--fleet-count N` (default 2, forwarded only to `bench_fleet --fleet-count`) — defaults chosen to mirror the smoke-test footprint so an interactive run takes seconds; per-bench argv is built by a small `_ArgsBuilder` class with a `*_args` method per child bench, looked up via `getattr(builder, spec.args_factory)` so the bench-spec table at module scope stays declarative (adding a new bench is one `BenchSpec` entry + one args method); each child bench's `TOTAL` line is parsed by a single shared regex (the five sibling benches all print `TOTAL  mean_X  p95_X  [...]` in the same fixed-width template, so the first numeric field after `TOTAL` is always the mean) — surfaced as the headline metric in the aggregate table, labelled `ms` for the four wall-clock benches and `mb` for `bench_mem`'s peak Python heap; columns are `bench | metric | iterations` with the bench-name column auto-fit to the longest row label; if any single child bench fails (non-zero exit, missing `TOTAL` line, unparseable mean, or `OSError` from a busted venv) the row prints `FAIL` in the metric column rather than aborting the whole run, captured stderr is printed below the table, and the umbrella exits 1 only at the end (so a single broken bench doesn't blackhole the rest of the snapshot); benches print their name to stdout *before* running so a Ctrl-C mid-run shows which one was in flight; new `tests/test_bench_smoke.py::test_bench_summary_runs_minimal` runs the umbrella with `--iterations 2 --limit 2 --fleet-count 2 --seed 0` via `subprocess.run` and asserts exit 0 + every child bench script's name appears in stdout (catches the regression where the umbrella silently drops a row from `BENCHES`); stdlib only (no extra deps); on the dev box the full umbrella run takes ~3 s wall-clock at the smoke defaults — turns the five micro-benches into a single "perf snapshot" command useful before/after a refactor, complementing per-script depth with cross-script breadth; full `pytest -q` (1993 tests) + `ruff check .` both green

- [x] feat-cli-list-greeble-types: add `--list-greeble-types` flag — prints every `GreebleType` enum value, exits 0
      scope: `src/spaceship_generator/cli.py`, `tests/test_cli.py`
      accept: `--list-greeble-types` prints one greeble type per line in enum-declaration order, exits 0; tested; CHANGELOG bullet
      notes: shipped 2026-04-29; new `args.list_greeble_types` short-circuit handler in `cli.main` placed directly after the `--list-shape-styles` handler — it iterates `GreebleType` (declaration order is the StrEnum's natural iteration order, deterministic and stable) and emits each `.value` on its own line via the existing `_emit(args, ...)` helper so the `--quiet` carve-out keeps working without a special case (suppresses stdout same as the other `--list-*` flags); deliberately no group header / indent prefix (only one enum to emit, so the indent-by-two grouping `--list-shape-styles` uses would be noise) — output is the bare value list suitable for piping straight into another tool; existing `--list-styles` / `--list-shape-styles` behavior unchanged (the new flag short-circuits before either handler so adding it doesn't perturb the grouped paths); new `tests/test_cli.py::test_cli_list_greeble_types` covers exit 0 + every member's `.value` present + deterministic enum-declaration order via direct `[line for line in lines if line] == [g.value for g in GreebleType]` list comparison (no hard-coded string list, so the test doesn't drift when a new greeble type is added) + asserts none of the `--list-styles` group headers leak into the output; full `pytest -q` (1974 tests) + `ruff check .` both green

- [x] feat-tests-cli-help-snapshot: add a snapshot-style test pinning `--help` output references every public flag
      scope: `tests/test_cli.py`
      accept: test runs `build_parser().format_help()` and asserts every CLI flag declared in `cli.py` is mentioned by name in the help string; failure names the missing flag; CHANGELOG bullet
      notes: shipped 2026-04-29; new `tests/test_cli.py::test_cli_help_text_mentions_every_declared_flag` walks `build_parser()._actions` (the canonical argparse list of registered actions) and for every action with non-empty `option_strings` (skipping positionals, which have empty `option_strings`) collects every flag string (long form, short alias, etc.) into a flat list, then asserts each one appears verbatim in `parser.format_help()`; discovery is dynamic — adding a new `add_argument` to `cli.py` automatically widens the assertion so the test never goes stale and won't be the test you have to update when shipping a new flag; failure mode caught is silent removal/rename of a flag (e.g. someone deletes the `add_argument` for `--quiet` or renames it to `--silent` and forgets to update one of the docs/CLI ref tables) or `help=argparse.SUPPRESS` slips; on miss the assertion message lists the offending flag name(s) directly so the failure is unambiguous; also asserts `format_help()` returns a non-empty string and mentions `spaceship` (case-insensitive substring match against `parser.prog`) so a parser that's been gutted entirely also fails fast; defensive `len(declared_flags) >= 5` sanity check catches the case where the test logic itself broke (e.g. `parser._actions` access changed in a future argparse) so a green test always means the help string really does mention every flag; complements the narrower per-flag help assertions in this same file (`test_cli_no_weapons_help_mentions_both_flags`) by giving catalog-wide coverage of every flag in one cheap defensive test (~0.5 s); full `pytest -q` (1973 tests) + `ruff check .` both green

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
