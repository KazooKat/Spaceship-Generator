"""Render a role grid as an isometric PNG preview using matplotlib."""

from __future__ import annotations

import io
from numbers import Real

import matplotlib

matplotlib.use("Agg")  # headless — safe for Flask/CLI

# M1 (iter3): use matplotlib's object-oriented API instead of pyplot. pyplot
# maintains a global figure registry that is not thread-safe; this function is
# called from Flask request handlers that may run on threaded WSGI workers
# (gunicorn --threads, waitress), so two concurrent renders can race on the
# registry and leak figures or close the wrong handle. The OO API keeps each
# render self-contained.
import numpy as np  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402, F401 — registers '3d' projection
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
    azimuth_deg: float | None = None,
    elevation_deg: float | None = None,
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

    Camera control:
      ``view``: legacy ``(elevation, azimuth)`` tuple, still honored as the
        baseline when the new kwargs are ``None``. Default ``(22.0, -62.0)``
        preserves the established isometric look.
      ``elevation_deg`` / ``azimuth_deg``: optional overrides (in degrees) for
        matplotlib's ``ax.view_init``. When ``None`` (the default), the
        corresponding component of ``view`` is used — so the default call
        produces byte-identical output to previous versions. Must be finite
        when provided.
    """
    if role_grid.ndim != 3:
        raise ValueError(f"role_grid must be 3D, got shape {role_grid.shape}")
    # M4 (iter3) — guard against zero-/negative-sized dimensions which would
    # otherwise crash deep in matplotlib's set_box_aspect or in PIL.Image.new
    # with a confusing error. Mirrors the upfront check in export.py.
    if any(d <= 0 for d in role_grid.shape):
        raise ValueError(
            f"role_grid dims must be positive, got {role_grid.shape}"
        )
    # L2 (iter3) — validate size upfront so callers get a clear message
    # instead of a matplotlib "figure size must be positive" stack trace.
    if not (isinstance(size, tuple) and len(size) == 2):
        raise ValueError(f"size must be a (width, height) tuple, got {size!r}")
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError(f"size must be positive, got {size!r}")

    # L1 (iter3) — coerce view components through float() so non-numeric
    # inputs raise ValueError (the advertised contract) instead of TypeError
    # from numpy's ufunc dispatcher. Same treatment for the dedicated kwargs
    # below.
    try:
        view_elev = float(view[0])
        view_azim = float(view[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("view angles must be finite") from exc
    if not np.isfinite(view_elev) or not np.isfinite(view_azim):
        raise ValueError("view angles must be finite")
    if elevation_deg is not None:
        try:
            elevation_deg = float(elevation_deg)
        except (TypeError, ValueError) as exc:
            raise ValueError("elevation_deg must be finite") from exc
        if not np.isfinite(elevation_deg):
            raise ValueError("elevation_deg must be finite")
    if azimuth_deg is not None:
        try:
            azimuth_deg = float(azimuth_deg)
        except (TypeError, ValueError) as exc:
            raise ValueError("azimuth_deg must be finite") from exc
        if not np.isfinite(azimuth_deg):
            raise ValueError("azimuth_deg must be finite")

    elev = view_elev if elevation_deg is None else elevation_deg
    azim = view_azim if azimuth_deg is None else azimuth_deg

    # M2 (iter3) — accept "transparent" case-insensitively and tolerate
    # whitespace from config files / query strings. Without this, "Transparent"
    # would fall through to _parse_hex_color and surface a misleading
    # "must be #rrggbb" error.
    transparent_bg = (
        isinstance(background, str) and background.strip().lower() == "transparent"
    )
    if not transparent_bg:
        bg_rgba = _parse_hex_color(background)
    else:
        bg_rgba = None

    # M3 (iter3) — validate color_override entries before they hit a numpy
    # assignment. The natural failure mode is a (3,)-vs-(N,4) broadcast error
    # deep in the loop below; surfacing it here names the offending role.
    if color_override:
        for role_key, rgba in color_override.items():
            try:
                length = len(rgba)
            except TypeError as exc:
                raise ValueError(
                    f"color_override[{role_key!r}] must be a 4-tuple of "
                    f"numbers, got {rgba!r}"
                ) from exc
            if length != 4 or not all(isinstance(c, Real) for c in rgba):
                raise ValueError(
                    f"color_override[{role_key!r}] must be a 4-tuple of "
                    f"numbers, got {rgba!r}"
                )

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

    # M1 (iter3) — use the OO Figure API directly so concurrent Flask workers
    # don't race on pyplot's global figure registry.
    fig = Figure(
        figsize=(render_size[0] / dpi, render_size[1] / dpi),
        dpi=dpi,
    )
    canvas = FigureCanvasAgg(fig)
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
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

        # H2 (iter3) — drop bbox_inches="tight". The tight crop made savefig
        # honour the 3-D plot's content bounding box instead of the requested
        # figsize, so the antialias 2× supersample factor advertised in the
        # docstring degraded to a content-dependent (often <2×) resample —
        # and for tall/narrow ships it even *upscaled*, making the render
        # blurrier instead of sharper. Relying on subplots_adjust(0,0,1,1)
        # alone keeps the canvas exactly at render_size so the subsequent
        # Lanczos resize to ``size`` is always a true 2× downsample.
        raw = io.BytesIO()
        fig.savefig(
            raw,
            format="png",
            transparent=True,
            pad_inches=0.0,
        )
    finally:
        # Release matplotlib-side artists / cyclic refs. ``fig`` would
        # normally be garbage-collected once the local goes out of scope, but
        # the 3-D axes can hold large voxel arrays via the artist tree;
        # clearing here keeps memory bounded under repeated calls.
        fig.clear()
        # canvas backreferences fig — drop it so refcount falls cleanly.
        del canvas

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
