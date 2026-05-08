# Recipes

Task-oriented index of common usage snippets — copy-paste a one-liner for
the job you're doing. For a 5-minute walk through install + first ship see
[quickstart.md](quickstart.md); for the per-flag CLI reference see
[cli.md](cli.md); for the HTTP API see [web_ui.md](web_ui.md).

## CLI

### Recipe 1 — Generate one ship from a fixed seed

Reproducible single-ship build. Same seed always produces the same ship.

```bash
spaceship-generator --seed 42 --palette sci_fi_industrial --out ./out
```

### Recipe 2 — Generate a coherent fleet of 5 ships

`--fleet-count` picks a mix of size tiers and writes each as
`ship_<seed>_<i>.litematic`. Tune cohesion via `--fleet-style-coherence`.

```bash
spaceship-generator --seed 0 --fleet-count 5 --palette sci_fi_industrial
```

### Recipe 3 — List every available palette, preset, and shape style

Discovery commands. All exit 0 and print to stdout.

```bash
spaceship-generator --list-palettes
spaceship-generator --list-presets
spaceship-generator --list-shape-styles
```

### Recipe 4 — Lint every palette before committing

Linter exits 0 if all clean / 1 if any error. Add `--strict` to treat
warnings as errors. Useful as a pre-commit gate.

```bash
python scripts/palette_lint.py --all --strict
```

### Recipe 5 — Validate a single palette YAML

Schema + role-coverage check on one file (e.g. before opening a PR for a
new palette). Prints `OK` and exits 0 on success.

```bash
spaceship-generator --validate-palette palettes/sci_fi_industrial.yaml
```

### Recipe 6 — Use the JSON list-flag family for tooling

Every `--list-*` flag has a `--list-*-json` sibling that emits a single
machine-readable JSON document. Pipe into `jq` for downstream tooling.

```bash
spaceship-generator --list-palettes-json | jq '.palettes[]'
```

### Recipe 7 — Run the perf bench snapshot

Umbrella driver that times every bench script under `scripts/`. Add
`--csv` for spreadsheet-ingestable output.

```bash
python scripts/bench_summary.py --iterations 5
```

## Web API

The Flask app must be running for the curl recipes below:

```bash
flask --app spaceship_generator.web.app run
```

### Recipe 8 — Compare two seeds without writing files

Returns side-by-side metadata for two seeds under the same palette — no
`.litematic` files written, no rate-limit cost beyond the standard
request.

```bash
curl -s 'http://127.0.0.1:5000/api/compare?seed_a=1&seed_b=2&palette=sci_fi_industrial'
```

### Recipe 9 — Spin the wheel via `/api/random`

Returns a random `seed` / `palette` / `preset` combo as JSON. Pass
`?seed=N` to make the choice deterministic for sharable links.

```bash
curl -s http://127.0.0.1:5000/api/random
```

### Recipe 10 — Generate a ship via the JSON API

`POST /api/generate` with a JSON body. Response includes `download_url`,
`preview_url`, and `gen_id` — fetch the `.litematic` from `download_url`.

```bash
curl -X POST http://127.0.0.1:5000/api/generate \
    -H 'Content-Type: application/json' \
    -d '{"seed":42,"palette":"sci_fi_industrial"}'
```

### Recipe 11 — Diff two palettes

Role-by-role diff between two palette YAMLs. Useful when porting one
palette's accent role over to another, or auditing role drift between a
biome variant and its base. See [palette_authoring.md](palette_authoring.md).

```bash
python scripts/palette_diff.py palettes/desert_oasis.yaml palettes/foggy_marsh.yaml
python scripts/palette_diff.py --csv palettes/desert_oasis.yaml palettes/foggy_marsh.yaml
```

### Recipe 12 — Audit my palette corpus

Cross-corpus stats over `palettes/*.yaml` — role coverage, block
diversity, most-referenced blocks. Run after adding a palette to
confirm role coverage and block diversity are healthy. See
[palette_authoring.md](palette_authoring.md).

```bash
python scripts/palette_stats.py
python scripts/palette_stats.py --csv
python scripts/palette_stats.py --top 5
```

### Recipe 13 — Check the server version programmatically

Two parallel paths for fetching the installed version: `GET /api/version`
for a running web client, and `--version-json` for shell pipelines
without a server. Both emit the same `{"version": "..."}` document. See
[web_ui.md](web_ui.md), [cli.md](cli.md).

```bash
curl http://localhost:5000/api/version
python -m spaceship_generator --version-json
```

### Recipe 14 — Run benchmarks for CI

Every `scripts/bench_*.py` script has a `--csv` flag for spreadsheet /
CI ingest; `bench_summary.py --csv` is the umbrella driver that emits
one row per child bench. See [bench.md](bench.md), [bench-ci.md](bench-ci.md).

```bash
python scripts/bench_summary.py --csv > bench-summary.csv
python scripts/bench_palette.py --csv > bench-palette.csv
python scripts/bench_shape.py --csv > bench-shape.csv
```

### Recipe 15 — Find every palette referencing a Minecraft block id

Cross-corpus search of `palettes/*.yaml` for a given block id, printed
as a `(palette, role)` table. Blockstate suffixes (`[facing=north,...]`)
are stripped before comparison so variants of the same block all match.
Add `--csv` for spreadsheet / CI ingest (banner routed to stderr). See
[palette_authoring.md](palette_authoring.md).

```bash
python scripts/palette_search.py --block minecraft:deepslate
python scripts/palette_search.py --block minecraft:deepslate --csv
```

### Recipe 16 — Run a single cross-axis property test

Cross-axis property tests live in `tests/test_properties.py` named
`test_property_<axis_a>_x_<axis_b>_seed_grid_*`. Use `pytest -k` to
run just one pairing (27 nodes per pair) instead of the full suite —
useful when a regression localizes to a specific interaction.

```bash
pytest -q -k engine_style_x_wing
pytest -q -k cockpit_x_hull
pytest -q -k palette_x_cockpit_style
```

### Recipe 17 — Jump to one component's pipeline in the architecture doc

`docs/architecture.md` opens with a [Per-component pipelines](architecture.md#per-component-pipelines)
anchor index linking each `## <Component> pipeline` section
(Shape / Hull / Wing / Greeble / Weapon / Cockpit / Engine / Structure).
Open the index and click through to the component you want instead of
scrolling — each section is self-contained with its own Mermaid diagram.

```bash
python -c "import webbrowser; webbrowser.open('docs/architecture.md#per-component-pipelines')"
```

### Recipe 18 — Validate every authored palette before commit

Whole-corpus form of the palette linter — runs `palette_lint.py` over
every `palettes/*.yaml` in one invocation and exits 1 if any palette
errors. Add `--strict` to treat warnings as errors so the pre-commit
gate catches mandatory-role gaps and unknown-block ids too.

```bash
python scripts/palette_lint.py --all --strict
```

### Recipe 19 — Discover every enum / palette / preset in one call

`--meta-json` emits a single JSON document combining every payload the
`--list-*-json` family emits (palettes, presets, hull/engine/wing/cockpit/
structure styles, greeble types, weapon types, roles, version) — one
subprocess instead of ten. Mirror of the web `/api/meta` endpoint.

```bash
python -m spaceship_generator --meta-json | jq 'keys'
```

### Recipe 20 — Batch a fleet from one master seed

`--fleet-count N` derives every per-ship seed from a single
`random.Random(--seed)` stream, so the whole fleet is reproducible from
one master seed. Outputs land at `ship_<seed>_<idx>.litematic`. See
[Fleet pipeline](architecture.md#fleet-pipeline) for the underlying
batch driver.

```bash
python -m spaceship_generator --fleet-count 20 --seed 42 --out fleet_out
```

### Recipe 21 — Extract ship metadata in shell scripts via `--output-json`

`--output-json` prints one JSON summary per generated ship to stdout
(filename, seed, palette, dims, blocks). Pipe into `jq` for tab-
separated rows usable in `awk` / spreadsheets. Errors stay on stderr
(do not `2>&1`) so the stream-split convention stays clean.

```bash
python -m spaceship_generator --output-json --seed 42 --palette sci_fi_industrial --out out/ \
    | jq -r '"\(.seed)\t\(.palette)\t\(.blocks)"'
```

### Recipe 22 — Wire palette lint into a CI gate as JSON

`palette_lint.py --all --format json` emits one machine-readable
document over every `palettes/*.yaml` with per-palette error / warning
arrays — ingest in CI to fail builds on regressions and post structured
annotations. Cross-link `feat-scripts-palette-lint-json` once shipped.

```bash
python scripts/palette_lint.py --all --format json | jq '.[] | select(.errors | length > 0)'
```

## See also

- [quickstart.md](quickstart.md) — 5-minute getting-started walk
- [cli.md](cli.md) — full per-flag CLI reference
- [web_ui.md](web_ui.md) — HTML page + `/api/*` route reference
- [configuration.md](configuration.md) — config-by-category index
- [troubleshooting.md](troubleshooting.md) — common failures + one-line fixes
- [faq.md](faq.md) — common-question reference
