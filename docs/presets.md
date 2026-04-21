# Ship Presets

A **preset** is a named bundle of hull, engine, wing, cockpit, greeble, and
weapon parameters. Instead of wiring every knob by hand, you pick a role
name (`"corvette"`, `"gunship"`, ...) and the library returns a kwargs
dict you can unpack into `generate(...)`.

## Bundled archetypes

| Name              | One-liner                                                                           |
| ----------------- | ----------------------------------------------------------------------------------- |
| `corvette`        | Fast dagger-hulled escort: twin nacelles, swept wings, turret + point-defense pair. |
| `dropship`        | Blocky freighter hull with quad-cluster engines, tapered wings, no weapons.         |
| `science_vessel`  | Saucer hull + ring engine and canopy dome; single plasma-core emitter.              |
| `gunship`         | Arrow hull, ion-array engines, delta wings, offset turret — four-weapon loadout.    |
| `freighter_heavy` | Fat whale hull, single-core engine, straight wings, wrap-bridge; heaviest preset.   |
| `interceptor`     | Smallest and fastest: dagger hull, ion array, split wings, pointed nose, laser lance. |

Each preset sets `(width, height, length)` sizing and a possibly-empty weapon loadout.

## Usage from Python

```python
from spaceship_generator.generator import generate
from spaceship_generator.presets import apply_preset, list_presets

print(list_presets())
# ['corvette', 'dropship', 'freighter_heavy', 'gunship', 'interceptor', 'science_vessel']

kwargs = apply_preset("corvette")
result = generate(seed=1337, palette="sci_fi_industrial", **kwargs)
print(result.litematic_path, result.block_count)
```

`apply_preset(name)` returns a dict with keys `shape_params`,
`hull_style`, `engine_style`, `greeble_density`, `weapon_count`, and
`weapon_types` — all of which `generate(...)` already understands.
Every call constructs a fresh `ShapeParams` and a fresh `weapon_types`
list, so you can mutate them without polluting the registry.

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
    assert set(spec.keys()) == set(PRESET_KEYS)
    print(name, spec["hull_style"].value, spec["size"])
```

## Scope and roadmap

- Presets are a **Python-library feature** in this wave.
- CLI integration (`--preset corvette`) and a matching web-UI dropdown
  are intentionally **future wave** items; this module keeps its surface
  area small so CLI/web layers can build on top without a rewrite.

## Adding a new preset

1. Add an entry to `SHIP_PRESETS` in `src/spaceship_generator/presets.py`.
2. Ensure `size=(w, h, l)` respects `ShapeParams` minimums: `w >= 4`,
   `h >= 4`, `l >= 8`.
3. Add a row to the table above and run
   `.venv/Scripts/python -m pytest tests/test_presets.py -q`.
