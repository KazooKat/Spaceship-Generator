"""Tests for the matplotlib preview renderer."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from spaceship_generator.palette import Role, load_palette
from spaceship_generator.preview import render_preview
from spaceship_generator.shape import ShapeParams, generate_shape
from spaceship_generator.texture import assign_roles


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def role_grid():
    g = generate_shape(
        11, ShapeParams(length=20, width_max=10, height_max=8, greeble_density=0.0)
    )
    return assign_roles(g)


@pytest.fixture
def palette():
    return load_palette("sci_fi_industrial")


def _open_rgba(data: bytes) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(data)).convert("RGBA"))


def _grayscale_step_count(data: bytes, threshold: int = 64) -> int:
    """Count row-adjacent grayscale jumps >= ``threshold`` across the image."""
    im = np.array(Image.open(io.BytesIO(data)).convert("L")).astype(int)
    diffs = np.abs(np.diff(im, axis=1))
    return int((diffs >= threshold).sum())


def test_render_preview_returns_png_bytes(role_grid, palette):
    data = render_preview(role_grid, palette, size=(300, 300))
    assert isinstance(data, bytes)
    assert len(data) > 200
    assert data.startswith(PNG_MAGIC)


def test_render_preview_empty_grid(palette):
    g = np.zeros((5, 5, 5), dtype=np.int8)
    data = render_preview(g, palette, size=(200, 200))
    # Still returns a PNG (blank).
    assert data.startswith(PNG_MAGIC)


def test_render_preview_full_grid(palette):
    g = np.full((4, 4, 4), Role.HULL, dtype=np.int8)
    data = render_preview(g, palette, size=(200, 200))
    assert data.startswith(PNG_MAGIC)


def test_render_preview_rejects_non_3d(palette):
    with pytest.raises(ValueError):
        render_preview(np.zeros((4, 4)), palette)


def test_render_preview_rejects_nonfinite_view(palette):
    g = np.zeros((3, 3, 3), dtype=np.int8)
    g[0, 0, 0] = Role.HULL
    with pytest.raises(ValueError):
        render_preview(g, palette, view=(float("nan"), -62.0))
    with pytest.raises(ValueError):
        render_preview(g, palette, view=(22.0, float("inf")))


# ----- New tests for antialias / specular / background --------------------


def test_default_preview_has_correct_dimensions(role_grid, palette):
    data = render_preview(role_grid, palette, size=(256, 256))
    assert len(data) > 0
    im = Image.open(io.BytesIO(data))
    assert im.size == (256, 256)


def test_antialias_reduces_high_frequency_steps(role_grid, palette):
    on = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        antialias=True,
        specular=False,
        background="#0d0f12",
    )
    off = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        antialias=False,
        specular=False,
        background="#0d0f12",
    )
    # Antialiased output should have strictly fewer sharp (>=64) grayscale
    # jumps along rows than the non-antialiased render.
    assert _grayscale_step_count(on) < _grayscale_step_count(off)


def test_specular_increases_bright_pixels(role_grid, palette):
    on = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        antialias=False,
        specular=True,
        background="transparent",
    )
    off = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        antialias=False,
        specular=False,
        background="transparent",
    )
    im_on = _open_rgba(on)
    im_off = _open_rgba(off)
    # Bright = perceptually-bright opaque pixels (mean RGB > 150).
    def bright_count(arr: np.ndarray) -> int:
        mean_rgb = arr[..., :3].mean(axis=-1)
        opaque = arr[..., 3] > 0
        return int(((mean_rgb > 150) & opaque).sum())

    assert bright_count(im_on) > bright_count(im_off)


def test_transparent_background_preserves_alpha(role_grid, palette):
    data = render_preview(
        role_grid,
        palette,
        size=(200, 200),
        background="transparent",
    )
    im = _open_rgba(data)
    # Some pixels must have alpha < 255 (outside the ship silhouette).
    assert (im[..., 3] < 255).any()


def test_hex_background_is_opaque(role_grid, palette):
    data = render_preview(
        role_grid,
        palette,
        size=(200, 200),
        background="#0d0f12",
    )
    im = _open_rgba(data)
    # All pixels fully opaque when a solid hex background is supplied.
    assert int(im[..., 3].min()) == 255
    # Corner pixels should be the specified background color.
    corner = im[0, 0, :3].tolist()
    assert corner == [13, 15, 18]


def test_render_is_deterministic(role_grid, palette):
    a = render_preview(role_grid, palette, size=(250, 250))
    b = render_preview(role_grid, palette, size=(250, 250))
    assert a == b


def test_legacy_call_signature_still_works(role_grid, palette):
    # Only the original (pre-change) keyword args: size, view, color_override.
    data = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        view=(22.0, -62.0),
        color_override=None,
    )
    assert data.startswith(PNG_MAGIC)
    im = Image.open(io.BytesIO(data))
    assert im.size == (300, 300)


def test_default_within_2pct_of_legacy_baseline(role_grid, palette):
    """The default render (new features on) must remain visually close to the
    pre-change baseline (legacy: antialias off, specular off, same bg). The
    subtle specular boost + Lanczos downsample should only introduce small
    per-pixel deltas — fewer than 2% of pixels should differ by more than a
    perceptually noticeable amount (RGB max-channel diff > 32)."""
    legacy = render_preview(
        role_grid,
        palette,
        size=(300, 300),
        antialias=False,
        specular=False,
        background="#0d0f12",
    )
    default = render_preview(role_grid, palette, size=(300, 300))  # all defaults

    im_legacy = _open_rgba(legacy)
    im_default = _open_rgba(default)
    assert im_legacy.shape == im_default.shape

    rgb_diff = np.abs(
        im_legacy[..., :3].astype(np.int16) - im_default[..., :3].astype(np.int16)
    ).max(axis=-1)
    pct_large_diff = float((rgb_diff > 32).mean()) * 100.0
    assert pct_large_diff < 2.0
