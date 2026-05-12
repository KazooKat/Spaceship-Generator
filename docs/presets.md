# Ship Presets

All 9 presets shipped with the Spaceship Generator. A **preset** is a named bundle of hull, engine, wing, cockpit, greeble, and weapon parameters — instead of wiring every knob by hand, you pick a role name (`"corvette"`, `"gunship"`, ...) and the library returns a kwargs dict you can unpack into `generate(...)`. Presets live in `src/spaceship_generator/presets.py` (`SHIP_PRESETS` dict) — see [Adding a new preset](#adding-a-new-preset) below for the schema.

| Preset | Description |
|---|---|
| `battlecruiser` | Heavy combat line ship — thick armor, quad-cluster engines |
| `capital_carrier` | Fleet flagship — massive hull, hosts fighter wings |
| `corvette` | Fast light warship — twin nacelles, two weapon hardpoints |
| `dropship` | Armored troop transport — wide hull, short-range insertion craft |
| `freighter_heavy` | Bulk cargo hauler — boxy silhouette, minimal armament |
| `gunship` | Fire-support platform — heavy weapon loadout, twin-engine drive |
| `interceptor` | Agile point-defense fighter — small frame, high speed |
| `science_vessel` | Deep-space research ship — sensor arrays, zero weapons |
| `scout` | Lightweight recon craft — speed over firepower, long-range |

Run `spaceship-generator --list-presets` to see this list from the CLI, or use `apply_preset(NAME)` from Python (see below) to expand a preset into `generate(...)` kwargs.

## Usage from Python

```python
from spaceship_generator.generator import generate
from spaceship_generator.presets import apply_preset, list_presets

print(list_presets())
# ['battlecruiser', 'capital_carrier', 'corvette', 'dropship',
#  'freighter_heavy', 'gunship', 'interceptor', 'science_vessel', 'scout']

kwargs = apply_preset("corvette")
result = generate(seed=1337, palette="sci_fi_industrial", **kwargs)
print(result.litematic_path, result.block_count)
```

`apply_preset(name)` returns a dict with keys `shape_params`, `hull_style`,
`engine_style`, `greeble_density`, `weapon_count`, and `weapon_types` —
all of which `generate(...)` already understands. Every call constructs
a fresh `ShapeParams` and a fresh `weapon_types` list, so you can mutate
them without polluting the registry.

You can override any field at call time by passing it after the unpack:

```python
# Corvette silhouette, but with four turrets instead of two.
generate(seed=42, **apply_preset("corvette"), weapon_count=4)
```

Unknown names raise `KeyError`:

```python
apply_preset("star_destroyer")  # KeyError: unknown preset 'star_destroyer'
```

## Inspecting the raw table

If you need UI or tooling on top of the registry, read the source-of-truth
dict directly:

```python
from spaceship_generator.presets import SHIP_PRESETS, PRESET_KEYS

for name, spec in SHIP_PRESETS.items():
    assert set(spec.keys()) >= set(PRESET_KEYS)
    print(name, spec["hull_style"].value, spec["size"])
```

## Adding a new preset

1. Add an entry to `SHIP_PRESETS` in `src/spaceship_generator/presets.py`.
2. Include a `description:` one-liner so `--list-presets` and this catalog
   stay informative.
3. Ensure `size=(w, h, l)` respects `ShapeParams` minimums: `w >= 4`,
   `h >= 4`, `l >= 8`.
4. Add a row to the table above (alphabetical by name) and run
   `.venv/Scripts/python -m pytest tests/test_presets.py -q`.

## Preset parameter breakdown

The table below is sourced from the `SHIP_PRESETS` dict in
`src/spaceship_generator/presets.py` — if you suspect it has drifted, regenerate
it from that module directly (or via `--list-presets-json`, see [cli.md](cli.md)).
Note that `palette` is **not** a preset field — it's a separate `generate(...)`
kwarg you pass alongside the unpacked preset (see the [Usage from Python](#usage-from-python)
example above). Style cells are `hull / engine / wing / cockpit`. Enum values
use the lowercase `StrEnum` `.value` form (matches `--list-presets-json` output).

| preset | hull / engine / wing / cockpit | size (w,h,l) | weapon_count | greeble_density | weapon_types |
|---|---|---|---|---|---|
| `battlecruiser` | arrow / quad_cluster / delta / wrap_bridge | (22, 12, 40) | 6 | 0.20 | turret_large, missile_pod, point_defense |
| `capital_carrier` | modular_block / ring / straight / offset_turret | (30, 16, 50) | 8 | 0.15 | turret_large, missile_pod, point_defense |
| `corvette` | dagger / twin_nacelle / swept / bubble | (20, 12, 50) | 2 | 0.10 | turret_large, point_defense |
| `dropship` | blocky_freighter / quad_cluster / tapered / integrated | (25, 15, 35) | 0 | 0.05 | (none) |
| `freighter_heavy` | whale / single_core / straight / wrap_bridge | (40, 20, 80) | 0 | 0.03 | (none) |
| `gunship` | arrow / ion_array / delta / offset_turret | (22, 13, 55) | 4 | 0.05 | missile_pod, turret_large |
| `interceptor` | dagger / ion_array / split / pointed | (15, 10, 45) | 1 | 0.02 | laser_lance |
| `science_vessel` | saucer / ring / gull / canopy_dome | (30, 15, 50) | 1 | 0.08 | plasma_core |
| `scout` | sleek_racing / ion_array / swept / bubble | (8, 5, 14) | 1 | 0.05 | point_defense |

Run `python -m spaceship_generator --list-presets-json` for the same data in
machine-readable form (see [`docs/cli.md`](cli.md) for the flag's
`--quiet` carve-out and JSON shape).

## Annotated preset entry schema

Presets are Python dicts in `src/spaceship_generator/presets.py` (no YAML
form — palettes are YAML, presets are not). Every entry in `SHIP_PRESETS`
matches the schema pinned by `PRESET_KEYS` plus a free-text `description`:

```python
"corvette": {
    "description": "Fast light warship — twin nacelles, two weapon hardpoints",
    "hull_style": HullStyle.DAGGER,        # silhouette, drives structure_styles.py dispatch
    "engine_style": EngineStyle.TWIN_NACELLE,  # engine layout, plumbed via top-level kwarg
    "wing_style": WingStyle.SWEPT,         # wing planform, set on ShapeParams.wing_style
    "cockpit_style": CockpitStyle.BUBBLE,  # cockpit, set on ShapeParams.cockpit_style
    "greeble_density": 0.1,                # float in [0.0, 1.0], greeble scatter probability
    "weapon_count": 2,                     # non-negative int
    "weapon_types": (WeaponType.TURRET_LARGE, WeaponType.POINT_DEFENSE),  # immutable tuple
    "size": (20, 12, 50),                  # (width_max, height_max, length); minimums 4/4/8
},
```

`apply_preset(name)` flattens this into `generate(...)` kwargs: `size` is
spread into a fresh `ShapeParams(length=, width_max=, height_max=,
cockpit_style=, wing_style=)`, and `weapon_types` is materialized as a
fresh `list` so callers can mutate without polluting the registry.

## Selecting a preset on the CLI

Pass `--preset NAME` to load a preset and let the CLI fill in the styles,
size, and loadout for you. `NAME` is constrained to the keys returned by
`list_presets()` (argparse `choices=`), so typos error out early:

```bash
python -m spaceship_generator --preset corvette --seed 42 --palette sci_fi_industrial
python -m spaceship_generator --preset star_destroyer  # error: invalid choice
```

Pair with `--list-presets` (human-readable) or `--list-presets-json`
(machine-readable) to discover what's available without leaving the
shell — both honor the standard `--quiet` carve-out.

## Composing CLI flags on top of a preset

Explicit flags **always win** over preset values. The CLI walks each
preset field and only writes it onto `args` when the matching flag was
NOT typed on the command line (see the `if "--<flag>" not in explicit`
guards in `cli.py` around the `--preset` resolution block). For example:

```bash
# Corvette silhouette + loadout, but force four weapons and a freighter palette:
python -m spaceship_generator --preset corvette --weapon-count 4 --palette industrial_freighter
```

Override coverage spans the preset-controlled axes: `--hull-style`,
`--engine-style`, `--wing-style`, `--cockpit-style`, `--length`, `--width`,
`--height`, `--greeble-density`, `--weapon-count`, and `--weapon-types`.
Anything the preset does not own (`--seed`, `--palette`, `--out`, fleet
flags, texture knobs, …) is passed through untouched. To audit the
resolved values without generating, add `--config-dump` — it prints the
post-preset, post-override kwargs the generator would actually receive.

## Writing a custom preset for a fleet

Custom presets live alongside the shipped ones — there is no separate
discovery directory. To add one:

1. Open `src/spaceship_generator/presets.py` and add an entry to
   `SHIP_PRESETS` matching the schema above (all `PRESET_KEYS` fields
   plus `description`).
2. Respect the `ShapeParams` minimums in `size`: `width_max >= 4`,
   `height_max >= 4`, `length >= 8`.
3. Use enum members (`HullStyle.X`, `EngineStyle.Y`, `WeaponType.Z`),
   not raw strings — `apply_preset` calls `.value` when projecting onto
   the CLI surface.
4. Run `pytest tests/test_presets.py -q` — the schema, enum-membership,
   and `--list-presets-json` round-trip tests will catch typos.
5. Drive a fleet from your new preset with `--preset my_role
   --fleet-count N --seed <master>`; per-ship dims are still planned by
   `fleet.py` from the master seed, and your preset's `size` becomes
   the size-tier baseline (see [Fleet pipeline](architecture.md#fleet-pipeline)).
