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

### Recipe 23 — Palette lint CI gate via `--json --all`

`palette_lint.py --json --all` emits a JSON array (one object per palette
with `ok` / `errors` / `warnings`) and exits 1 if any palette is dirty.
Wrap it in a shell gate so CI fails fast on regressions.

```bash
python scripts/palette_lint.py --json --all > lint.json || \
    { jq -r '.[] | select(.ok==false) | "\(.palette): \(.errors|join(", "))"' lint.json; exit 1; }
```

### Recipe 24 — Extract palette names and version from `--meta-json`

`--meta-json` emits one combined JSON document — pipe to `jq` to pull
just the fields tooling needs (e.g. palette names + version) instead of
ten separate `--list-*-json` subprocesses.

```bash
python -m spaceship_generator --meta-json | jq '{version, palettes: .palettes[].name}'
```

### Recipe 25 — Tune Texture pipeline knobs

`--window-period` / `--stripe-period` / `--engine-glow-depth` plumb into
`TextureParams` in the [Texture pipeline](architecture.md#texture-pipeline)
to dial window cadence, accent-stripe period, and engine glow recess
depth without editing palette YAML.

```bash
spaceship-generator --seed 42 --palette sci_fi_industrial \
    --window-period 4 --stripe-period 6 --engine-glow-depth 2 --out ./out
```

### Recipe 26 — Debug a cross-axis property test failure

When a cross-axis test in [tests/test_properties.py](../tests/test_properties.py)
fails, re-run just that pair with `-v` so the offending parametrize tuple
`(axis_a, axis_b, seed)` prints in the failure header — much faster than
the full ~700-test suite. See Recipe 16 for the naming convention.

```bash
pytest -k engine_style_x_wing -v
```

### Recipe 27 — Diff-only palette lint CI gate

Fail CI only on lint errors *introduced* by the current branch — capture
`palette_lint.py --all --json` at merge-base and HEAD, then `jq` for palettes newly flipped to `ok==false` so a dirty corpus does not block unrelated PRs.

```bash
git stash && git checkout "$(git merge-base HEAD origin/main)" && \
    python scripts/palette_lint.py --all --json > /tmp/base.json && git checkout - && git stash pop && \
    python scripts/palette_lint.py --all --json > /tmp/head.json && \
    jq -s '.[1] - .[0] | map(select(.ok==false))' /tmp/base.json /tmp/head.json
```

### Recipe 28 — Scaffold a new cross-axis property test

Drop-in template for adding one more `(axisA × axisB × seed)` pairing to
`tests/test_properties.py` — reuses `_slice_first_middle_last` and `_SHAPE_STYLE_STABILITY_SEEDS` so the new test costs exactly 27 nodes.

```python
_AX_A = _slice_first_middle_last(list(AxisA))
_AX_B = _slice_first_middle_last(list(AxisB))
@pytest.mark.parametrize("a", _AX_A, ids=lambda v: v.name)
@pytest.mark.parametrize("b", _AX_B, ids=lambda v: v.name)
@pytest.mark.parametrize("seed", _SHAPE_STYLE_STABILITY_SEEDS)
def test_property_axisa_x_axisb_seed_grid(tmp_path, a, b, seed):
    out = tmp_path / f"{a.name}_{b.name}_{seed}.litematic"
    generate(seed=seed, out_path=out, axis_a=a, shape_params=ShapeParams(axis_b=b))
    assert out.exists() and out.stat().st_size > 0
```

### Recipe 29 — Combined `--meta-json` + `--output-json` pipeline

Capture the discovery bundle and per-ship summary in one pipeline, then tool
both in a single `jq` pass — pins palette/version context alongside the ship for reproducible run reports.

```bash
python -m spaceship_generator --meta-json > meta.json && \
    python -m spaceship_generator --output-json --seed 42 --palette sci_fi_industrial --out out/ > ship.json && \
    jq -n --slurpfile m meta.json --slurpfile s ship.json '{version: $m[0].version, ship: $s[0]}'
```

### Recipe 30 — Auto-generate a tooling map from the cross-link table

Mine the `## Cross-link index` table in `docs/architecture.md` into a JSON
`{section: [cli, api]}` map for IDE tooling — `grep` the `| [Section]` rows then `awk` over the pipe-delimited columns.

```bash
grep -E '^\| \[' docs/architecture.md | awk -F '\\|' '{gsub(/^ +| +$/,"",$2); gsub(/^ +| +$/,"",$3); gsub(/^ +| +$/,"",$4); printf "\"%s\": [\"%s\", \"%s\"],\n", $2, $3, $4}' | sed '1s/^/{/; $s/,$/}/'
```

### Recipe 31 — Capture an exact CLI invocation as a config bundle

`--config-dump` emits the resolved generator-relevant args (post `--preset`
and `--palette random` resolution) as one JSON document and exits 0 without
producing a ship. Redirect to a file to share the exact reproducible
invocation with a collaborator alongside a bug report or gallery entry.

```bash
python -m spaceship_generator --seed 42 --preset gunship --palette random --config-dump > ship_config.json
```

### Recipe 32 — Replay a saved manifest plus extra overrides

`--from-manifest FILE` reproduces a ship from an `--export-manifest` JSON
sidecar (seed, palette, dims). It is mutually exclusive with `--seed` /
`--seeds` / `--seed-phrase` / `--repeat` / `--fleet-count`, but every other
flag (palette overrides via re-pass, greeble density, styles) still layers
on top — useful for "same shape, different paint".

```bash
python -m spaceship_generator --from-manifest ship_42.json --greeble-density 0.0 --no-weapons --out replay/
```

### Recipe 33 — Mass-generate one ship per biome-pack palette in a loop

Iterate over a list of biome-pack palette names and write one ship per
palette under a per-palette subdirectory. Reuse the same `--seed` so every
ship shares its silhouette and only the palette-driven block mapping
varies — handy for side-by-side palette gallery shots.

```bash
for p in arcane_library mistwood_grove obsidian_forge prismatic_reef shadow_citadel golden_savannah; do \
    python -m spaceship_generator --seed 42 --palette "$p" --out "out/$p/"; \
done
```

### Recipe 34 — Run a single cross-axis test node by parametrize id

`pytest -k` matches against the parametrize id, not just the function
name — combine `<test_name> and <id>` to drill down to one of the 27 nodes
in a cross-axis grid. Test ids read `[seed-axis_b-axis_a]` (outermost
parametrize first), e.g. `[0-arrow-abyss_deep]` for the palette × hull
cross-axis test. Pair with `-v` so the parametrize tuple prints in the
failure header.

```bash
pytest -q -v -k 'palette_x_hull_style and 0-arrow-abyss_deep'
```

## See also

- [quickstart.md](quickstart.md) — 5-minute getting-started walk
- [cli.md](cli.md) — full per-flag CLI reference
- [web_ui.md](web_ui.md) — HTML page + `/api/*` route reference
- [configuration.md](configuration.md) — config-by-category index
- [troubleshooting.md](troubleshooting.md) — common failures + one-line fixes
- [faq.md](faq.md) — common-question reference
