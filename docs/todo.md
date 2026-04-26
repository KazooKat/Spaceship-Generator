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

- [ ] shapes-B-hull-blend: blend two hull profiles along Z (e.g. front=arrow + rear=saucer)
      scope: `structure_styles.py` (blend helper), `shape/hull.py`, `shape/core.py` (params), CLI
      accept: `--hull-style-front X --hull-style-rear Y` flag, deterministic per seed, smooth crossover region; tests cover blend boundaries; gallery example
      notes: cheapest of the bunch — start here; useful as warm-up for the larger items

- [ ] shapes-C-csg: CSG operations on primitives (union/subtract/intersect of cylinders, ellipsoids, boxes)
      scope: new `src/spaceship_generator/shape/csg.py`, `shape/hull.py` (call sites), tests
      accept: ring-spine / hangar-bay cutout / hollow torus achievable via composed primitives; primitive registry + op enum; documented in `docs/architecture.md`
      notes: voxel CSG over the int8 grid is enough — no SDF library needed; keep it numpy-vectorized

- [ ] shapes-D-modular: modular segments (N stacked modules along Z, each its own primitive, with connectors)
      scope: new `shape/modules.py`, `shape/core.py` (params)
      accept: cargo-pod + bridge + engine-block archetype; segment count + module-type list configurable; greebles still place; tests
      notes: overlaps with B and C — consider whether modular-block (existing `HullStyle.MODULAR_BLOCK`) absorbs this or stays as a stepped-profile cousin

- [ ] shapes-E-noise: procedural-noise hull distortion (asteroid-like / battle-damaged / organic irregularity)
      scope: `shape/hull.py` post-pass, `texture.py` (optional rivet/panel interplay), CLI flag
      accept: `--hull-noise AMPLITUDE` toggles 3D-noise displacement on the hull membrane; deterministic per seed; tests; gallery sample
      notes: cheap perlin/simplex over the cell coords; clamp to keep silhouette legible

- [ ] shapes-F-other: open slot for compound-shape ideas not in A–E
      scope: TBD per concrete proposal
      accept: TBD per concrete proposal
      notes: must come with a one-paragraph design before opening a new item below this one

- [ ] feat-palettes-biome-pack-2026-04-26: add three new biome palettes (lush_caves, mangrove_swamp, pale_garden)
      scope: `palettes/*.yaml`, `tests/test_palette.py` or `tests/test_palette_lint.py` (count update only)
      accept: three new YAML palettes pass `test_palette_lint`, hull/wing/glow blocks valid; palette count test updated; loadable via `--palette NAME`
      notes: lush_caves = azalea/glow_berries; mangrove_swamp = mangrove_log/mud/mangrove_roots; pale_garden = pale_oak (1.21); follow existing palette schema

- [ ] feat-api-openapi-spec: add `GET /api/spec` endpoint returning OpenAPI 3.0 JSON schema
      scope: `src/spaceship_generator/web/` (new endpoint), `tests/test_api.py` or `tests/test_web.py`
      accept: route `/api/spec` returns `application/json` with valid OpenAPI 3.0 doc enumerating all current endpoints; test asserts shape and content-type
      notes: hand-written schema is fine — no code generation; must enumerate existing endpoints (/api/health, /api/random, /api/styles, /api/palettes, /api/presets, /api/compare, /api/fleet/plan, etc.)

- [ ] feat-docs-shape-pipeline: write architecture doc for the shape pipeline as foundation for shapes-A..E
      scope: `docs/architecture.md` only (extend existing file; do not create a new one)
      accept: new section "Shape pipeline" describes `shape/core.py`, `shape/hull.py`, `shape/assembly.py`, `shape/cockpit.py`, `shape/wings.py`, `shape/engines.py`, `shape/greebles.py` with one paragraph per module + a Mermaid or ASCII flow diagram of the build order; CHANGELOG bullet
      notes: this unblocks the bigger shape epic (A–E) by giving future agents a single place to read before touching shape code

## Open — Bugs

(none tracked here yet; daily tick adds them)

## Open — Chores / docs

(none tracked here yet)

## Closed (last cycle)

(none yet)
