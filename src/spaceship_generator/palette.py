"""Role enum + Palette loader.

A palette maps semantic roles (HULL, WINDOW, ENGINE_GLOW, ...) to Minecraft
block IDs and preview hex colors. Palettes are YAML files in ``palettes/``.

Block state strings may include properties using the Minecraft syntax
``minecraft:foo[prop1=val1,prop2=val2]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import yaml
from litemapy import BlockState


class Role(IntEnum):
    """Semantic role of a voxel. 0 means empty (no block)."""

    EMPTY = 0
    HULL = 1
    HULL_DARK = 2
    WINDOW = 3
    ENGINE = 4
    ENGINE_GLOW = 5
    COCKPIT_GLASS = 6
    WING = 7
    GREEBLE = 8
    LIGHT = 9
    INTERIOR = 10


#: Role names required in every palette (EMPTY excluded).
REQUIRED_ROLES: tuple[str, ...] = tuple(r.name for r in Role if r != Role.EMPTY)

_BLOCKSTATE_RE = re.compile(
    r"^(?P<id>[a-z0-9_]+:[a-z0-9_]+)(?:\[(?P<props>[^\]]*)\])?$"
)


def parse_block_state(spec: str) -> BlockState:
    """Parse a Minecraft block-state string into a :class:`litemapy.BlockState`.

    Accepts ``"minecraft:stone"`` or ``"minecraft:redstone_lamp[lit=true]"``.
    """
    spec = spec.strip()
    m = _BLOCKSTATE_RE.match(spec)
    if not m:
        raise ValueError(f"Invalid block state string: {spec!r}")
    block_id = m.group("id")
    props_str = m.group("props")
    props: dict[str, str] = {}
    if props_str:
        for pair in props_str.split(","):
            key, _, value = pair.partition("=")
            key, value = key.strip(), value.strip()
            if not key or not value:
                raise ValueError(f"Malformed block-state property in {spec!r}: {pair!r}")
            props[key] = value
    return BlockState(block_id, **props)


def _parse_color(value: str | list[float]) -> tuple[float, float, float, float]:
    """Parse a color to RGBA tuple (0..1 floats). Accepts ``"#rrggbb"`` or list."""
    if isinstance(value, (list, tuple)):
        if len(value) == 3:
            r, g, b = value
            return (float(r), float(g), float(b), 1.0)
        if len(value) == 4:
            return tuple(float(v) for v in value)  # type: ignore[return-value]
        raise ValueError(f"Color list must have 3 or 4 elements, got {value!r}")
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) == 6:
            r = int(s[0:2], 16) / 255.0
            g = int(s[2:4], 16) / 255.0
            b = int(s[4:6], 16) / 255.0
            return (r, g, b, 1.0)
        if len(s) == 8:
            r = int(s[0:2], 16) / 255.0
            g = int(s[2:4], 16) / 255.0
            b = int(s[4:6], 16) / 255.0
            a = int(s[6:8], 16) / 255.0
            return (r, g, b, a)
    raise ValueError(f"Cannot parse color: {value!r}")


@dataclass(frozen=True)
class Palette:
    """A named mapping from roles to BlockStates + preview colors."""

    name: str
    blocks: dict[Role, BlockState]
    preview_colors: dict[Role, tuple[float, float, float, float]]

    def block_state(self, role: Role | int) -> BlockState:
        """Return the :class:`BlockState` for a role. Raises on EMPTY."""
        r = Role(role)
        if r == Role.EMPTY:
            raise ValueError("Cannot get block state for Role.EMPTY")
        return self.blocks[r]

    def preview_color(self, role: Role | int) -> tuple[float, float, float, float]:
        """Return the RGBA preview color for a role. Transparent for EMPTY."""
        r = Role(role)
        if r == Role.EMPTY:
            return (0.0, 0.0, 0.0, 0.0)
        return self.preview_colors[r]

    @classmethod
    def load(cls, path: str | Path) -> "Palette":
        """Load a palette from a YAML file.

        Errors raised by :meth:`from_dict` are wrapped so that the offending
        file path is included in the message.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        try:
            return cls.from_dict(data)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc

    @classmethod
    def from_dict(cls, data: dict) -> "Palette":
        if "name" not in data or "blocks" not in data:
            raise ValueError("Palette YAML must include 'name' and 'blocks'")
        name = str(data["name"])
        raw_blocks = data["blocks"] or {}
        raw_colors = data.get("preview_colors") or {}

        missing = [r for r in REQUIRED_ROLES if r not in raw_blocks]
        if missing:
            raise ValueError(f"Palette {name!r} missing block roles: {missing}")

        blocks = {Role[r]: parse_block_state(raw_blocks[r]) for r in REQUIRED_ROLES}
        preview: dict[Role, tuple[float, float, float, float]] = {}
        for r in REQUIRED_ROLES:
            if r in raw_colors:
                preview[Role[r]] = _parse_color(raw_colors[r])
            else:
                # Fallback: mid-gray.
                preview[Role[r]] = (0.5, 0.5, 0.5, 1.0)

        return cls(name=name, blocks=blocks, preview_colors=preview)


def palettes_dir() -> Path:
    """Return the default palettes directory (``<repo>/palettes``)."""
    return Path(__file__).resolve().parents[2] / "palettes"


def load_palette(name: str, search_dir: str | Path | None = None) -> Palette:
    """Load a palette by name (filename stem) from the palettes directory."""
    directory = Path(search_dir) if search_dir else palettes_dir()
    path = directory / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Palette {name!r} not found at {path}")
    return Palette.load(path)


def validate_palette_file(path: str | Path) -> list[str]:
    """Return a list of human-readable warnings for a palette YAML.

    This is intended for "lint my palette" tooling. It never raises; if the
    file cannot be opened or parsed, that becomes a warning itself.

    Checks performed:
      * File exists and parses as a YAML mapping.
      * Required top-level keys ``name`` and ``blocks`` are present.
      * Every role in :data:`REQUIRED_ROLES` has a block state string.
      * Each block state string parses via :func:`parse_block_state`.
      * Each role has a preview color; unparseable colors are flagged.
      * Unknown top-level keys or unknown role names are flagged.
    """
    path = Path(path)
    warnings: list[str] = []

    if not path.exists():
        warnings.append(f"file does not exist: {path}")
        return warnings

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        warnings.append(f"invalid YAML: {exc}")
        return warnings

    if not isinstance(data, dict):
        warnings.append("top-level YAML must be a mapping")
        return warnings

    if "name" not in data:
        warnings.append("missing top-level 'name' key")
    if "blocks" not in data:
        warnings.append("missing top-level 'blocks' key")

    known_top_keys = {"name", "description", "blocks", "preview_colors"}
    unknown = sorted(set(data.keys()) - known_top_keys)
    for key in unknown:
        warnings.append(f"unknown top-level key: {key!r}")

    raw_blocks = data.get("blocks") or {}
    if not isinstance(raw_blocks, dict):
        warnings.append("'blocks' must be a mapping of role -> block state")
        raw_blocks = {}
    raw_colors = data.get("preview_colors") or {}
    if not isinstance(raw_colors, dict):
        warnings.append("'preview_colors' must be a mapping of role -> color")
        raw_colors = {}

    required = set(REQUIRED_ROLES)
    for role in REQUIRED_ROLES:
        if role not in raw_blocks:
            warnings.append(f"missing block for role: {role}")
        else:
            spec = raw_blocks[role]
            if not isinstance(spec, str):
                warnings.append(
                    f"block for role {role!r} must be a string, got {type(spec).__name__}"
                )
            else:
                try:
                    parse_block_state(spec)
                except ValueError as exc:
                    warnings.append(f"invalid block state for role {role!r}: {exc}")

        if role not in raw_colors:
            warnings.append(f"missing preview_color for role: {role}")
        else:
            try:
                _parse_color(raw_colors[role])
            except (ValueError, TypeError) as exc:
                warnings.append(f"invalid preview_color for role {role!r}: {exc}")

    unknown_block_roles = sorted(set(raw_blocks.keys()) - required)
    for role in unknown_block_roles:
        warnings.append(f"unknown role in 'blocks': {role!r}")
    unknown_color_roles = sorted(set(raw_colors.keys()) - required)
    for role in unknown_color_roles:
        warnings.append(f"unknown role in 'preview_colors': {role!r}")

    return warnings


def list_palettes(
    search_dir: str | Path | None = None,
    include_errors: bool = False,
) -> list[str] | list[tuple[str, list[str]]]:
    """List palette names available in the palettes directory.

    With ``include_errors=True``, returns a ``list[tuple[name, warnings]]``
    where ``warnings`` is the output of :func:`validate_palette_file` for
    each discovered YAML. Otherwise returns a plain ``list[str]`` of names.
    """
    directory = Path(search_dir) if search_dir else palettes_dir()
    if not directory.exists():
        return []
    paths = sorted(directory.glob("*.yaml"))
    if not include_errors:
        return [p.stem for p in paths]
    return [(p.stem, validate_palette_file(p)) for p in paths]
