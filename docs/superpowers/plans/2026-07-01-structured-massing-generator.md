# Structured-Massing Generator v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blob-ellipsoid ship generator with a blueprint-driven structured-massing generator so outputs read as deliberate spacecraft.

**Architecture:** A new `shape/blueprint.py` builds an explicit `ShipPlan` (segments, cockpit, engines, wings) from the RNG first; every placement module reads the plan instead of guessing geometry. Hull uses superellipse cross-sections (flat panels + chamfered corners) over 3–4 Z-segments. Parts anchor to planned hull faces so connectivity holds by construction.

**Tech Stack:** Python 3.11+, numpy, existing pytest suite (hypothesis property tests), matplotlib preview.

## Global Constraints

- Public API unchanged: `generate_shape(seed, params, *, hull_style=..., hull_style_front=..., hull_style_rear=..., hull_blend_midband=...)` signature stays; `Role` enum values stay; palette YAML schema stays; CLI flags stay.
- Same seed + params → deterministic identical grid (property tests enforce).
- X-mirror symmetry after assembly (property tests enforce).
- Final ship = single 6-connected component.
- Test baseline (recorded 2026-07-01, pre-rebuild): **5 failed, 2893 passed**. Pre-existing failures (environmental, CLI-runner): `test_cli.py::test_seed_phrase_deterministic`, `test_cli_extra.py::test_dunder_main_executes_cli`, `test_cli_extra.py::test_list_weapon_types`, `test_cli_extra.py::test_dry_run_prints_json_seed_and_no_file_written`, `test_cli_extra.py::test_greeble_style_valid_type_exits_zero`. Gate for every task: failures stay exactly this set (plus intentionally-updated golden tests mid-rewrite, which must be fixed within the same task).
- Run tests with: `& ".venv\Scripts\python.exe" -m pytest tests -q --tb=short` from the `Spaceship Generator` directory.
- Visual gate at the end of hull/engine/wing/greeble tasks: render previews for seeds {1, 42, 1234, 99999} and inspect.

---

### Task 1: Blueprint module

**Files:**
- Create: `src/spaceship_generator/shape/blueprint.py`
- Test: `tests/test_blueprint.py`

**Interfaces:**
- Consumes: `ShapeParams`, `CockpitStyle` from `shape/core.py`; `HullStyle`, `StructureStyle` from `structure_styles.py`; `WingStyle` from `wing_styles.py`.
- Produces (later tasks rely on these exact names):
  - `HullSegment(z0: int, z1: int, half_w0: float, half_h0: float, half_w1: float, half_h1: float, exponent: float, y_center: float)`
  - `CockpitPlan(style: CockpitStyle, z0: int, z1: int, half_w: int)`
  - `EnginePlan(wall_z: int, nozzle_xs: tuple[int, ...], nozzle_y: int, radius: int, nacelles: bool, nacelle_half_w: int, nacelle_half_h: int, nacelle_z0: int, nacelle_z1: int, nacelle_cx_off: int)`
  - `WingPlan(present: bool, style: WingStyle, root_z: int, root_chord: int, span: int, thickness: int, y_anchor: int)`
  - `ShipPlan(segments: tuple[HullSegment, ...], cockpit: CockpitPlan, engine: EnginePlan, wing: WingPlan)` with method `hull_half_at(z: int) -> tuple[float, float, float, float]` returning `(half_w, half_h, exponent, y_center)`.
  - `build_plan(rng: np.random.Generator, params: ShapeParams, hull_style: HullStyle | None) -> ShipPlan`
  - `MASSING: dict[HullStyle, MassingConfig]` — per-style config: `MassingConfig(width_frac, height_frac, exponent, nose_frac, tail_frac, nose_tip_frac, wing_bias, nacelle_prob)`.

**Key geometry rules `build_plan` must implement:**
- Hull occupies only ~`width_frac` (0.30–0.42 typical) of grid W as half-width, leaving outer X for wings/nacelles.
- Segments rear→front: engine `[wall_z, ~0.25L)`, mid `[~0.25L, ~0.62L)`, fore `[~0.62L, ~0.85L)`, nose `[~0.85L, L)` shrinking to `nose_tip_frac`.
- `wall_z = max(2, L // 12)` — hull starts there; nozzles protrude into `[0, wall_z)`.
- Segment sizes step: fore = mid × ~0.85, engine = mid × ~0.9; per-seed jitter ±8% from `rng`.
- Nozzle radius `max(2, int(hull_half_h * 0.55))`; count from `params.engine_count` via existing `engine_count_override`; positions symmetric within hull half-width.
- Wing: `span = int(W/2 - hull_half_w) - 1` (to grid edge minus margin), `root_chord ≈ L//4`, `thickness = max(2, H//6)`, `root_z ≈ 0.30L ± jitter`, `y_anchor = mid deck line`.
- Cockpit: strip on fore-segment deck, `z0/z1` inside fore segment, `half_w = max(1, int(hull_half_w * 0.45))`.

- [ ] Step 1: write failing tests: `build_plan` deterministic for same rng seed; segments cover `[wall_z, L)` contiguously; `hull_half_at` continuous inside segments; wing span leaves ≥1 margin to grid edge; every `HullStyle` has a `MASSING` entry.
- [ ] Step 2: run tests, verify fail (module missing).
- [ ] Step 3: implement module.
- [ ] Step 4: run tests, verify pass.
- [ ] Step 5: commit `feat(shape): blueprint stage — explicit ShipPlan drives all placement`.

### Task 2: Hull massing rewrite

**Files:**
- Modify: `src/spaceship_generator/shape/hull.py` (replace `_place_hull`; adapt `_place_hull_blend`), `src/spaceship_generator/shape/core.py` (`generate_shape` builds plan, passes to placers)
- Test: `tests/test_shape.py` (update geometry assertions), `tests/test_blueprint.py`

**Interfaces:**
- Consumes: `ShipPlan.hull_half_at(z)`.
- Produces: `_place_hull(grid, rng, params, plan)` — fills superellipse cross-sections `|dx/half_w|^n + |dy/half_h|^n <= 1` for `z in [wall_z, L)`. `generate_shape` now calls `build_plan` first and threads `plan` to every placer. `hull_style_front`/`hull_style_rear` blend = interpolate the two styles' `MassingConfig` fields over the midband instead of `blended_hull_radii`.

- [ ] Step 1: failing test — hull cross-section at mid-Z has flat side panel (≥3 consecutive same-x surface cells along y) and flat deck (≥3 consecutive same-y top cells along x); hull half-width ≤ `W * 0.45`.
- [ ] Step 2: verify fail.
- [ ] Step 3: implement; keep `apply_hull_style` import path alive (may delegate to new massing).
- [ ] Step 4: full suite; update broken geometry goldens in `tests/test_shape.py` to new expectations within this task.
- [ ] Step 5: render seeds {1, 42, 1234, 99999} previews to scratchpad; inspect silhouette.
- [ ] Step 6: commit `feat(shape): superellipse segmented hull massing`.

### Task 3: Engine rewrite

**Files:**
- Modify: `src/spaceship_generator/shape/engines.py`
- Test: `tests/test_shape.py`

**Interfaces:**
- Consumes: `plan.engine` (`EnginePlan`).
- Produces: `_place_engines(grid, rng, params, plan)` — flat rear wall at `wall_z` (hull already there); nozzle cylinders (role ENGINE) protruding `[0, wall_z)`, radius `plan.engine.radius`, ring rim of HULL one voxel around each nozzle at `wall_z` face; optional nacelle pods (HULL boxes `nacelle_half_w/h` at `±nacelle_cx_off`) with 2-voxel-thick pylons connecting to hull.

- [ ] Step 1: failing test — for default params some ENGINE voxels exist at `z < wall_z` (outside hull) and none float (each ENGINE voxel 6-connected to hull component after assembly).
- [ ] Step 2: verify fail. Step 3: implement. Step 4: suite green (update goldens same-task). Step 5: preview inspect. Step 6: commit `feat(shape): protruding nozzle engines + nacelle pods`.

### Task 4: Wing rewrite

**Files:**
- Modify: `src/spaceship_generator/shape/wings.py`
- Test: `tests/test_shape.py`, `tests/test_wing_styles.py`

**Interfaces:**
- Consumes: `plan.wing`; existing `wing_styles.place_wings(grid, style, span=..., thickness=..., length=..., cy=..., cz=..., y_lo=..., y_hi=...)` outline generators reused.
- Produces: `_place_wings(grid, rng, params, plan)` — wing box starts `2` voxels *inside* hull surface (root embedded), span from `plan.wing.span`, thickness ≥2 at root with 1-voxel taper outboard half.

- [ ] Steps: failing test (wing voxels overlap hull-occupied x-range by ≥2 columns; span ≥ `0.8 * plan.wing.span`), fail, implement, suite green + goldens, preview inspect, commit `feat(shape): rooted proportional wings`.

### Task 5: Cockpit rewrite

**Files:**
- Modify: `src/spaceship_generator/shape/cockpit.py`
- Test: `tests/test_shape.py`

**Interfaces:**
- Consumes: `plan.cockpit`.
- Produces: `_place_cockpit(grid, rng, params, plan)` — for each style: glass strip recessed into deck (replace top hull row inside cockpit rect) with 1-voxel HULL frame kept on all 4 sides, or raised bridge (2-voxel hull block + glass strip on its front face). Every glass voxel must have ≥2 HULL/INTERIOR 6-neighbors (framed).

- [ ] Steps: failing test (frame rule above; glass confined to `plan.cockpit` rect), fail, implement all 6 `CockpitStyle` variants as strip/bridge/dome-on-frame variants, suite green + goldens, preview inspect, commit `feat(shape): framed deck cockpits`.

### Task 6: Greeble rewrite

**Files:**
- Modify: `src/spaceship_generator/shape/greebles.py`
- Test: `tests/test_shape.py`

**Interfaces:**
- Consumes: `plan` (deck/side rectangles derived from segments).
- Produces: `_place_greebles(grid, rng, params, plan)` — chooses `K = round(density * 40)` rect patches (3–8 × 2–5) on flat deck/side faces of mid+engine segments; per patch one motif: `panel_outline` (GREEBLE border ring), `vent_row` (alternating GREEBLE columns), `pipe_run` (1-wide GREEBLE line along z, 2 long bumps), `antenna_cluster` (deck only: 1×1 GREEBLE masts height 2–4). No isolated single-voxel placements anywhere.

- [ ] Steps: failing test (every GREEBLE voxel has ≥1 GREEBLE or ≥2 filled 6-neighbors — no scatter; zero GREEBLEs when density 0), fail, implement, suite green + goldens, preview inspect, commit `feat(shape): clustered greeble patches`.

### Task 7: Window rows + texture polish

**Files:**
- Modify: `src/spaceship_generator/texture.py` (`_paint_windows` only)
- Test: `tests/test_texture.py`

**Interfaces:**
- Consumes: role grid (no plan — texture stays shape-agnostic).
- Produces: `_paint_windows` v2 — windows only on side-facing HULL surface cells in a single row `y = cy + 1` (fallback `cy`), pattern `z % 5 in {1, 2}` (2-on-3-off runs), only where ≥2 consecutive z-cells qualify (kills isolated speckle).

- [ ] Steps: failing test (all WINDOW voxels share one y; runs length ≥2), fail, implement, suite green + goldens, commit `feat(texture): window rows replace speckle`.

### Task 8: Assembly struts + integration sweep

**Files:**
- Modify: `src/spaceship_generator/shape/assembly.py` (`_draw_line_hull` → 2×2 strut), `src/spaceship_generator/shape/core.py` (final orchestration order)
- Test: `tests/test_properties.py` (new property: every non-hull part voxel 6-connected to main component), full suite.

- [ ] Steps: failing property test, fail, implement strut upgrade, run FULL suite — gate: exactly the 5 pre-existing failures, commit `feat(shape): 2x2 bridge struts + part-connectivity property`.

### Task 9: Style remap verification + gallery + docs

**Files:**
- Modify: `docs/architecture.md` (pipeline description), `README.md` (pipeline diagram line), regenerate `docs/gallery/*.png` via `scripts/gen_gallery.py`
- Test: visual.

- [ ] Steps: render grid of hull styles × seeds to scratchpad, inspect each of 10 hull styles reads distinctly; regenerate gallery; update docs; full suite; commit `docs: v2 generator gallery + architecture update`.

## Self-review notes

- Spec §1–8 → Tasks 2,5,3,4,6,7,8 + blueprint Task 1; gallery/verification → Task 9. Covered.
- Golden-test churn is folded into each geometry task (fix within task, never leave red between tasks).
- `generator.py` engine_style override path untouched (writes into `[0, L//8)` region which remains outside hull wall) — verified compatible by full-suite gate each task.
