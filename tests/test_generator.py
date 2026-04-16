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
