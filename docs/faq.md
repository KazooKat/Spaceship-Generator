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
