"""Tests for the matplotlib preview renderer."""

from __future__ import annotations

import numpy as np
import pytest

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
