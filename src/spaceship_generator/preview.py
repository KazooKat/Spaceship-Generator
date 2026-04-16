"""Render a role grid as an isometric PNG preview using matplotlib."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # headless — safe for Flask/CLI

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .palette import Palette, Role  # noqa: E402


def render_preview(
    role_grid: np.ndarray,
    palette: Palette,
    *,
    size: tuple[int, int] = (800, 800),
    view: tuple[float, float] = (22.0, -62.0),
    color_override: dict | None = None,
) -> bytes:
    """Return PNG bytes of an isometric voxel render of ``role_grid``.

    ``role_grid`` is indexed ``grid[x, y, z]`` (Y-up). Matplotlib's 3-D axes
    use Z-up, so axes are swapped for display.

    ``color_override`` optionally maps ``Role -> (r, g, b, a)`` tuples (values
    in 0-1). When provided, it takes precedence over ``palette.preview_color``
    for the given roles. Used by the web UI to render with approximated
    Minecraft block colors instead of the stylized palette colors.
    """
    if role_grid.ndim != 3:
        raise ValueError(f"role_grid must be 3D, got shape {role_grid.shape}")

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

    dpi = 100
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi)
    try:
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

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            transparent=True,
            bbox_inches="tight",
            pad_inches=0.0,
        )
    finally:
        plt.close(fig)

    return buf.getvalue()
