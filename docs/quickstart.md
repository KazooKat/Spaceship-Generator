# Quickstart

A 5-minute getting-started guide for the Spaceship Generator. Walks through install, first ship, palette swap, preset use, and the web UI.

For the full CLI flag reference see [cli.md](cli.md). For the palette catalog see [palettes.md](palettes.md). For the preset catalog see [presets.md](presets.md). For the HTTP API see [web_ui.md](web_ui.md).

## 1. Install

Requires Python 3.11+.

```bash
git clone https://github.com/KazooKat/Spaceship-Generator.git
cd Spaceship-Generator
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
```

## 2. Generate your first ship

Run the CLI with a fixed seed so the output is reproducible:

```bash
spaceship-generator --seed 42
```

Output: `out/ship_42.litematic`. Copy that file into `.minecraft/schematics/` and load it from Litematica's `Load Schematic` menu in-game.

## 3. Swap the palette

Pick a different block palette with `--palette NAME`. Run `--list-palettes` to see all 51 shipped palettes, or browse the catalog in [palettes.md](palettes.md).

```bash
spaceship-generator --seed 42 --palette cyberpunk_neon
spaceship-generator --seed 42 --palette random
```

`random` picks a palette at generation time so each run varies.

## 4. Use a preset

Presets bundle hull, engine, wing, cockpit, and weapon parameters under a single archetype name (`corvette`, `gunship`, `scout`, ...). Run `--list-presets` to see all 9, or browse the catalog in [presets.md](presets.md).

```bash
spaceship-generator --seed 42 --preset corvette --palette sci_fi_industrial
spaceship-generator --seed 42 --preset capital_carrier --palette gold_imperial
```

Individual style flags (e.g. `--hull-style`, `--engines`) override preset values when explicitly set.

## 5. Launch the web UI

The Flask app gives you the same generator with a browser form, isometric WebGL preview, and one-click `.litematic` download.

```bash
flask --app spaceship_generator.web.app run
```

Open `http://127.0.0.1:5000`, fill in the form, and download your ship. The full HTML page list and `/api/*` JSON route reference lives in [web_ui.md](web_ui.md).

## 6. Running a fleet

Pass `--fleet-count N` to build a batch of ships in a single invocation. Each ship gets a deterministic per-ship seed derived from a single `random.Random(--seed)` stream, so the whole fleet is reproducible from one master seed.

```bash
python -m spaceship_generator --fleet-count 3 --seed 42 --out fleet_out
```

Output filenames follow the convention `ship_<seed>_<idx>.litematic`, where `<seed>` is the per-ship seed pulled from the master stream and `<idx>` is the zero-based fleet index. Re-running with the same `--seed` and `--out` overwrites the previous fleet.

For the full fleet flag pack (`--fleet-size-tier`, `--fleet-style-coherence`, ...) see [cli.md](cli.md). For the underlying batch driver and per-ship seed/dims/style planning, see the [Fleet pipeline](architecture.md#fleet-pipeline) section in `docs/architecture.md`.

## Next steps

- Browse the full biome palette catalog in [palettes.md](palettes.md) — every shipped palette grouped by theme (industrial, biome, holiday, ...) with preview swatches and intended use cases.
- Use a [preset](presets.md) for one-shot config — preset names like `corvette`, `gunship`, `capital_carrier` bundle hull / engine / wing / cockpit / weapon parameters into a single archetype so you don't have to tune every flag yourself.
- Skim [recipes.md](recipes.md) for a task-oriented index of common workflows — fleet runs, palette validation, `--meta-json` discovery, `--output-json | jq` extraction, cross-axis test debugging, and more.
- Browse the full CLI flag list in [cli.md](cli.md) — fleet mode, manifest export, preview rendering, weapon scatter, texture knobs, machine-readable list flags, and the rest of the surface.
- Read [architecture.md](architecture.md) for the pipeline overview — how the Shape / Hull / Wing / Greeble / Weapon / Cockpit / Engine / Structure / Fleet / Texture pipelines fit together end-to-end.
- Drop a YAML file in `palettes/` to ship your own palette — see [palette_authoring.md](palette_authoring.md) for the schema.
