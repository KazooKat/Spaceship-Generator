"""Render a role grid as an isometric PNG preview using matplotlib."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # headless — safe for Flask/CLI

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from .palette import Palette, Role  # noqa: E402


def _parse_hex_color(value: str) -> tuple[int, int, int, int]:
    """Parse ``"#rrggbb"`` or ``"#rrggbbaa"`` into 0-255 RGBA ints.

    ``"transparent"`` is handled by callers; this helper raises on it.
    """
    s = value.strip().lstrip("#")
    if len(s) == 6:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255
    if len(s) == 8:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
    raise ValueError(f"background must be #rrggbb or #rrggbbaa, got {value!r}")


def _apply_specular(
    colors: np.ndarray,
    filled: np.ndarray,
) -> None:
    """In-place specular highlight: boost voxels with exposed top (+Y) / sides.

    ``colors`` is shape ``(W, L, H, 4)`` — display-space with axis 2 = vertical.
    ``filled`` is the bool mask of occupied voxels in the same layout.

    Voxels with an exposed top face (nothing directly above) get a +8% RGB
    boost. Voxels that are only side-exposed get +4%. Bottom-only → 0.
    """
    if not filled.any():
        return
    W, L, H = filled.shape
    above = np.zeros_like(filled)
    above[:, :, : H - 1] = filled[:, :, 1:]
    top_exposed = filled & ~above

    # Side exposure: any neighbor in ±X missing.
    side_exposed = np.zeros_like(filled)
    if W > 1:
        neg_x = np.ones_like(filled)
        neg_x[1:, :, :] = filled[:-1, :, :]
        pos_x = np.ones_like(filled)
        pos_x[:-1, :, :] = filled[1:, :, :]
        side_exposed |= filled & (~neg_x | ~pos_x)
    else:
        side_exposed |= filled  # single-column grids — every side is exposed

    top_boost = 1.08
    side_boost = 1.04

    # Top takes precedence over side (higher boost).
    rgb = colors[..., :3]
    mask_top = top_exposed
    mask_side_only = side_exposed & ~top_exposed
    rgb[mask_top] = np.clip(rgb[mask_top] * top_boost, 0.0, 1.0)
    rgb[mask_side_only] = np.clip(rgb[mask_side_only] * side_boost, 0.0, 1.0)


def render_preview(
    role_grid: np.ndarray,
    palette: Palette,
    *,
    size: tuple[int, int] = (800, 800),
    view: tuple[float, float] = (22.0, -62.0),
    color_override: dict | None = None,
    antialias: bool = True,
    specular: bool = True,
    background: str = "#0d0f12",
) -> bytes:
    """Return PNG bytes of an isometric voxel render of ``role_grid``.

    ``role_grid`` is indexed ``grid[x, y, z]`` (Y-up). Matplotlib's 3-D axes
    use Z-up, so axes are swapped for display.

    ``color_override`` optionally maps ``Role -> (r, g, b, a)`` tuples (values
    in 0-1). When provided, it takes precedence over ``palette.preview_color``
    for the given roles. Used by the web UI to render with approximated
    Minecraft block colors instead of the stylized palette colors.

    Keyword-only visual tuning:
      ``antialias``: render at 2× scale and Lanczos-downsample for smoother
        edges. Default ``True``.
      ``specular``: apply a subtle brightness boost to top-facing voxels.
        Default ``True``.
      ``background``: hex string (``"#rrggbb"`` / ``"#rrggbbaa"``) used as a
        solid backdrop composited behind the render. Use the sentinel
        ``"transparent"`` to emit an RGBA PNG with no backdrop. Default is the
        dark console color ``"#0d0f12"``.
    """
    if role_grid.ndim != 3:
        raise ValueError(f"role_grid must be 3D, got shape {role_grid.shape}")
    if not np.isfinite(view[0]) or not np.isfinite(view[1]):
        raise ValueError("view angles must be finite")

    transparent_bg = background == "transparent"
    if not transparent_bg:
        bg_rgba = _parse_hex_color(background)
    else:
        bg_rgba = None

    # Matplotlib voxels expects (x, y, z) with z = vertical. Swap Y and Z.
    display = np.transpose(role_grid, (0, 2, 1))  # (W, L, H) → z-axis = our height
    W, L, H = display.shape

    filled = display != Role.EMPTY
    colors = np.zeros((W, L, H, 4), dtype=float)
    for role in Role:
        if role == Role.EMPTY:
            continue
        mask = display == role
        if not mask.any():
            continue
        if color_override and role in color_override:
            colors[mask] = color_override[role]
        else:
            colors[mask] = palette.preview_color(role)

    if specular:
        _apply_specular(colors, filled)

    dpi = 100
    scale = 2 if antialias else 1
    render_size = (size[0] * scale, size[1] * scale)

    fig = None
    try:
        fig = plt.figure(figsize=(render_size[0] / dpi, render_size[1] / dpi), dpi=dpi)
        ax = fig.add_subplot(111, projection="3d")
        if filled.any():
            ax.voxels(
                filled,
                facecolors=colors,
                edgecolor=(0.0, 0.0, 0.0, 0.15),
                linewidth=0.15,
            )

        # Preserve real aspect ratio (X × Z (length) × Y (height)).
        ax.set_box_aspect((W, L, H))
        ax.view_init(elev=view[0], azim=view[1])
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

        raw = io.BytesIO()
        fig.savefig(
            raw,
            format="png",
            transparent=True,
            bbox_inches="tight",
            pad_inches=0.0,
        )
    finally:
        if fig is not None:
            plt.close(fig)

    raw.seek(0)
    img = Image.open(raw).convert("RGBA")

    if img.size != size:
        img = img.resize(size, Image.LANCZOS)

    if not transparent_bg:
        bg = Image.new("RGBA", img.size, bg_rgba)
        bg.alpha_composite(img)
        img = bg

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=False, compress_level=6)
    return out.getvalue()
