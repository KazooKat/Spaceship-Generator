"""End-to-end pipeline: seed + params → .litematic + (optional) preview PNG."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .engine_styles import EngineStyle, build_engines
from .export import export_litematic, filled_voxel_count
from .greeble_styles import GreebleType, scatter_greebles
from .palette import Palette, Role, load_palette
from .shape import ShapeParams, generate_shape
from .structure_styles import HullStyle
from .texture import TextureParams, assign_roles
from .weapon_styles import WeaponType, scatter_weapons


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
    preview_png: bytes | None = None

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


def _nose_tip_anchor_cells(
    shape_grid: np.ndarray, texture_params: TextureParams,
) -> dict[tuple[int, int], int]:
    """Return ``{(x, z_tip): y_tip}`` for every centerline nose-tip-light slot.

    Mirrors the geometry rule used by :func:`texture._paint_nose_tip_light`
    so the weapon writer can refuse to stack cells above a nose tip and
    silently drop the LIGHT it would otherwise receive. When the
    ``nose_tip_light`` texture flag is disabled the returned mapping is
    empty and the writer falls back to the plain "EMPTY-only" gate.
    """
    if not texture_params.nose_tip_light:
        return {}
    W, H, L = shape_grid.shape
    if W == 0 or H == 0 or L == 0:
        return {}
    if W % 2 == 1:
        center_xs: tuple[int, ...] = (W // 2,)
    else:
        center_xs = (W // 2 - 1, W // 2)

    out: dict[tuple[int, int], int] = {}
    for x in center_xs:
        col = shape_grid[x, :, :]
        filled = col != Role.EMPTY
        if not filled.any():
            continue
        z_tip = int(np.argwhere(filled.any(axis=0))[:, 0].max())
        ys = np.argwhere(filled[:, z_tip])[:, 0]
        if ys.size == 0:
            continue
        out[(x, z_tip)] = int(ys.max())
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
    hull_style_front: HullStyle | None = None,
    hull_style_rear: HullStyle | None = None,
    hull_blend_midband: float = 0.25,
    engine_style: EngineStyle | None = None,
    greeble_density: float = 0.0,
    greeble_types: Iterable[GreebleType] | None = None,
    weapon_count: int = 0,
    weapon_types: Iterable[WeaponType] | None = None,
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
    hull_style_front, hull_style_rear:
        Optional pair of :class:`HullStyle` archetypes for blending two
        silhouettes along Z. Both must be set for the blend to engage; when
        either is ``None`` the legacy hull selection (driven by
        ``hull_style``/``shape_params.structure_style``) is used unchanged.
        When both are set the blend takes precedence over ``hull_style``.
    hull_blend_midband:
        Fraction of the ship's length over which the front/rear crossover
        is centred (default ``0.25`` — a 25% midband). Ignored unless both
        ``hull_style_front`` and ``hull_style_rear`` are provided.
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
    weapon_count:
        Non-negative integer number of weapon emplacements to scatter on
        the ship's top-facing hull. ``0`` (default) leaves the grid
        untouched. When ``> 0``, :func:`scatter_weapons` runs after the
        main pipeline (and after greebles) and placements are written
        into empty cells only so existing hull/cockpit/engine/wing cells
        are preserved.
    greeble_types:
        Optional iterable of :class:`GreebleType` members restricting which
        greeble archetypes may be scattered. ``None`` (default) allows every
        type. Unknown members raise :class:`ValueError`.
    weapon_types:
        Optional iterable of :class:`WeaponType` members restricting which
        archetypes may be placed. ``None`` (default) allows every type.
        Unknown members raise :class:`ValueError`.
    """
    out_dir = Path(out_dir)

    pal = palette if isinstance(palette, Palette) else load_palette(palette)
    shape_params = shape_params or ShapeParams()
    texture_params = texture_params or TextureParams()
    if not 0.0 <= float(greeble_density) <= 1.0:
        raise ValueError(
            f"greeble_density must be in [0, 1]; got {greeble_density!r}"
        )
    if int(weapon_count) < 0:
        raise ValueError(
            f"weapon_count must be >= 0; got {weapon_count!r}"
        )
    # Materialize greeble_types once so we can validate members eagerly.
    allowed_greeble_types: list[GreebleType] | None
    if greeble_types is None:
        allowed_greeble_types = None
    else:
        allowed_greeble_types = []
        for t in greeble_types:
            if not isinstance(t, GreebleType):
                raise ValueError(
                    f"greeble_types entries must be GreebleType members; "
                    f"got {t!r}"
                )
            allowed_greeble_types.append(t)
    # Materialize weapon_types once so we can validate members eagerly and
    # still hand a concrete list to scatter_weapons below.
    allowed_weapon_types: list[WeaponType] | None
    if weapon_types is None:
        allowed_weapon_types = None
    else:
        allowed_weapon_types = []
        for t in weapon_types:
            if not isinstance(t, WeaponType):
                raise ValueError(
                    f"weapon_types entries must be WeaponType members; "
                    f"got {t!r}"
                )
            allowed_weapon_types.append(t)

    shape_grid = generate_shape(
        seed,
        shape_params,
        hull_style=hull_style,
        hull_style_front=hull_style_front,
        hull_style_rear=hull_style_rear,
        hull_blend_midband=hull_blend_midband,
    )

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
            shape_grid, greeble_rng, float(greeble_density), types=allowed_greeble_types
        ):
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                if shape_grid[x, y, z] == Role.EMPTY:
                    shape_grid[x, y, z] = role

    # Optional scattered weapons. Placements are written into empty cells
    # only so existing hull/cockpit/engine/wing cells are preserved. We
    # additionally refuse to stack weapon cells *above* the nose-tip-light
    # column(s): otherwise a plasma_core / missile_pod stamped near the
    # forward centerline shadows the topmost cell with ENGINE_GLOW (a
    # protected role in :func:`assign_roles`), which silently drops the
    # nose-tip LIGHT and breaks the additive contract of the weapon writer.
    if int(weapon_count) > 0:
        W, H, L = shape_grid.shape
        nose_tips = _nose_tip_anchor_cells(shape_grid, texture_params)
        weapon_rng = np.random.default_rng(seed ^ 0x7A)
        for x, y, z, role in scatter_weapons(
            shape_grid,
            weapon_rng,
            int(weapon_count),
            types=allowed_weapon_types,
        ):
            if 0 <= x < W and 0 <= y < H and 0 <= z < L:
                if shape_grid[x, y, z] != Role.EMPTY:
                    continue
                # Skip writes that would shadow a nose-tip-light slot, i.e.
                # any cell strictly above (y > y_tip) the centerline tip at
                # the same (x, z_tip).
                if (x, z) in nose_tips and y > nose_tips[(x, z)]:
                    continue
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

    preview_bytes: bytes | None = None
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
