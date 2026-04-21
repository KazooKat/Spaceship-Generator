"""Tests for ``scripts/palette_lint.py``."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LINT_SCRIPT = REPO_ROOT / "scripts" / "palette_lint.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("palette_lint", LINT_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["palette_lint"] = mod
    spec.loader.exec_module(mod)
    return mod


palette_lint = _load_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from spaceship_generator.palette import REQUIRED_ROLES  # noqa: E402


def _write_full(
    path: Path,
    name: str = "test_pal",
    *,
    block_overrides: dict[str, str] | None = None,
    color_overrides: dict[str, str] | None = None,
) -> Path:
    """Write a known-clean palette YAML, with optional per-role overrides."""
    default_blocks = {
        "HULL": "minecraft:white_concrete",
        "HULL_DARK": "minecraft:black_concrete",
        "WINDOW": "minecraft:light_blue_stained_glass",
        "ENGINE": "minecraft:polished_blackstone",
        "ENGINE_GLOW": "minecraft:sea_lantern",
        "COCKPIT_GLASS": "minecraft:tinted_glass",
        "WING": "minecraft:quartz_block",
        "GREEBLE": "minecraft:smooth_quartz",
        "LIGHT": "minecraft:glowstone",
        "INTERIOR": "minecraft:white_terracotta",
    }
    default_colors = {
        "HULL": "#f2f2f2",
        "HULL_DARK": "#101010",
        "WINDOW": "#70b0ff",
        "ENGINE": "#333333",
        "ENGINE_GLOW": "#ffffff",
        "COCKPIT_GLASS": "#3a2a5a",
        "WING": "#e8e4d8",
        "GREEBLE": "#eae6d8",
        "LIGHT": "#d8e8ff",
        "INTERIOR": "#d8d0c4",
    }
    if block_overrides:
        default_blocks.update(block_overrides)
    if color_overrides:
        default_colors.update(color_overrides)

    lines = [f"name: {name}", "blocks:"]
    for role in REQUIRED_ROLES:
        lines.append(f"  {role}: {default_blocks[role]}")
    lines.append("preview_colors:")
    for role in REQUIRED_ROLES:
        lines.append(f'  {role}: "{default_colors[role]}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Shipped palettes
# ---------------------------------------------------------------------------


def test_all_shipped_palettes_have_zero_errors():
    """Every palette in ``palettes/`` must lint with 0 errors (warnings ok)."""
    paths = sorted((REPO_ROOT / "palettes").glob("*.yaml"))
    assert paths, "no shipped palettes found"
    for p in paths:
        result = palette_lint.lint_palette(p)
        assert result.errors == [], (
            f"{p.name} has errors: {result.errors}"
        )


def test_shipped_palettes_covered_by_lint_report():
    """Lint reports should cover every shipped palette (smoke check)."""
    paths = sorted((REPO_ROOT / "palettes").glob("*.yaml"))
    results = [palette_lint.lint_palette(p) for p in paths]
    assert len(results) == len(paths)
    # At least one should be completely clean (no warnings either).
    assert any(not r.errors and not r.warnings for r in results)


# ---------------------------------------------------------------------------
# Hard errors
# ---------------------------------------------------------------------------


def test_missing_hull_is_error(tmp_path: Path):
    bad = tmp_path / "no_hull.yaml"
    bad.write_text(
        "name: no_hull\nblocks:\n  HULL_DARK: minecraft:stone\n",
        encoding="utf-8",
    )
    result = palette_lint.lint_palette(bad)
    assert any("HULL" in e and "missing" in e for e in result.errors)
    # 'HULL' missing + 9 other required roles missing.
    assert len(result.errors) >= 1


def test_invalid_block_id_is_error(tmp_path: Path):
    bad = _write_full(
        tmp_path / "bad_id.yaml", block_overrides={"HULL": "NOT A BLOCK"}
    )
    result = palette_lint.lint_palette(bad)
    assert any(
        "invalid block id format" in e and "HULL" in e for e in result.errors
    )


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_duplicate_role_same_block_warns(tmp_path: Path):
    pal = _write_full(
        tmp_path / "dup.yaml",
        block_overrides={
            "WING": "minecraft:white_concrete",  # same as HULL
        },
    )
    result = palette_lint.lint_palette(pal)
    assert result.errors == []
    assert any(
        "HULL" in w and "WING" in w and "both map to" in w for w in result.warnings
    )


def test_dark_window_warns(tmp_path: Path):
    pal = _write_full(
        tmp_path / "dark_win.yaml", color_overrides={"WINDOW": "#202020"}
    )
    result = palette_lint.lint_palette(pal)
    assert result.errors == []
    assert any("WINDOW" in w and "too dark" in w for w in result.warnings)


def test_bright_window_does_not_warn(tmp_path: Path):
    pal = _write_full(
        tmp_path / "bright_win.yaml", color_overrides={"WINDOW": "#70b0ff"}
    )
    result = palette_lint.lint_palette(pal)
    assert not any("too dark" in w for w in result.warnings)


def test_low_hull_contrast_warns(tmp_path: Path):
    pal = _write_full(
        tmp_path / "low_contrast.yaml",
        color_overrides={"HULL": "#cccccc", "HULL_DARK": "#c0c0c0"},
    )
    result = palette_lint.lint_palette(pal)
    assert any(
        "HULL" in w and "HULL_DARK" in w and "contrast" in w for w in result.warnings
    )


def test_non_emissive_engine_glow_warns(tmp_path: Path):
    pal = _write_full(
        tmp_path / "bad_glow.yaml",
        block_overrides={"ENGINE_GLOW": "minecraft:cobblestone"},
    )
    result = palette_lint.lint_palette(pal)
    assert any(
        "ENGINE_GLOW" in w and "known-emissive" in w for w in result.warnings
    )


def test_known_emissive_suffixes_accepted(tmp_path: Path):
    """Both ``*_lamp`` and ``*_candle_cake`` should pass the emissive check."""
    for block in ("minecraft:redstone_lamp", "minecraft:white_candle_cake"):
        pal = _write_full(
            tmp_path / f"{block.rsplit(':', 1)[1]}.yaml",
            block_overrides={"ENGINE_GLOW": block},
        )
        result = palette_lint.lint_palette(pal)
        assert not any("known-emissive" in w for w in result.warnings), block


def test_unparseable_preview_color_warns(tmp_path: Path):
    pal = _write_full(
        tmp_path / "bad_color.yaml", color_overrides={"HULL": "not-a-hex"}
    )
    result = palette_lint.lint_palette(pal)
    assert any(
        "HULL" in w and "unparseable" in w for w in result.warnings
    )


# ---------------------------------------------------------------------------
# CLI (exit codes + format flags)
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_cli_default_exits_zero_on_shipped_palettes():
    cp = _run_cli()
    assert cp.returncode == 0, cp.stdout + cp.stderr


def test_cli_strict_flips_warnings_to_errors(tmp_path: Path):
    pal = _write_full(
        tmp_path / "warns.yaml", color_overrides={"WINDOW": "#101010"}
    )
    ok = _run_cli("--file", str(pal))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    strict = _run_cli("--file", str(pal), "--strict")
    assert strict.returncode == 1


def test_cli_errors_always_exit_one(tmp_path: Path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("name: broken\nblocks:\n  HULL: minecraft:stone\n", encoding="utf-8")
    cp = _run_cli("--file", str(bad))
    assert cp.returncode == 1


def test_cli_format_json_parses(tmp_path: Path):
    pal = _write_full(tmp_path / "ok.yaml")
    cp = _run_cli("--file", str(pal), "--format", "json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    payload = json.loads(cp.stdout)
    assert isinstance(payload, list) and len(payload) == 1
    entry = payload[0]
    assert set(entry) == {"name", "path", "errors", "warnings"}
    assert entry["errors"] == []


def test_cli_text_format_has_ok_line_for_clean(tmp_path: Path):
    pal = _write_full(tmp_path / "clean.yaml", name="clean")
    cp = _run_cli("--file", str(pal))
    assert cp.returncode == 0
    assert "clean: OK" in cp.stdout


def test_cli_text_format_summary_for_warnings(tmp_path: Path):
    pal = _write_full(
        tmp_path / "warny.yaml",
        name="warny",
        color_overrides={"WINDOW": "#101010"},
    )
    cp = _run_cli("--file", str(pal))
    assert cp.returncode == 0
    assert "warny:" in cp.stdout
    assert "warning(s)" in cp.stdout
    assert "too dark" in cp.stdout


# ---------------------------------------------------------------------------
# Internal helper coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_some",
    [
        ("#ffffff", True),
        ("#000000", True),
        ("ffffff", True),
        ("#aabbccdd", True),
        ("nope", False),
        (None, False),
        (123, False),
    ],
)
def test_parse_hex(value, expected_some):
    got = palette_lint._parse_hex(value)
    if expected_some:
        assert got is not None
        assert all(0.0 <= v <= 1.0 for v in got)
    else:
        assert got is None


def test_luminance_monotonic():
    y_black = palette_lint._yiq_luminance((0.0, 0.0, 0.0))
    y_gray = palette_lint._yiq_luminance((0.5, 0.5, 0.5))
    y_white = palette_lint._yiq_luminance((1.0, 1.0, 1.0))
    assert y_black < y_gray < y_white
    assert y_white == pytest.approx(1.0)


def test_contrast_ratio_symmetric_and_identity():
    a = (1.0, 1.0, 1.0)
    b = (0.0, 0.0, 0.0)
    r_ab = palette_lint._contrast_ratio(a, b)
    r_ba = palette_lint._contrast_ratio(b, a)
    assert r_ab == pytest.approx(r_ba)
    # Identity contrast is 1.0.
    assert palette_lint._contrast_ratio(a, a) == pytest.approx(1.0)
