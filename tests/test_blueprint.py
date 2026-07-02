"""Tests for the blueprint stage — ShipPlan construction."""

from __future__ import annotations

import numpy as np

from spaceship_generator.shape.blueprint import (
    MASSING,
    ShipPlan,
    build_plan,
)
from spaceship_generator.shape.core import ShapeParams
from spaceship_generator.structure_styles import HullStyle


def _plan(seed: int = 42, params: ShapeParams | None = None,
          hull_style: HullStyle | None = None) -> ShipPlan:
    rng = np.random.default_rng(seed)
    return build_plan(rng, params or ShapeParams(), hull_style)


def test_build_plan_deterministic():
    a = _plan(7)
    b = _plan(7)
    assert a == b


def test_build_plan_seed_varies():
    assert _plan(1) != _plan(2)


def test_segments_cover_hull_z_range_contiguously():
    params = ShapeParams()
    plan = _plan(42, params)
    segs = plan.segments
    assert segs[0].z0 == plan.engine.wall_z
    assert segs[-1].z1 == params.length
    for prev, nxt in zip(segs, segs[1:], strict=False):
        assert prev.z1 == nxt.z0


def test_hull_half_at_within_bounds():
    params = ShapeParams(length=40, width_max=20, height_max=12)
    plan = _plan(42, params)
    for z in range(plan.engine.wall_z, params.length):
        half_w, half_h, exponent, y_center = plan.hull_half_at(z)
        assert 0.5 <= half_w <= params.width_max * 0.45
        assert 0.5 <= half_h <= params.height_max * 0.5
        assert exponent >= 2.0
        assert 0 <= y_center <= params.height_max - 1


def test_wing_span_leaves_grid_margin():
    params = ShapeParams(length=40, width_max=20, height_max=12)
    for seed in range(20):
        plan = _plan(seed, params)
        if not plan.wing.present:
            continue
        mid_z = (plan.wing.root_z + plan.wing.root_chord // 2)
        mid_z = min(mid_z, params.length - 1)
        half_w, _, _, _ = plan.hull_half_at(mid_z)
        # wing root starts inside hull; tip must stay >= 1 cell from edge
        cx = (params.width_max - 1) / 2.0
        tip_x = cx - half_w - plan.wing.span
        assert tip_x >= 0.0


def test_every_hull_style_has_massing_config():
    for style in HullStyle:
        assert style in MASSING


def test_nozzles_inside_hull_width():
    params = ShapeParams(length=40, width_max=20, height_max=12)
    plan = _plan(42, params)
    half_w, _, _, _ = plan.hull_half_at(plan.engine.wall_z)
    cx = (params.width_max - 1) / 2.0
    r = plan.engine.radius
    for ex in plan.engine.nozzle_xs:
        assert abs(ex - cx) + r <= half_w + r * 0.5 + 1.0


def test_wall_z_positive_and_small():
    params = ShapeParams(length=40)
    plan = _plan(42, params)
    assert 2 <= plan.engine.wall_z <= params.length // 6
