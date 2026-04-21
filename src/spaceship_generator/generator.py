"""End-to-end pipeline: seed + params → .litematic + (optional) preview PNG."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .engine_styles import EngineStyle, build_engines
from .export import export_litematic, filled_voxel_count
from .greeble_styles import scatter_greebles
from .palette import Palette, Role, load_palette
from .shape import ShapeParams, generate_shape
from .structure_styles import HullStyle
from .texture import TextureParams, assign_roles


def _sanitize_filename(name: str) -> str:
    """Reject absolute paths, path separators, traversal, and illegal chars.

    Returns ``name`` unchanged when valid. Raises :class:`ValueError` otherwise.
    """
    if not name:
        raise ValueError("filename must be non-empty")
    if os.path.isabs(name):
        raise ValueError("filename must not be absolute")
    if (
        "/" in name
        or "\\" in name
        or name in ("..", ".")
        or ".." in Path(name).parts
    ):
        raise ValueError("filename must not contain path separators or traversal")
    illegal = set('<>:"|?*\x00')
    if any(c in illegal for c in name):
        raise ValueError("filename contains illegal characters")
    return name


@dataclass
class GenerationResult:
    """Everything produced by one call to :func:`generate`."""

    seed: int
    palette_name: str
    litematic_path: Path
    role_grid: np.ndarray
    preview_png: Optional[bytes] = None

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(self.role_grid.shape)  # type: ignore[return-value]

    @property
    def block_count(self) -> int:
        return filled_voxel_count(self.role_grid)

    def save_preview(self, path: str | Path) -> Path:
        """Write ``preview_png`` bytes to ``path`` and return the path.

        Raises
        ------
        ValueError
            If ``preview_png`` is ``None`` (no preview was rendered).
        """
        if self.preview_png is None:
            raise ValueError(
                "No preview available; call generate(..., with_preview=True) first."
            )
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(self.preview_png)
        return out


def generate(
    seed: int,
    *,
    palette: str | Palette = "sci_fi_industrial",
    shape_params: ShapeParams | None = None,
    texture_params: TextureParams | None = None,
    out_dir: str | Path = "out",
    filename: str | None = None,
    author: str = "spaceship-generator",
    name: str | None = None,
    with_preview: bool = False,
    preview_size: tuple[int, int] = (800, 800),
    hull_style: HullStyle | None = None,
    engine_style: EngineStyle | None = None,
    greeble_density: float = 0.0,
) -> GenerationResult:
    """Run the full pipeline and write a ``.litematic`` to ``out_dir``.

    Parameters
    ----------
    seed:
        Integer seed for reproducibility.
    palette:
        Palette name (loaded from the built-in ``palettes/`` folder) or a
        :class:`Palette` instance.
    shape_params, texture_params:
        Optional overrides; defaults used otherwise.
    out_dir:
        Directory for the output file (created if missing).
    filename:
        Output filename (defaults to ``ship_<seed>.litematic``).
    author, name:
        Schematic metadata. ``name`` defaults to ``"Ship <seed>"``.
    with_preview:
        If True, also render a matplotlib preview PNG and return its bytes.
    preview_size:
        Preview image size in pixels.
    hull_style:
        Optional :class:`HullStyle` archetype. When ``None`` (default) the
        current hull behavior is preserved. When set, :func:`apply_hull_style`
        stamps the base hull before parts placement inside ``generate_shape``.
    engine_style:
        Optional :class:`EngineStyle` archetype. When ``None`` (default) the
        built-in engine placer is used. When set, the default ENGINE and
        ENGINE_GLOW cells are cleared and replaced with placements from
        :func:`build_engines`.
    greeble_density:
        Fraction in ``[0.0, 1.0]``. When ``0.0`` (default) no extra surface
        greebles are added. When ``> 0``, :func:`scatter_greebles` is run
        after the main build and placements are written into empty cells
        only (existing hull/cockpit/engine cells are preserved).
    """
    out_dir = Path(out_dir)

    pal = palette if isinstance(palette, Palette) else load_palette(palette)
    shape_params = shape_params or ShapeParams()
    texture_params = texture_params or TextureParams()
    if not 0.0 <= float(greeble_density) <= 1.0:
        raise ValueError(
            f"greeble_density must be in [0, 1]; got {greeble_density!r}"
        )

    shape_grid = generate_shape(seed, shape_params, hull_style=hull_style)

    # Optional engine override: wipe the default engine cells and rewrite
    # using the chosen EngineStyle. Engines sit at the rear slab (z=0).
    if engine_style is not None:
        W, H, L = shape_grid.shape
        engine_mask = (shape_grid == Role.ENGINE) | (shape_grid == Role.ENGINE_GLOW)
        shape_grid[engine_mask] = Role.EMPTY
        engine_rng = np.random.default_rng(seed ^ 0xE5)
        # Match the geometry conventions used by the default engine placer:
        # radius = max(1, min(W, H) // 10), length = max(2, L // 8), spread
        # across half the width so multi-engine layouts don't collide.
        base_radius = max(1, min(W, H) // 10)
        engine_length = max(2, L // 8)
        spread = max(2, W // 4)
        cy_engine = max(base_radius + 1, H // 2 - 1)
        placements = build_engines(
            shape_grid,
            engine_style,
            position=(W // 2, cy_engine, 0),
            size=(base_radius, engine_length, spread),
            rng=engine_rng,
        )
        for x, y, z, role in placements:
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                shape_grid[x, y, z] = role

    # Optional scattered greebles. Write into empty cells only so existing
    # hull/cockpit/engine/wing cells aren't clobbered.
    if greeble_density > 0.0:
        W, H, L = shape_grid.shape
        greeble_rng = np.random.default_rng(seed ^ 0x6E)
        for x, y, z, role in scatter_greebles(
            shape_grid, greeble_rng, float(greeble_density)
        ):
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                if shape_grid[x, y, z] == Role.EMPTY:
                    shape_grid[x, y, z] = role

    role_grid = assign_roles(shape_grid, texture_params)

    filename = filename or f"ship_{seed}.litematic"
    filename = _sanitize_filename(filename)
    out_path = out_dir / filename
    schem_name = name or f"Ship {seed}"
    export_litematic(
        role_grid,
        pal,
        out_path,
        name=schem_name,
        author=author,
        description=f"Procedurally generated spaceship (seed={seed}, palette={pal.name})",
    )

    preview_bytes: Optional[bytes] = None
    if with_preview:
        # Import here so the CLI/export path doesn't always pull in matplotlib.
        from .preview import render_preview

        preview_bytes = render_preview(role_grid, pal, size=preview_size)

    return GenerationResult(
        seed=seed,
        palette_name=pal.name,
        litematic_path=out_path,
        role_grid=role_grid,
        preview_png=preview_bytes,
    )
