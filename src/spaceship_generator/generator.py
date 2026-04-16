"""End-to-end pipeline: seed + params → .litematic + (optional) preview PNG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .export import export_litematic, filled_voxel_count
from .palette import Palette, load_palette
from .shape import ShapeParams, generate_shape
from .texture import TextureParams, assign_roles


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
    """
    out_dir = Path(out_dir)

    pal = palette if isinstance(palette, Palette) else load_palette(palette)
    shape_params = shape_params or ShapeParams()
    texture_params = texture_params or TextureParams()

    shape_grid = generate_shape(seed, shape_params)
    role_grid = assign_roles(shape_grid, texture_params)

    filename = filename or f"ship_{seed}.litematic"
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
