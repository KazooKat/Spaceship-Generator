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
