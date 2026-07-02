# Structured-Massing Generator v2 — Design Spec

Date: 2026-07-01
Status: Approved (user approved design in session; full delegation on details)

## Problem

Current ships read as lumpy noise blobs, not spaceships. User verdict: "ships
too simple and pieces don't fit together — nobody would use the current app."

Confirmed root causes (file:line refs against pre-rebuild code):

1. Hull is a quantized ellipsoid-of-revolution (`shape/hull.py` `_place_hull`)
   — jagged staircase rings, no flat surfaces, silhouette reads as blob.
2. Greebles are random single-voxel bumps on 5% of surface cells
   (`shape/greebles.py`) — surface acne, not machinery.
3. Wings span `W//5` (~4 blocks) (`shape/wings.py:24`) — tiny, buried or
   float as plus-signs in previews.
4. Engines are small cylinders stamped *inside* the rear hull volume
   (`shape/engines.py`) — invisible from outside.
5. Texture pass sprinkles windows randomly — blue speckle everywhere.
6. `_connect_floaters` bridges islands with 1-voxel lines
   (`shape/assembly.py:130`) — spindly "pieces don't fit" connections.

## Goal

Ships that read as deliberate spacecraft: legible silhouette, visible engines,
a cockpit that looks like a cockpit, wings that grow out of the hull,
machinery-like surface detail, window rows.

## Non-goals

- No change to CLI flags, web routes, palette YAML schema, export formats,
  preset names, or the public `generate_shape(seed, params, ...)` signature.
- No byte-compatibility with old seeds. Same seed → different (better) ship.
  User explicitly accepted this.

## Scope

**Keep as-is:** CLI, web UI, palettes, export, presets, preview renderer,
docs structure, test infra, CI.

**Replace:** the whole shape stage (`shape/*.py` placement logic) and the
window/detail portion of the texture pass.

## Architecture

### 1. Blueprint stage (new module `shape/blueprint.py`)

RNG first builds an explicit `ShipPlan` dataclass — the single source of
truth every placement function reads:

- 2–4 hull segments (nose / cockpit / mid / engine), each with Z-extent and
  cross-section half-width/half-height.
- Wing config: style, root Z, root chord, span, thickness, vertical anchor.
- Engine config: style, nozzle count/radius, optional side-nacelle pods with
  pylon cross-section.
- Cockpit config: style, deck rectangle it occupies.

Parts read the plan instead of guessing → alignment by construction.

### 2. Hull massing (`shape/hull.py` rewrite)

- Superellipse cross-section (exponent ≈ 4: rounded rectangle) → flat side
  panels, flat top deck, chamfered corners.
- Per-segment sizes with stepped transitions between segments (1–2 voxel
  shoulder steps, not smooth blends).
- Nose segment tapers to wedge or point per hull style.
- Existing 10 `HullStyle` values remap to massing parameter sets (segment
  count, cross-section exponents, taper curves, asymmetry flags).

### 3. Cockpit (`shape/cockpit.py` rewrite)

- Recessed glass canopy set into flat nose deck with a 1-block hull frame,
  or a raised bridge block with a window strip — per existing
  `CockpitStyle` values remapped.
- Always framed by hull; never a floating glass blob.

### 4. Engines (`shape/engines.py` rewrite)

- Engine segment ends in a flat rear wall; nozzles protrude 2–4 voxels with
  a hull rim ring and recessed `ENGINE_GLOW` core.
- Nozzle radius ~W/6 (visible at preview scale).
- Optional side nacelles: separate pods connected by 2–3-voxel-thick pylons
  anchored at hull midline.
- Existing 9 `EngineStyle` values remapped onto nozzle-layout variants.

### 5. Wings (`shape/wings.py` rewrite)

- Root embedded ≥2 voxels into hull; thickness ≥2 at root, tapering
  outboard; span 1.0–1.6× hull width.
- Existing 6 `WingStyle` planforms kept as outline generators.

### 6. Greebles (`shape/greebles.py` rewrite)

- Pick K rectangular patches on flat hull faces; fill each with structured
  detail: raised panel outlines, vent rows, pipe runs, antenna/turret
  clusters (top deck only).
- `greeble_density` now scales patch count/size. Zero single-voxel scatter.

### 7. Texture pass (`texture.py` partial rewrite)

- Windows: horizontal rows along mid-hull sides at consistent Y, in spaced
  runs (e.g. 3-on 1-off), only on flat side panels.
- Accent stripe along the chine (hull corner line).
- Engine glow / running lights logic retained where it already works.

### 8. Assembly (`shape/assembly.py` update)

- Connectivity by construction — every part anchors to a planned hull face.
- `_connect_floaters` kept as safety net, upgraded to 2×2 struts.
- X-mirror symmetry pass unchanged.

## Testing & verification gate

- Byte-exact golden tests updated to new outputs.
- Property tests stay green: X-symmetry, determinism (same seed+params →
  identical grid), single connected component, role validity, bounds.
- New property: every non-hull part voxel is 6-connected to hull.
- `pytest` full suite green (baseline recorded before work starts).
- Regenerate `docs/gallery` and visually inspect across seeds × hull styles
  × engine styles — ships must read as spacecraft.

## Risks

- 10 hull × 9 engine × 6 wing styles is a large remap surface; mitigate by
  building the core massing path first, then remapping styles in batches
  with gallery checks per batch.
- Presets tuned for old generator may need proportion re-tuning.
