# FAQ

A "How do I X?" reference for the Spaceship Generator. Companion to [quickstart.md](quickstart.md) (5-minute walk) and [troubleshooting.md](troubleshooting.md) (common errors). For the full flag list see [cli.md](cli.md); for the palette catalog see [palettes.md](palettes.md); for the HTTP API see [web_ui.md](web_ui.md).

### How do I pick a random palette?

Pass `--palette random` — the generator picks one of the shipped palettes at generation time, so each run varies. See [cli.md](cli.md) for the full `--palette` flag reference and [palettes.md](palettes.md) for the catalog of names you can also pin explicitly.

### How do I install the preview / web extras?

The base `pip install -e .` only pulls runtime deps. Add `pip install -e .[dev]` to pick up `pytest` / `ruff` / `hypothesis`; install `flask` and `Pillow` directly (`pip install flask Pillow`) if you want the web UI and PNG previews. The same fix list lives in [troubleshooting.md](troubleshooting.md) under the `ModuleNotFoundError` row.

### How do I build a fleet of ships?

Two routes. `--fleet-count N` plans a coherent fleet of `N` ships and writes each as `ship_<seed>_<i>.litematic` (tunable via `--fleet-size-tier` and `--fleet-style-coherence`). `--seeds 1,2,3` (or `--seeds 0-9`, or a mix like `--seeds 1,3-4,9`) generates one ship per seed with no shared style. See [cli.md](cli.md) § "Repeat & fleet modes".

### How do I add a custom palette?

Drop a YAML file at `palettes/<name>.yaml` mapping each role to a Minecraft block ID and (optionally) a hex preview color. It auto-appears in `--list-palettes`, the `/api/palettes` JSON, and the web UI dropdown — no code changes. See [palette_authoring.md](palette_authoring.md) for the full role list and lint rules.

### How do I start the web UI?

Run `flask --app spaceship_generator.web.app run` from the repo root and open `http://127.0.0.1:5000`. The form is the same parameter surface as the CLI, plus a WebGL preview and one-click `.litematic` download. See [web_ui.md](web_ui.md) for the HTML page list and `/api/*` JSON route reference.

### How do I open the `.litematic` in Minecraft?

Install the [Litematica mod](https://www.curseforge.com/minecraft/mc-mods/litematica) for Minecraft Java 1.20+, copy the file into `.minecraft/schematics/`, and load it from Litematica's `Load Schematic` menu in-game. The same step is in [quickstart.md](quickstart.md) § 2.

### How do I list all presets / palettes / styles?

Use the `--list-*` short-circuit flags: `--list-palettes`, `--list-presets` (or `--list-presets-json` for a single JSON document), `--list-shape-styles`, `--list-greeble-types`, `--list-weapon-types`, `--list-cockpit-styles`, or the broader `--list-styles`. Each prints to stdout and exits 0. See [cli.md](cli.md) § "Style discovery" / "Presets".

### How do I get JSON output instead of human text?

`--output-json` emits one NDJSON summary line per ship to stdout (kept on under `--quiet`). `--stats-json` prints role / block-count tallies as JSON. `--export-manifest` writes a `<name>.json` sidecar next to each `.litematic` (reproducible later via `--from-manifest FILE`). See [cli.md](cli.md) § "Diagnostics & manifests".

### How do I disable weapons or greebles?

Pass `--no-weapons` (shorthand for `--weapon-count 0`) and/or `--no-greebles` (shorthand for `--greeble-density 0`). Each is mutually exclusive with its numeric counterpart — see [troubleshooting.md](troubleshooting.md) for the exact error if both are passed.

### How do I benchmark generation speed?

Run `python scripts/bench_full_pipeline.py` for end-to-end ship-build wall-clock, `scripts/bench_shape.py` for per-stage shape timings, `scripts/bench_palette.py` for per-palette cost variance, `scripts/bench_mem.py` for peak Python heap, or `scripts/bench_summary.py` to drive every sibling bench in one fixed-width aggregate table. See [performance.md](performance.md) for baseline numbers and [bench-ci.md](bench-ci.md) for the CI regression gate.

### How do I get the package version programmatically?

For HTTP clients use `GET /api/version`, which returns a `{"version":"X.Y.Z"}` JSON document — see [web_ui.md](web_ui.md) for the full `/api/*` route table. For shell pipelines and tooling use `--version-json` (machine-readable JSON, mutually exclusive with `--version`); `--version` itself prints the plain `spaceship_generator <ver>` line. See [cli.md](cli.md) for the full flag reference.

### What's the difference between a palette and a preset?

A *palette* is a YAML mapping of role → Minecraft block ID (a visual skin only — no shape parameters). A *preset* is a named bundle of generator parameters (shape style, dimensions, weapon count, etc.) and may itself reference a palette. See [palette_authoring.md](palette_authoring.md) for the palette role schema, [presets.md](presets.md) for the preset catalog, and [glossary.md](glossary.md) for the canonical one-line definitions.

### How do I run benchmarks in CI?

Every `scripts/bench_*.py` script accepts a `--csv` flag that emits a clean CSV document on stdout (uniform across all 9 bench scripts), suitable for spreadsheet diffing or piping into a CI parser. The run-banner and progress lines are routed to stderr in `--csv` mode so the stdout stream stays parseable. See [bench.md](bench.md) for the full bench-script catalog and [bench-ci.md](bench-ci.md) for the existing CI regression gate.

### Where do I find the list of every CLI flag?

`python -m spaceship_generator --help` is authoritative — the curated reference (grouped by category, with examples) lives in [cli.md](cli.md). For enum discovery use the `--list-*` flag family (`--list-presets`, `--list-palettes`, `--list-shape-styles`, `--list-cockpit-styles`, `--list-structure-styles`, `--list-greeble-types`, `--list-weapon-types`, `--list-roles`); each has a sibling `--list-*-json` variant for tooling. See [cli.md](cli.md) § "Style discovery" / "Presets".

### Which palette tooling script should I reach for?

The `scripts/palette_*.py` family splits by task: `palette_lint.py` validates a single palette (or `--all` to sweep `palettes/*.yaml`) against the role schema; `palette_stats.py` produces cross-corpus role-coverage / block-frequency stats (with `--csv` and `--top N` flags); `palette_diff.py` shows a role-by-role diff between two palettes (`--csv` for spreadsheet ingest); `palette_merge.py` combines two palettes into one with a configurable strategy; `palette_to_json.py` converts a palette YAML into JSON for tooling that prefers a JSON pipeline. See [palette_authoring.md](palette_authoring.md) for the role schema and [recipes.md](recipes.md) for end-to-end task walk-throughs.

### Why do cross-axis property tests exist alongside single-axis ones?

The single-axis `test_property_<axis>_seed_grid_*` tests pin one parameter at a time and catch regressions in that axis in isolation; the cross-axis siblings (`test_property_cockpit_x_hull_style_seed_grid_*`, `test_property_cockpit_x_wing_style_seed_grid_*`, `test_property_hull_x_engine_style_seed_grid_*`, `test_property_greeble_density_x_weapon_count_seed_grid_*`, `test_property_palette_x_cockpit_style_seed_grid_*` in `tests/test_properties.py`) pin two axes together over a small seed grid. They catch interaction-only regressions that a single-axis test cannot — e.g. a palette missing a role that only matters under a specific cockpit placer, or a maxed greeble scatter starving the weapon scatter of free anchors — where each axis is fine alone but the combination silently no-ops.

### How do I navigate `docs/architecture.md` for one specific component?

Open `docs/architecture.md` and jump to the `## Per-component pipelines` section near the top — it lists each per-component sub-pipeline (Shape / Hull / Wing / Greeble / Weapon / Cockpit / Engine / Structure) as anchor links to its own `## <Component> pipeline` section deeper in the doc. Click the one you care about to land directly on the inputs / steps / outputs / extension-points table for that component without scrolling through the others. The same per-component sections double as the entry points cross-linked from [extending.md](extending.md) and [glossary.md](glossary.md).

### How do I capture the exact effective config of a CLI invocation?

Add `--config-dump` to the same command line — it emits a single `{"effective_config":{...}}` JSON document to stdout reflecting the preset-resolved palette / shape / style / weapon args that WOULD be passed into `generate()` (so `--palette random` is resolved to the concrete palette name, presets are expanded, etc.) and exits 0 without writing a `.litematic`. It is mutually exclusive with `--output` / `--output-json` / `--output-json-schema` and prints under `--quiet` (same carve-out as the `--list-*-json` family). Pipe it to a file (`... --config-dump > effective.json`) to share or replay a weird ship reproducibly. See [cli.md](cli.md) § "Effective config dump".

### When should I use `--meta-json` vs the individual `--list-*-json` flags?

Reach for `--meta-json` when a tool needs the full enum / palette / preset / version surface in one shot — it emits a single combined JSON document (`{version, palettes, presets, hull_styles, engine_styles, wing_styles, cockpit_styles, structure_styles, greeble_types, weapon_types, roles}`) in one subprocess invocation, which is the CLI mirror of the web `/api/meta` endpoint. Reach for an individual `--list-<x>-json` (e.g. `--list-palettes`, `--list-presets-json`, `--list-shape-styles-json`) when you only need a single enum or list and want to skip the cost of building the rest. Both families share the `--quiet` carve-out and exit 0; `--meta-json` is mutually exclusive with `--output` / `--output-json` / `--output-json-schema` / `--config-dump`. See [cli.md](cli.md) § "Machine-readable list / output flags".

### How do I run `palette_lint.py --json` in a CI gate?

Pass `--all --json` (or `--file palettes/X.yaml --json`) to `scripts/palette_lint.py` — it emits a JSON array (or single object) of `{"palette": "...", "ok": true|false, "errors": [...], "warnings": [...]}` documents and exits 0 if every entry has `ok=true`, 1 otherwise (combine with `--strict` to count warnings toward `ok`). A typical CI gate pipes it through `jq` to surface offenders, e.g. `python scripts/palette_lint.py --all --json | jq '.[] | select(.ok | not)'`. See [recipes.md](recipes.md) § "Recipe 22 — Wire palette lint into a CI gate as JSON" for the full pipeline walk-through.

### What does the Texture pipeline do at a glance?

The Texture pipeline (`src/spaceship_generator/texture.py`) is the role refinement stage between the coarse shape grid and palette-driven block assignment — `assign_roles(shape_grid, params)` walks 10 internal `_paint_*` passes (interior, accent stripe, panel bands, windows, hull noise, rivets, engine glow, engine glow ring, wing lights, belly lights, nose-tip light) that rewrite coarse `HULL` / `COCKPIT_GLASS` / `ENGINE` / `WING` / `GREEBLE` cells into the fine roles (`INTERIOR`, `WINDOW`, `HULL_DARK`, `ENGINE_GLOW`, `LIGHT`) the palette layer maps to blocks. Tunable via `TextureParams` (plumbed through `--window-period` / `--stripe-period` / `--engine-glow-depth` / `--hull-noise-ratio` / `--panel-bands` / `--rivet-period` / `--engine-glow-ring`). See [architecture.md](architecture.md#texture-pipeline) for the full pipeline section and [cli.md](cli.md) for the texture flag pack.

### What does the hull × wing cross-axis property test catch that single-axis tests don't?

`test_property_hull_x_wing_style_seed_grid_*` in `tests/test_properties.py` pins (`HullStyle` × `WingStyle` × seed) over a 27-node grid (3 × 3 × 3) to catch interaction-only regressions where the hull silhouette and the wing planform individually validate but their *combination* silently no-ops — e.g. a narrow dagger hull combined with a swept-back gull wing where the wing's stern anchor column falls outside the dagger's thin Z-band, so neither single-axis sibling (`test_property_hull_style_seed_grid_*` or `test_property_wing_style_seed_grid_*`) sees a problem. See [architecture.md](architecture.md) for the Hull / Wing per-component pipeline sections and the [generic cross-axis FAQ entry](#why-do-cross-axis-property-tests-exist-alongside-single-axis-ones) above for the broader pattern.

### Why does the palette × greeble_density cross-axis property test exist?

`test_property_palette_x_greeble_density_x_seed_grid_*` in `tests/test_properties.py` pins (palette × `greeble_density` × seed) over a 27-node grid (3 × 3 × 3) to catch interaction-only regressions where palette role coverage and the greeble scatter density individually validate but their *combination* silently no-ops — e.g. a palette stubbing the `greeble` role combined with `greeble_density=1.0` claiming every surface anchor with a block id the palette cannot map (degenerate output) — that slips past both single-axis siblings (`test_property_palette_seed_grid_*` and `test_property_greeble_density_seed_grid_*`). It is the palette-axis numeric-sibling of the existing palette × cockpit_style cross-axis test and slices the palette list dynamically (first / middle / last alphabetically of `_PALETTE_NAMES`) so a new YAML in `palettes/` automatically tracks the slice. See the [generic cross-axis FAQ entry](#why-do-cross-axis-property-tests-exist-alongside-single-axis-ones) above for the broader pattern.

### When should I reach for the `arcane_library` or `mistwood_grove` palettes?

Pick `arcane_library` for indoor / dim-lit / scholarly-vault reads — bookshelf-and-stone block roles with warm soul-lantern accent lighting fit research-vessel, archive-ship, or library-station fiction; pick `mistwood_grove` for organic / wooded / overgrown-canopy reads — moss-and-mangrove block roles with subdued green palette fit treeship, biological-vessel, or grove-station fiction. Both are biome-themed siblings of the existing pack (`abyssal_trench`, `sunset_horizon`, `ember_forge`, `twilight_glade`, `meteor_shower`, `solar_corona`, `scarlet_oasis`, `frostbite_tundra`) and ship via the standard `--palette <name>` flag — see [palettes.md](palettes.md) for the full catalog and [palette_authoring.md](palette_authoring.md) for the role schema.

### What fields does `palette_lint.py --json` emit and how do I consume them?

`scripts/palette_lint.py --json` emits the modern lint schema `{"palette": "<name>", "ok": true|false, "errors": [...], "warnings": [...]}` — `palette` is the YAML stem (no `.yaml`), `ok` is the boolean pass/fail flag (true = no errors, or no errors-and-warnings under `--strict`), `errors` is a list of fatal-issue strings, `warnings` is a list of non-fatal strings. `--file palettes/X.yaml --json` emits one object; `--all --json` emits a JSON array of those objects (one per palette). The legacy `--format json` flag still emits the older `{name, path, errors, warnings}` shape for backward compatibility — pick `--json` for new CI gates that branch on `.ok`, `--format json` for legacy tooling. See [recipes.md](recipes.md) Recipe 22 for a `jq` consumption walk-through and [troubleshooting.md](troubleshooting.md) for the schema-mismatch row.

### What is the `## Cross-link index` footer in `docs/architecture.md` for?

The `## Cross-link index` H2 at the bottom of `docs/architecture.md` is a 3-column `Pipeline | CLI flag(s) | Web API endpoint(s)` table mapping each documented pipeline (Shape / Hull / Wing / Greeble / Weapon / Cockpit / Engine / Structure / Fleet / Texture) to its driver CLI flag(s) and (where applicable) `/api/*` mirror — each pipeline name links to its in-doc anchor (`#shape-pipeline`, `#hull-pipeline`, …) so readers can jump from a CLI flag or HTTP endpoint they're using back to the pipeline section that defines its semantics. Use it as the navigation entry point when you know "which flag" or "which endpoint" but not "which pipeline" — see [cli.md](cli.md) for the full flag reference and [web_ui.md](web_ui.md) for the API.
