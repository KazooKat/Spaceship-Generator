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
