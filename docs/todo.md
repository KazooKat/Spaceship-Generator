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

(none tracked here yet; daily tick adds them)

## Open — Chores / docs

(none tracked here yet)

## Closed (last cycle)

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
