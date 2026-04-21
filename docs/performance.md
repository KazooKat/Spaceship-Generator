# Performance — generator pipeline

This document records a baseline run of `scripts/bench_generator.py` and lists
the top observed bottlenecks with one-line hypotheses. It is a read-only
report; no source files were changed as part of writing it.

## Running the bench

From the repo root:

```bash
# Full run (20 ships across 3 dim presets x 4 palettes, cProfile-instrumented)
.venv/Scripts/python scripts/bench_generator.py

# Smaller run, save a baseline, then diff later
.venv/Scripts/python scripts/bench_generator.py --n 10 --save baseline.json
.venv/Scripts/python scripts/bench_generator.py --n 10 --compare baseline.json
```

Flags:

| flag | default | meaning |
|------|---------|---------|
| `--n N` | 20 | number of ships to generate |
| `--save PATH.json` | — | write current run's per-phase totals to a baseline JSON |
| `--compare PATH.json` | — | diff current run against a previously-saved baseline |
| `--top N` | 10 | top-N hottest functions printed under `tottime` |
| `--out-dir DIR` | tempdir | where to write the `.litematic` files |
| `--keep-output` | false | keep generated files (default: deleted after run) |

The bench uses only stdlib (`cProfile`, `pstats`, `tempfile`, `argparse`,
`json`, `platform`, `time`) plus the generator's existing numpy dependency.

## Baseline (this machine)

- Python: **3.14.3**
- CPU: **AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD** (via
  `platform.processor()`)
- OS: Windows 11 Home 10.0.26200
- numpy: 2.4.4
- litemapy: installed in `.venv`
- Workload: n=20 ships, dims cycled through small (24x12x8) / med (40x20x12) /
  large (64x32x18), palettes cycled through `sci_fi_industrial` /
  `stealth_black` / `nordic_scout` / `sleek_modern`.

Raw output from `scripts/bench_generator.py --n 20 --top 12`:

```
phase               total_s     mean_s     pct   hottest
------------------------------------------------------------------------------
shape_build          0.1647     0.0082   17.0%   assembly.py:20:_label_components
role_assign          0.0035     0.0002    0.4%   texture.py:115:_paint_windows
palette_lookup       0.0011     0.0001    0.1%   palette.py:129:from_dict
export               0.5320     0.0266   55.0%   schematic.py:342:to_nbt
other                0.2661     0.0133   27.5%   ~:0:<built-in method builtins.len>
------------------------------------------------------------------------------
WALL TOTAL           0.9672     0.0484 (n=20 ships)
```

Top 12 functions by `tottime` (exclusive time):

```
ncalls  tottime  percall  cumtime filename:lineno(function)
    20   0.147    0.007    0.349  litemapy/schematic.py:342(to_nbt)
    20   0.117    0.006    0.127  spaceship_generator/shape/assembly.py:20(_label_components)
304512   0.105    0.000    0.162  litemapy/storage.py:63(__setitem__)
792796   0.101    0.000    0.140  litemapy/minecraft.py:147(__eq__)
    20   0.080    0.004    0.720  spaceship_generator/export.py:13(export_litematic)
 77206   0.070    0.000    0.257  litemapy/schematic.py:666(__setitem__)
318132   0.044    0.000    0.058  {built-in method builtins.len}
 77029   0.041    0.000    0.110  {method 'index' of 'list' objects}
810767   0.041    0.000    0.041  {built-in method builtins.isinstance}
615368   0.033    0.000    0.033  {built-in method builtins.abs}
    20   0.025    0.001    0.026  spaceship_generator/shape/hull.py:12(_place_hull)
304512   0.014    0.000    0.014  litemapy/storage.py:83(__len__)
```

### Read

- At ~50 ms/ship, wall total is dominated by the **export** phase
  (~55 %). The generator's own code (shape + texture) is only ~17 %.
- The `"other"` bucket (~27 %) is almost entirely builtins (`len`,
  `isinstance`, `abs`, `list.index`) called from inside litemapy, so in
  practice export + other together account for ~82 % of wall time.
- `palette_lookup` is already negligible (0.1 %). The
  `block_state` cache inside `export_litematic` keeps it that way even at
  ~15 k filled voxels per ship.

## Observed bottlenecks

Ranked by `tottime` (exclusive time per call) on the baseline run. The
`hypothesis` column is a guess at *why* the function is hot; it has not been
confirmed by a fix.

| # | file:line | tottime | hypothesis |
|---|-----------|---------|-----------|
| 1 | `src/spaceship_generator/export.py:13` `export_litematic` + its callees in `litemapy/schematic.py:666` `Schematic.__setitem__` and `litemapy/storage.py:63` `__setitem__` | ~0.30 s (≈31 % of total) | The export loop does one Python-level `region[x,y,z] = bs` per filled voxel (~15 k voxels/ship). Each write triggers litemapy's palette-index lookup, which calls `BlockState.__eq__` against every entry of the region's block palette (that's the ~790 k `minecraft.py:147(__eq__)` calls and ~77 k `list.index` calls). Quadratic-ish in palette size * voxels. |
| 2 | `.venv/.../litemapy/schematic.py:342` `to_nbt` | ~0.15 s | Serializing the region to an NBT tree — once per ship, so this is structural overhead of the file format, not an obvious algorithmic win unless we can skip it for non-export callers (e.g. preview). |
| 3 | `src/spaceship_generator/shape/assembly.py:20` `_label_components` | ~0.117 s (≈12 % of total) | Pure-Python iterative DFS over a W*H*L filled array. For the large preset that's 64*32*18 = 37 k cells to scan, with per-cell `ndarray.__getitem__` overhead. This is by far the hottest first-party function. |
| 4 | `src/spaceship_generator/shape/hull.py:12` `_place_hull` | ~0.025 s | Triple-nested Python loop (`for z: for x: for y:`) doing per-cell ellipsoid distance test. Called once per ship. Runs fast enough but scales as O(W*H*L) without numpy broadcast. |
| 5 | `.venv/.../litemapy/storage.py:63` `storage.__setitem__` + `storage.__len__` | ~0.12 s combined | Called ~304 k times total (once per filled voxel + metadata overhead). Tight loop; dominated by Python dispatch. Upstream library — not fixable in-repo. |

## Suggested optimizations (not implemented)

These are *suggestions only*. They should each land as their own PR with the
bench re-run to confirm the delta.

1. **Batch the export loop.** Today `export_litematic` walks every filled
   voxel in a Python `for (x,y,z) in np.argwhere(...)` loop and calls
   `region[x,y,z] = bs` for each. Alternatives to explore, in order of
   expected payoff:
   - Group cells by role first (there are only 10 roles), then either (a)
     bulk-assign per role, or (b) pre-seed the litemapy region's internal
     block palette once so the first `__setitem__` per role doesn't trigger
     a linear palette scan. Since the hot `__eq__` call count (~790 k) is
     ~50× the voxel count, most of that cost is the palette scan, and
     pre-seeding should remove it.
   - If litemapy exposes a lower-level "set a raw paletted-index buffer"
     API, feed it the numpy array directly via a role → palette-index
     lookup table (`np.take` on an int8 lookup). That would collapse ~15 k
     Python calls per ship to a single vectorized write.

2. **Vectorize `_label_components`.** The current DFS is pure-Python.
   `scipy.ndimage.label` would do the same job in C and return a labeled
   array in milliseconds, but scipy isn't a current dependency. A
   dependency-free option: use `numpy`'s `np.nonzero` to enumerate filled
   voxels once, then run a union-find where the "find" is implemented on a
   preallocated `labels.ravel()` array — replaces the per-cell 3D index
   lookups (the main source of overhead) with 1D contiguous access.

3. **Vectorize `_place_hull` with broadcasting.** Replace the `for z: for
   x: for y:` triple loop with one broadcasted distance computation per
   ship:
   ```python
   # pseudocode
   x = np.arange(W)[:, None, None]
   y = np.arange(H)[None, :, None]
   z = np.arange(L)[None, None, :]
   profile = np.vectorize(profile_f)(z / max(L-1,1))  # or compute inline
   rx = np.maximum(0.5, (W*0.5 - 0.5) * profile * thickness * rx_scale)
   ry = np.maximum(0.5, (H*0.5 - 0.5) * profile * thickness * 0.7 * ry_scale)
   mask = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
   grid[mask] = Role.HULL
   ```
   Same for `_place_cockpit_bubble`, `_place_cockpit_pointed`, and
   `_place_engines`, all of which follow the identical triple-nested shape.
   Expected win: small in absolute terms (~25 ms → <5 ms) but *eliminates*
   the single-ship hull cost on any future enlargement.

4. **Cache the `_HULL_NOISE_FORBIDDEN` dtype-cast array in `texture.py`.**
   Every call to `_paint_hull_noise` and `_paint_rivets` does
   `np.array([r.value for r in _HULL_NOISE_FORBIDDEN], dtype=grid.dtype)`
   from scratch. It is constant — cache it module-level (or promote to a
   real `np.ndarray` constant). Impact is tiny in absolute terms because
   `role_assign` is already only 0.4 % of wall, but it's a free cleanup.

5. **Avoid double-computing `_surface_mask`.** `generate_shape` calls
   `_surface_mask` via `_place_greebles`, and then `assign_roles` calls it
   again on the final grid. If the grid's filled set didn't change between
   greeble placement and role assignment, the mask could be cached on the
   returned `GenerationResult` or passed through. In the current
   measurement this matters little (texture is 0.4 % of wall), but it's
   worth revisiting if `_surface_mask` is ever moved out of the 6-direction
   NumPy-shift form it's in today.

## Wave 2 optimizations

### export: pre-seed litemapy palette + vectorized block writes

Landed in `perf(export): cache BlockState by role`. The old `export_litematic`
loop did one Python-level `region[x,y,z] = bs` per filled voxel, and
litemapy's `Region.__setitem__` resolves each write by scanning the region's
block palette linearly (`block in self.__palette` + `self.__palette.index(block)`),
which calls `BlockState.__eq__` per comparison. For n=20 ships that was
~790 k `__eq__` calls and ~31 % of total wall time charged to
`export.py:13:export_litematic` + its litemapy callees.

The fix keeps the same public signature but:

1. Scans `role_grid` once with `np.unique(..., return_index=True)` to find
   each unique role's first-encounter offset, in C-order — exactly the order
   the naive loop would add them to the palette.
2. Pre-appends one `BlockState` per role (reused instance from
   `palette.block_state`) into the region's `_Region__palette` in that
   order, so indices 1..N match what the naive loop would have produced.
3. Builds a tiny `uint32` LUT keyed by role value and assigns the whole
   paletted-index buffer in one vectorized write
   (`region._Region__blocks[...] = lut[role_grid]`).

Result (20 ships, n=20 on the same machine as the baseline table above):

```
phase             base_s    cur_s   delta_s  delta_%
shape_build       0.1805   0.1545   -0.0260   -14.4%
role_assign       0.0036   0.0034   -0.0002    -4.9%
palette_lookup    0.0016   0.0012   -0.0004   -22.3%
export            0.5903   0.2829   -0.3074   -52.1%
other             0.3076   0.1819   -0.1258   -40.9%
WALL TOTAL        1.0833   0.6237   -0.4596   -42.4%
```

Export time per ship dropped from ~27 ms to ~14 ms. `BlockState.__eq__` fell
out of the top-5 hottest functions (it was ~103 ms total before). Total
profiled function calls dropped from ~4.46 M to ~1.79 M. Remaining export
cost is dominated by `schematic.py:342:to_nbt` (~150 ms) and
`storage.py:63:__setitem__` (~107 ms) — both inside litemapy's NBT
serializer, not the write loop.

**Byte-identity caveat.** Raw `.litematic` bytes are not reproducible even
between two back-to-back runs of the *old* code (litemapy's gzipped NBT
stream carries non-deterministic metadata). The regression contract is
*block-identity*: the palette ordering and per-voxel block content of the
loaded schematic must match across runs. That is enforced by
`tests/test_export.py::test_export_block_equivalence_across_runs`. A direct
spot-check across four sampled ships (seeds 1000/1037/1074/1111 across all
four palettes and all three dim presets) confirmed palette ordering
identical and 0/58368 block mismatches when comparing the new exporter's
output against the old one's.
