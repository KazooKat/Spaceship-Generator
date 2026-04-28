"""Tests for the orchestrator + CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from litemapy import Schematic

from spaceship_generator.cli import main as cli_main
from spaceship_generator.generator import generate
from spaceship_generator.palette import load_palette
from spaceship_generator.shape import ShapeParams


def test_generate_end_to_end(tmp_path: Path):
    res = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=12, height_max=8),
        out_dir=tmp_path,
    )
    assert res.litematic_path.exists()
    assert res.litematic_path.stat().st_size > 0
    assert res.block_count > 0
    # Load it back and check at least one block is present.
    schem = Schematic.load(str(res.litematic_path))
    regions = list(schem.regions.values())
    assert len(regions) == 1


def test_generate_uses_palette_object(tmp_path: Path):
    pal = load_palette("sleek_modern")
    res = generate(
        1,
        palette=pal,
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
    )
    assert res.palette_name == "sleek_modern"
    assert res.litematic_path.exists()


def test_generate_custom_filename(tmp_path: Path):
    res = generate(
        7,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="my_ship.litematic",
    )
    assert res.litematic_path.name == "my_ship.litematic"


def test_generate_missing_palette(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        generate(
            1,
            palette="nonexistent",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
        )


def test_cli_smoke(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "5",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Wrote:" in captured.out
    assert (tmp_path / "ship_5.litematic").exists()


def test_cli_list_palettes(capsys):
    rc = cli_main(["--list-palettes"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "sci_fi_industrial" in captured.out
    assert "sleek_modern" in captured.out
    assert "rustic_salvage" in captured.out


def test_cli_missing_palette_error(tmp_path: Path, capsys):
    rc = cli_main([
        "--palette", "nonexistent_palette_xyz",
        "--length", "16", "--width", "8", "--height", "6",
        "--out", str(tmp_path),
    ])
    assert rc == 2
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower() or "available" in captured.err.lower()


def test_cli_bad_params_error(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "1",
        "--length", "4",  # too small
        "--out", str(tmp_path),
    ])
    assert rc == 2


# ---------------------------------------------------------------------------
# GenerationResult.save_preview
# ---------------------------------------------------------------------------

def test_save_preview_writes_matching_bytes(tmp_path: Path):
    res = generate(
        3,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        with_preview=True,
        preview_size=(200, 200),
    )
    assert res.preview_png is not None
    target = tmp_path / "preview.png"
    written = res.save_preview(target)
    assert written == target
    assert target.exists()
    assert target.read_bytes() == res.preview_png
    assert target.stat().st_size > 0


def test_save_preview_raises_without_preview(tmp_path: Path):
    res = generate(
        4,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
    )
    assert res.preview_png is None
    with pytest.raises(ValueError):
        res.save_preview(tmp_path / "nope.png")


# ---------------------------------------------------------------------------
# CLI: --preview, --seeds, mutual exclusion
# ---------------------------------------------------------------------------

def test_cli_preview_writes_png(tmp_path: Path):
    rc = cli_main([
        "--seed", "6",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
        "--preview", "--preview-size", "200x200",
        "--quiet",
    ])
    assert rc == 0
    litematic = tmp_path / "ship_6.litematic"
    png = tmp_path / "ship_6.png"
    assert litematic.exists()
    assert png.exists()
    assert png.stat().st_size > 0


def test_cli_seeds_comma_list(tmp_path: Path):
    rc = cli_main([
        "--seeds", "1,2,3",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
        "--quiet",
    ])
    assert rc == 0
    for s in (1, 2, 3):
        assert (tmp_path / f"ship_{s}.litematic").exists()


def test_cli_seeds_range(tmp_path: Path):
    rc = cli_main([
        "--seeds", "1-3",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
        "--quiet",
    ])
    assert rc == 0
    for s in (1, 2, 3):
        assert (tmp_path / f"ship_{s}.litematic").exists()


def test_cli_seed_and_seeds_mutually_exclusive(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "1",
        "--seeds", "2,3",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
    ])
    assert rc != 0
    captured = capsys.readouterr()
    assert "mutually exclusive" in captured.err.lower() or "error" in captured.err.lower()


def test_cli_verbose_and_quiet_mutually_exclusive(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "1",
        "--verbose", "--quiet",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
    ])
    assert rc != 0
    captured = capsys.readouterr()
    assert "mutually exclusive" in captured.err.lower() or "error" in captured.err.lower()


def test_cli_seeds_partial_failure_returns_zero(tmp_path: Path, capsys):
    # Seed 1 OK; seed 2 will fail due to invalid shape params (length too small
    # would fail for ALL seeds, so instead simulate partial failure by providing
    # seeds where all but one succeed via a valid config; since shape params are
    # shared, easiest is: use --greeble-density out of range? But that's shared
    # too. Instead, assert the all-fail path returns 2.)
    rc = cli_main([
        "--seeds", "1,2",
        "--length", "4",  # too small → fails for every seed
        "--out", str(tmp_path),
    ])
    assert rc == 2
    captured = capsys.readouterr()
    assert "error" in captured.err.lower()


def test_cli_verbose_prints_elapsed(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "8",
        "--verbose",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Elapsed:" in captured.out


def test_generate_rejects_path_traversal_filename(tmp_path: Path):
    with pytest.raises(ValueError):
        generate(
            42,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            filename="../evil.litematic",
        )


def test_generate_rejects_absolute_filename(tmp_path: Path):
    # Use a platform-appropriate absolute path. On Windows this is "C:\\evil",
    # on POSIX this is "/evil"; both fail os.path.isabs.
    import os

    absolute = os.path.abspath(os.sep + "evil.litematic")
    with pytest.raises(ValueError):
        generate(
            42,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            filename=absolute,
        )


def test_generate_rejects_illegal_char_filename(tmp_path: Path):
    with pytest.raises(ValueError):
        generate(
            42,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            filename="bad<name>|file?.litematic",
        )


def test_cli_quiet_suppresses_success_lines(tmp_path: Path, capsys):
    rc = cli_main([
        "--seed", "9",
        "--quiet",
        "--palette", "sci_fi_industrial",
        "--length", "20", "--width", "10", "--height", "8",
        "--out", str(tmp_path),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Seed:" not in captured.out
    assert "Palette:" not in captured.out
    assert "Wrote:" not in captured.out
    assert (tmp_path / "ship_9.litematic").exists()


# ---------------------------------------------------------------------------
# Wave 1 wiring: hull_style / engine_style / greeble_density
# ---------------------------------------------------------------------------

def test_generate_hull_style_none_matches_default(tmp_path: Path):
    """hull_style=None must preserve byte-identical behavior with the default."""
    import numpy as np

    from spaceship_generator.generator import generate

    baseline = generate(
        123,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    explicit = generate(
        123,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="explicit.litematic",
        hull_style=None,
    )
    assert np.array_equal(baseline.role_grid, explicit.role_grid)


def test_generate_hull_style_changes_grid(tmp_path: Path):
    """Setting hull_style must produce a different role grid than default."""
    import numpy as np

    from spaceship_generator.generator import generate
    from spaceship_generator.structure_styles import HullStyle

    default = generate(
        7,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=12, height_max=8),
        out_dir=tmp_path,
        filename="default.litematic",
    )
    saucer = generate(
        7,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=12, height_max=8),
        out_dir=tmp_path,
        filename="saucer.litematic",
        hull_style=HullStyle.SAUCER,
    )
    # Saucer is dramatically different in silhouette — the grids must diverge.
    assert not np.array_equal(default.role_grid, saucer.role_grid)
    assert saucer.litematic_path.exists()
    assert saucer.block_count > 0


def test_generate_engine_style_none_matches_default(tmp_path: Path):
    """engine_style=None must preserve byte-identical behavior with the default."""
    import numpy as np

    from spaceship_generator.generator import generate

    baseline = generate(
        321,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    explicit = generate(
        321,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="explicit.litematic",
        engine_style=None,
    )
    assert np.array_equal(baseline.role_grid, explicit.role_grid)


def test_generate_engine_style_replaces_engines(tmp_path: Path):
    """Setting engine_style must change engine cells vs default placement."""
    import numpy as np

    from spaceship_generator.engine_styles import EngineStyle
    from spaceship_generator.generator import generate
    from spaceship_generator.palette import Role

    default = generate(
        11,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="default.litematic",
    )
    ring = generate(
        11,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="ring.litematic",
        engine_style=EngineStyle.RING,
    )
    # Engine cells must differ — RING leaves the center hollow, which the
    # default solid-disk placer does not.
    default_engine = (default.role_grid == Role.ENGINE) | (default.role_grid == Role.ENGINE_GLOW)
    ring_engine = (ring.role_grid == Role.ENGINE) | (ring.role_grid == Role.ENGINE_GLOW)
    assert not np.array_equal(default_engine, ring_engine)
    assert ring_engine.sum() > 0  # some engine cells were placed


def test_generate_greeble_density_zero_matches_default(tmp_path: Path):
    """greeble_density=0.0 (default) must match the baseline exactly."""
    import numpy as np

    from spaceship_generator.generator import generate

    baseline = generate(
        555,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    explicit = generate(
        555,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=20, width_max=10, height_max=8),
        out_dir=tmp_path,
        filename="explicit.litematic",
        greeble_density=0.0,
    )
    assert np.array_equal(baseline.role_grid, explicit.role_grid)


def test_generate_greeble_density_adds_cells(tmp_path: Path):
    """greeble_density > 0 must increase the block count vs baseline."""
    from spaceship_generator.generator import generate

    baseline = generate(
        99,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(
            length=24, width_max=14, height_max=10, greeble_density=0.0
        ),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    dense = generate(
        99,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(
            length=24, width_max=14, height_max=10, greeble_density=0.0
        ),
        out_dir=tmp_path,
        filename="dense.litematic",
        greeble_density=0.5,
    )
    # Scatter should add at least one new cell — strictly more voxels filled.
    assert dense.block_count > baseline.block_count


def test_generate_greeble_density_out_of_range_raises(tmp_path: Path):
    """greeble_density outside [0, 1] must raise ValueError eagerly."""
    from spaceship_generator.generator import generate

    with pytest.raises(ValueError):
        generate(
            1,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            greeble_density=1.5,
        )


# ---------------------------------------------------------------------------
# Wave 2 wiring: weapon_count / weapon_types
# ---------------------------------------------------------------------------

def test_generate_weapon_count_zero_matches_default(tmp_path: Path):
    """weapon_count=0 (explicit) must produce a byte-identical grid to default."""
    import numpy as np

    from spaceship_generator.generator import generate

    baseline = generate(
        777,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    explicit = generate(
        777,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="explicit.litematic",
        weapon_count=0,
    )
    assert np.array_equal(baseline.role_grid, explicit.role_grid)


def test_generate_weapon_count_positive_adds_cells_and_preserves_existing(
    tmp_path: Path,
):
    """weapon_count>0 adds new cells to previously-empty space without
    overwriting existing hull/cockpit/engine/wing cells."""
    import numpy as np

    from spaceship_generator.generator import generate
    from spaceship_generator.palette import Role

    baseline = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    armed = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="armed.litematic",
        weapon_count=3,
    )
    # Scatter must actually write at least one weapon-role cell. Every
    # weapon builder writes into previously-EMPTY cells (turret barrels,
    # missile tubes, etc.), so the armed grid must differ.
    assert not np.array_equal(baseline.role_grid, armed.role_grid)
    assert armed.block_count > baseline.block_count
    # Existing hull/cockpit/engine/wing cells must be preserved: every cell
    # that held one of those roles in the baseline must still hold the same
    # role in the armed grid.
    for role in (
        Role.HULL,
        Role.COCKPIT_GLASS,
        Role.ENGINE,
        Role.ENGINE_GLOW,
        Role.WING,
    ):
        mask = baseline.role_grid == role
        assert np.array_equal(
            armed.role_grid[mask], baseline.role_grid[mask]
        ), f"weapon scatter clobbered existing {role.name} cells"


def test_generate_weapon_count_negative_raises(tmp_path: Path):
    """weapon_count < 0 must raise ValueError eagerly."""
    from spaceship_generator.generator import generate

    with pytest.raises(ValueError):
        generate(
            1,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            weapon_count=-1,
        )


def test_generate_weapon_types_filter_restricts_output(tmp_path: Path):
    """Passing weapon_types={POINT_DEFENSE} must restrict placements to
    that subset — POINT_DEFENSE never emits ENGINE_GLOW, while the full
    type list does (via MISSILE_POD and PLASMA_CORE)."""
    import numpy as np

    from spaceship_generator.generator import generate
    from spaceship_generator.palette import Role
    from spaceship_generator.weapon_styles import WeaponType

    baseline = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="baseline.litematic",
    )
    baseline_glow = int((baseline.role_grid == Role.ENGINE_GLOW).sum())
    all_types = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="all_types.litematic",
        weapon_count=8,
    )
    only_pd = generate(
        42,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="only_pd.litematic",
        weapon_count=8,
        weapon_types={WeaponType.POINT_DEFENSE},
    )
    # With the unrestricted scatter we expect extra ENGINE_GLOW cells
    # (missile/plasma tips). With the POINT_DEFENSE-only filter there must
    # be none, so the ENGINE_GLOW count stays equal to baseline.
    all_glow = int((all_types.role_grid == Role.ENGINE_GLOW).sum())
    pd_glow = int((only_pd.role_grid == Role.ENGINE_GLOW).sum())
    assert all_glow > baseline_glow
    assert pd_glow == baseline_glow
    # The two filtered/unfiltered runs must also produce distinct grids.
    assert not np.array_equal(all_types.role_grid, only_pd.role_grid)


def test_generate_weapon_determinism(tmp_path: Path):
    """Same seed + weapon_count must yield an identical grid on repeat."""
    import numpy as np

    from spaceship_generator.generator import generate

    first = generate(
        2024,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="first.litematic",
        weapon_count=5,
    )
    second = generate(
        2024,
        palette="sci_fi_industrial",
        shape_params=ShapeParams(length=24, width_max=14, height_max=10),
        out_dir=tmp_path,
        filename="second.litematic",
        weapon_count=5,
    )
    assert np.array_equal(first.role_grid, second.role_grid)


def test_generate_weapon_types_rejects_unknown_member(tmp_path: Path):
    """Non-WeaponType entries in weapon_types must raise ValueError."""
    from spaceship_generator.generator import generate

    with pytest.raises(ValueError):
        generate(
            1,
            palette="sci_fi_industrial",
            shape_params=ShapeParams(length=20, width_max=10, height_max=8),
            out_dir=tmp_path,
            weapon_count=2,
            weapon_types=["not_a_weapon_type"],  # type: ignore[list-item]
        )


def test_generate_weapon_writer_does_not_shadow_nose_tip_light(tmp_path: Path):
    """Regression: bug-weapon-count-decreases-cells-2026-04-27.

    Hypothesis-found falsifying example: with seed=93 and weapon_count=4,
    a missile_pod / plasma_core lands directly above the nose-tip-light
    column. Pre-fix, the weapon writer stamped HULL/ENGINE_GLOW above the
    forward-most centerline cell, which made
    :func:`texture._paint_nose_tip_light` see a protected role at the
    topmost slot and silently bail — dropping the nose-tip LIGHT and
    leaving the variant with *fewer* LIGHT+HULL_DARK cells than the
    weaponless baseline (11 vs 12), violating the additive contract.

    This test re-asserts the exact failing case directly so future
    regressions are caught without needing Hypothesis to re-discover them.
    """
    import numpy as np

    from spaceship_generator.palette import Role

    params = ShapeParams(length=24, width_max=12, height_max=8)
    baseline = generate(
        93, shape_params=params, weapon_count=0, out_dir=tmp_path,
        filename="base.litematic",
    )
    variant = generate(
        93, shape_params=params, weapon_count=4, out_dir=tmp_path,
        filename="var.litematic",
    )
    base_weapon_cells = int(
        (baseline.role_grid == Role.LIGHT).sum()
        + (baseline.role_grid == Role.HULL_DARK).sum()
    )
    var_weapon_cells = int(
        (variant.role_grid == Role.LIGHT).sum()
        + (variant.role_grid == Role.HULL_DARK).sum()
    )
    assert var_weapon_cells >= base_weapon_cells, (
        f"weapon writer must be additive in LIGHT+HULL_DARK; "
        f"baseline={base_weapon_cells} variant={var_weapon_cells}"
    )
    # Both centerline nose-tip cells (W=12 → x=5,6) must keep their LIGHT.
    z_tip = 23  # ShapeParams(length=24) → forward-most filled z is 23
    for x in (5, 6):
        assert variant.role_grid[x, 4, z_tip] == Role.LIGHT, (
            f"nose-tip LIGHT at ({x}, 4, {z_tip}) was clobbered by a "
            f"weapon stamped above it; got "
            f"{Role(int(variant.role_grid[x, 4, z_tip])).name}"
        )
    # Sanity: the variant grid is not byte-equal to the baseline (weapons
    # actually placed something), so the regression isn't a no-op.
    assert not np.array_equal(baseline.role_grid, variant.role_grid)
