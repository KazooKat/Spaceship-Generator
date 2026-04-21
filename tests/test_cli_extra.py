"""Extra coverage tests for :mod:`spaceship_generator.cli`.

Targets the argparse-helper edge cases (``_parse_preview_size`` and
``_parse_seeds``), the bulk-mode success-line separator, the
no-palettes-found branch of ``--list-palettes``, and the
``__main__``-style module entry point.
"""

from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from spaceship_generator import cli
from spaceship_generator.cli import _parse_preview_size, _parse_seeds, main

# ----------- _parse_preview_size -----------


def test_parse_preview_size_happy_path():
    assert _parse_preview_size("800x600") == (800, 600)
    # Case-insensitive
    assert _parse_preview_size("1024X768") == (1024, 768)


def test_parse_preview_size_rejects_non_wxh():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_preview_size("800")


def test_parse_preview_size_rejects_too_many_parts():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_preview_size("800x600x400")


def test_parse_preview_size_rejects_non_integers():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_preview_size("fooxbar")


def test_parse_preview_size_rejects_zero_or_negative():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_preview_size("0x600")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_preview_size("-1x600")


# ----------- _parse_seeds -----------


def test_parse_seeds_single_int():
    assert _parse_seeds("42") == [42]


def test_parse_seeds_comma_list():
    assert _parse_seeds("1,2,3") == [1, 2, 3]


def test_parse_seeds_range_inclusive():
    assert _parse_seeds("0-3") == [0, 1, 2, 3]


def test_parse_seeds_mixed_comma_and_range():
    assert _parse_seeds("1,3-4,9") == [1, 3, 4, 9]


def test_parse_seeds_tolerates_whitespace_and_empty_tokens():
    # Empty tokens from ``", ,1, ,"`` must be silently skipped.
    assert _parse_seeds(" 1 , , 3-4 ") == [1, 3, 4]


def test_parse_seeds_rejects_empty():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("   ")


def test_parse_seeds_rejects_all_empty_tokens():
    """A string of only commas yields no values and must error."""
    with pytest.raises(argparse.ArgumentTypeError, match="produced no values"):
        _parse_seeds(",,,")


def test_parse_seeds_rejects_bad_range_shape():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("1-")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("-5")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("1-2-3")


def test_parse_seeds_rejects_non_integer_range():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("a-b")


def test_parse_seeds_rejects_reversed_range():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("5-3")


def test_parse_seeds_rejects_non_integer_token():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seeds("1,abc,2")


# ----------- main: --list-palettes empty dir -----------


def test_main_list_palettes_empty(monkeypatch, tmp_path: Path, capsys):
    """When the palettes directory is empty, main prints the friendly line."""
    # Force list_palettes to return []: patch the module-level reference the
    # CLI imported at module-load time.
    monkeypatch.setattr(cli, "list_palettes", lambda: [])
    rc = main(["--list-palettes"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "(no palettes found)" in out


# ----------- main: bulk-mode blank-line separator + preview output -----------


def test_main_bulk_mode_prints_blank_line_between_seeds(tmp_path: Path, capsys):
    """Non-quiet bulk runs emit a blank line between successful seeds."""
    rc = main(
        [
            "--seeds",
            "1,2",
            "--palette",
            "sci_fi_industrial",
            "--length",
            "20",
            "--width",
            "10",
            "--height",
            "8",
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Two "Seed:" lines separated by a blank line.
    assert out.count("Seed:") == 2
    assert "\n\n" in out


def test_main_preview_line_in_success_output(tmp_path: Path, capsys):
    """``--preview`` without ``--quiet`` prints a 'Preview: ...' line."""
    rc = main(
        [
            "--seed",
            "11",
            "--palette",
            "sci_fi_industrial",
            "--length",
            "20",
            "--width",
            "10",
            "--height",
            "8",
            "--preview",
            "--preview-size",
            "100x100",
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Preview:" in out
    assert "ship_11.png" in out


# ----------- main: random seed picked when --seed omitted -----------


def test_main_random_seed_used_when_none_given(
    monkeypatch, tmp_path: Path, capsys
):
    """If ``--seed`` is omitted and ``--seeds`` too, ``random.randint`` is used."""
    monkeypatch.setattr(cli.random, "randint", lambda a, b: 4242)
    rc = main(
        [
            "--palette",
            "sci_fi_industrial",
            "--length",
            "20",
            "--width",
            "10",
            "--height",
            "8",
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Seed: 4242" in out
    assert (tmp_path / "ship_4242.litematic").exists()


# ----------- main: partial failure exit code (seeds) -----------


def test_main_seeds_partial_failure_returns_one(
    monkeypatch, tmp_path: Path, capsys
):
    """Mix of successes and failures → exit code 1."""
    original_run_one = cli._run_one
    seen_seeds: list[int] = []

    def _flaky(seed, *, args, filename):
        seen_seeds.append(seed)
        if seed == 2:
            raise ValueError("boom on 2")
        return original_run_one(seed, args=args, filename=filename)

    monkeypatch.setattr(cli, "_run_one", _flaky)
    rc = main(
        [
            "--seeds",
            "1,2,3",
            "--palette",
            "sci_fi_industrial",
            "--length",
            "20",
            "--width",
            "10",
            "--height",
            "8",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "seed=2" in err
    assert seen_seeds == [1, 2, 3]


def test_main_missing_palette_in_bulk_mode_does_not_list_palettes(
    monkeypatch, tmp_path: Path, capsys
):
    """In bulk mode, a FileNotFoundError should NOT print 'Available palettes:'."""
    rc = main(
        [
            "--seeds",
            "1,2",
            "--palette",
            "nonexistent_palette_xyz",
            "--length",
            "16",
            "--width",
            "8",
            "--height",
            "6",
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    # Every seed fails; the friendly "Available palettes:" hint is only
    # emitted in single-seed mode, not in bulk.
    assert "Available palettes" not in err


# ----------- __main__.py entry -----------


def test_dunder_main_executes_cli():
    """``python -m spaceship_generator --list-palettes`` must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "spaceship_generator", "--list-palettes"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "sci_fi_industrial" in result.stdout


def test_dunder_main_module_import(monkeypatch):
    """Importing ``__main__.py`` as a module must expose ``main``."""
    import spaceship_generator.__main__ as dunder

    assert dunder.main is cli.main


def test_cli_module_runpy_smoke(monkeypatch, tmp_path: Path):
    """Running ``-m spaceship_generator`` via ``runpy`` covers the __main__ guard.

    ``runpy.run_module(..., run_name='__main__')`` triggers the
    ``if __name__ == '__main__': raise SystemExit(main())`` branch without
    spawning a subprocess, so coverage picks it up. We pass ``--list-palettes``
    via ``sys.argv`` and expect ``SystemExit(0)``.
    """
    monkeypatch.setattr(
        sys, "argv", ["spaceship_generator", "--list-palettes"]
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("spaceship_generator", run_name="__main__")
    assert excinfo.value.code == 0


# ----------- new style flags + --list-styles -----------


def _stub_generate(monkeypatch, calls: list[dict]):
    """Install a ``cli.generate`` stub that records kwargs and returns a
    minimal :class:`GenerationResult`-compatible object.

    ``calls`` is a mutable list the test owns; each invocation appends its
    kwargs so the test can assert on what the CLI forwarded.
    """
    import numpy as np

    from spaceship_generator.generator import GenerationResult

    def _fake_generate(seed, **kwargs):
        calls.append({"seed": seed, **kwargs})
        out_dir = kwargs.get("out_dir")
        filename = kwargs.get("filename") or f"ship_{seed}.litematic"
        path = Path(out_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub")
        return GenerationResult(
            seed=seed,
            palette_name="stub_palette",
            litematic_path=path,
            role_grid=np.zeros((2, 2, 2), dtype=np.int8),
        )

    monkeypatch.setattr(cli, "generate", _fake_generate)
    return calls


def test_list_styles_prints_all_enum_values(capsys):
    """``--list-styles`` prints every hull/engine/wing style name."""
    from spaceship_generator.engine_styles import EngineStyle
    from spaceship_generator.structure_styles import HullStyle
    from spaceship_generator.wing_styles import WingStyle

    rc = main(["--list-styles"])
    assert rc == 0
    out = capsys.readouterr().out
    # Section headers
    assert "Hull styles:" in out
    assert "Engine styles:" in out
    assert "Wing styles:" in out
    # Every enum value appears in the output.
    for h in HullStyle:
        assert h.value in out
    for e in EngineStyle:
        assert e.value in out
    for w in WingStyle:
        assert w.value in out


def test_hull_style_forwards_enum_to_generate(monkeypatch, tmp_path: Path):
    """``--hull-style whale`` is converted to ``HullStyle.WHALE`` and passed through."""
    from spaceship_generator.structure_styles import HullStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "7",
            "--hull-style",
            "whale",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["hull_style"] == HullStyle.WHALE
    # When not set, engine_style forwards as None.
    assert calls[0]["engine_style"] is None


def test_engine_style_forwards_enum_to_generate(monkeypatch, tmp_path: Path):
    """``--engine-style twin_nacelle`` is converted to the EngineStyle enum."""
    from spaceship_generator.engine_styles import EngineStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "9",
            "--engine-style",
            "twin_nacelle",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["engine_style"] == EngineStyle.TWIN_NACELLE
    assert calls[0]["hull_style"] is None


def test_wing_style_forwards_to_shape_params(monkeypatch, tmp_path: Path):
    """``--wing-style delta`` flows into ``ShapeParams.wing_style``."""
    from spaceship_generator.wing_styles import WingStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "11",
            "--wing-style",
            "delta",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["shape_params"].wing_style == WingStyle.DELTA


def test_greeble_density_forwards_to_generate_and_shape_params(
    monkeypatch, tmp_path: Path
):
    """``--greeble-density 0.3`` should appear at both the generator level
    and (capped at 0.5) inside ``ShapeParams``."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "13",
            "--greeble-density",
            "0.3",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["greeble_density"] == pytest.approx(0.3)
    assert calls[0]["shape_params"].greeble_density == pytest.approx(0.3)


def test_greeble_density_default_none_preserves_legacy_behavior(
    monkeypatch, tmp_path: Path
):
    """When ``--greeble-density`` is omitted, shape_params keeps the legacy
    default 0.05 and the generator-level scatter stays at 0.0."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(["--seed", "17", "--out", str(tmp_path), "--quiet"])
    assert rc == 0
    assert len(calls) == 1
    # Legacy in-shape default.
    assert calls[0]["shape_params"].greeble_density == pytest.approx(0.05)
    # Post-build scatter stays off.
    assert calls[0]["greeble_density"] == pytest.approx(0.0)


def test_invalid_hull_style_exits_non_zero(capsys):
    """``--hull-style foo`` must be rejected by argparse (exit code 2)."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--hull-style", "foo"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "--hull-style" in err or "invalid choice" in err


def test_invalid_engine_style_exits_non_zero(capsys):
    """``--engine-style bogus`` must be rejected by argparse."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--engine-style", "bogus"])
    assert excinfo.value.code != 0


def test_greeble_density_rejects_out_of_range(capsys):
    """``--greeble-density 1.5`` must be rejected at parse time."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--greeble-density", "1.5"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "greeble-density" in err.lower() or "0.0, 1.0" in err


def test_greeble_density_rejects_negative(capsys):
    """Negative densities are out of range."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--greeble-density", "-0.1"])
    assert excinfo.value.code != 0


def test_greeble_density_rejects_non_float(capsys):
    """Non-numeric strings fail parse."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--greeble-density", "huge"])
    assert excinfo.value.code != 0


def test_help_documents_new_flags(capsys):
    """``--help`` output lists the four new flags."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--hull-style", "--engine-style", "--wing-style",
                 "--greeble-density", "--list-styles"):
        assert flag in out


# ----------- weapon + fleet flags -----------


def test_parse_weapon_types_happy_path():
    """Valid comma-list parses into trimmed tokens."""
    from spaceship_generator.cli import _parse_weapon_types

    assert _parse_weapon_types("turret_large,missile_pod") == [
        "turret_large",
        "missile_pod",
    ]
    # Whitespace + empties dropped.
    assert _parse_weapon_types(" turret_large , ,missile_pod ") == [
        "turret_large",
        "missile_pod",
    ]


def test_parse_weapon_types_rejects_empty():
    """Empty input must fail at parse time."""
    from spaceship_generator.cli import _parse_weapon_types

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_weapon_types("")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_weapon_types(",,,")


def test_parse_nonneg_int_rejects_negative_and_non_int():
    """``--weapon-count`` helper enforces ``>= 0``."""
    from spaceship_generator.cli import _parse_nonneg_int

    assert _parse_nonneg_int("0") == 0
    assert _parse_nonneg_int("5") == 5
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_nonneg_int("-1")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_nonneg_int("abc")


def test_parse_pos_int_rejects_zero_and_negative():
    """``--fleet-count`` helper enforces ``>= 1``."""
    from spaceship_generator.cli import _parse_pos_int

    assert _parse_pos_int("1") == 1
    assert _parse_pos_int("7") == 7
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_pos_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_pos_int("-3")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_pos_int("xyz")


def test_list_styles_includes_weapon_types_when_module_available(capsys):
    """``--list-styles`` should list weapon types when ``weapon_styles`` is
    importable."""
    rc = main(["--list-styles"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Weapon types:" in out
    # Every enum value from weapon_styles appears in the output.
    from spaceship_generator.weapon_styles import WeaponType

    for wt in WeaponType:
        assert wt.value in out


def test_list_styles_when_weapon_module_missing_prints_unavailable(
    monkeypatch, capsys
):
    """``weapon_styles`` being ``None`` must print a stderr fallback line
    and omit the ``Weapon types:`` header."""
    monkeypatch.setattr(cli, "_weapon_styles", None)
    monkeypatch.setattr(cli, "_weapon_styles_error", "simulated missing")
    rc = main(["--list-styles"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Weapon types:" not in captured.out
    assert "weapon_styles unavailable" in captured.err
    assert "simulated missing" in captured.err


def test_weapon_count_zero_does_not_call_scatter(monkeypatch, tmp_path: Path):
    """``--weapon-count 0`` (the default) must never invoke the scatter,
    so legacy single-ship runs aren't slowed down."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    scatter_calls: list[tuple] = []

    def _tracking_scatter(*args, **kwargs):
        scatter_calls.append((args, kwargs))
        return []

    monkeypatch.setattr(
        cli._weapon_styles, "scatter_weapons", _tracking_scatter
    )
    rc = main(
        [
            "--seed",
            "31",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert scatter_calls == []


def test_weapon_count_invokes_scatter_and_restricts_types(
    monkeypatch, tmp_path: Path
):
    """``--weapon-count 4 --weapon-types X,Y`` forwards the count and the
    enum allow-list to ``scatter_weapons``."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    from spaceship_generator.weapon_styles import WeaponType

    seen: dict = {}

    def _fake_scatter(shape, rng, count, *, types=None):
        seen["count"] = count
        seen["types"] = list(types) if types is not None else None
        return []  # zero placements → re-export is skipped

    monkeypatch.setattr(cli._weapon_styles, "scatter_weapons", _fake_scatter)
    rc = main(
        [
            "--seed",
            "33",
            "--weapon-count",
            "4",
            "--weapon-types",
            "turret_large,missile_pod",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert seen["count"] == 4
    assert seen["types"] == [WeaponType.TURRET_LARGE, WeaponType.MISSILE_POD]


def test_weapon_unknown_type_warns_and_keeps_known(monkeypatch, tmp_path: Path, capsys):
    """Unknown ``--weapon-types`` tokens surface a stderr warning but the
    known tokens still get through to the scatter."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    from spaceship_generator.weapon_styles import WeaponType

    seen: dict = {}

    def _fake_scatter(shape, rng, count, *, types=None):
        seen["types"] = list(types) if types is not None else None
        return []

    monkeypatch.setattr(cli._weapon_styles, "scatter_weapons", _fake_scatter)
    rc = main(
        [
            "--seed",
            "35",
            "--weapon-count",
            "2",
            "--weapon-types",
            "turret_large,not_a_weapon",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert seen["types"] == [WeaponType.TURRET_LARGE]
    err = capsys.readouterr().err
    assert "unknown --weapon-types" in err
    assert "not_a_weapon" in err


def test_weapon_count_without_module_prints_unavailable(
    monkeypatch, tmp_path: Path, capsys
):
    """If ``weapon_styles`` is missing, ``--weapon-count 2`` logs a stderr
    fallback line but the ship itself still gets written."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    monkeypatch.setattr(cli, "_weapon_styles", None)
    monkeypatch.setattr(cli, "_weapon_styles_error", "not installed")

    rc = main(
        [
            "--seed",
            "37",
            "--weapon-count",
            "2",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1  # base ship still generated
    err = capsys.readouterr().err
    assert "weapons unavailable" in err
    assert "not installed" in err


def test_fleet_count_greater_than_one_generates_n_files(
    monkeypatch, tmp_path: Path
):
    """``--fleet-count 3`` produces three ``ship_<seed>_<i>.litematic`` files
    with distinct per-ship seeds."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "101",
            "--fleet-count",
            "3",
            "--fleet-size-tier",
            "small",
            "--fleet-style-coherence",
            "1.0",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    # Exactly three generator calls and three files on disk.
    assert len(calls) == 3
    files = sorted(p.name for p in tmp_path.iterdir())
    assert len(files) == 3
    for i, name in enumerate(files):
        assert name.endswith(f"_{i}.litematic") or f"_{i}.litematic" in name
    # Every filename is of the shape ship_<seed>_<i>.litematic.
    assert all(f.startswith("ship_") for f in files)


def test_fleet_style_coherence_forwards_to_fleet_params(monkeypatch, tmp_path: Path):
    """The coherence value reaches ``fleet.FleetParams`` unchanged."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    from spaceship_generator import fleet as fleet_mod

    observed: dict = {}
    real_generate_fleet = fleet_mod.generate_fleet

    def _spy_generate_fleet(params):
        observed["count"] = params.count
        observed["tier"] = params.size_tier
        observed["coherence"] = params.style_coherence
        observed["palette"] = params.palette
        observed["seed"] = params.seed
        return real_generate_fleet(params)

    monkeypatch.setattr(cli._fleet, "generate_fleet", _spy_generate_fleet)

    rc = main(
        [
            "--seed",
            "202",
            "--fleet-count",
            "2",
            "--fleet-size-tier",
            "mid",
            "--fleet-style-coherence",
            "0.25",
            "--palette",
            "sci_fi_industrial",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert observed["count"] == 2
    assert observed["tier"] == "mid"
    assert observed["coherence"] == pytest.approx(0.25)
    assert observed["palette"] == "sci_fi_industrial"
    assert observed["seed"] == 202


def test_fleet_count_one_preserves_single_ship_behavior(
    monkeypatch, tmp_path: Path
):
    """``--fleet-count 1`` is the legacy default: no fleet module use, and
    a single ``ship_<seed>.litematic`` is written."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    # If the fleet branch were taken it would call generate_fleet — trip a
    # sentinel to catch the regression.
    from spaceship_generator import fleet as fleet_mod

    tripped: list[bool] = []

    def _tripwire(params):  # pragma: no cover - should not fire
        tripped.append(True)
        return fleet_mod.generate_fleet(params)

    monkeypatch.setattr(cli._fleet, "generate_fleet", _tripwire)

    rc = main(
        [
            "--seed",
            "303",
            "--fleet-count",
            "1",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert tripped == []
    assert (tmp_path / "ship_303.litematic").exists()


def test_fleet_without_module_prints_unavailable_and_falls_back(
    monkeypatch, tmp_path: Path, capsys
):
    """If ``fleet`` is missing, ``--fleet-count 3`` logs a warning and
    falls back to single-ship generation so the run still produces output."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    monkeypatch.setattr(cli, "_fleet", None)
    monkeypatch.setattr(cli, "_fleet_error", "module absent")

    rc = main(
        [
            "--seed",
            "404",
            "--fleet-count",
            "3",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "fleet unavailable" in err
    assert "module absent" in err
    # Fallback path: a single legacy ship gets written.
    assert len(calls) == 1
    assert (tmp_path / "ship_404.litematic").exists()


def test_fleet_and_seeds_are_mutually_exclusive(monkeypatch, tmp_path: Path, capsys):
    """``--fleet-count > 1`` together with ``--seeds`` must error out (2)."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seeds",
            "1,2",
            "--fleet-count",
            "3",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "mutually exclusive" in err
    assert calls == []


def test_fleet_count_rejects_zero(capsys):
    """``--fleet-count 0`` violates the ``>= 1`` constraint."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--fleet-count", "0"])
    assert excinfo.value.code != 0


def test_weapon_count_rejects_negative(capsys):
    """``--weapon-count -1`` violates the ``>= 0`` constraint."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--weapon-count", "-1"])
    assert excinfo.value.code != 0


def test_help_documents_new_weapon_and_fleet_flags(capsys):
    """``--help`` output lists every new flag added in this wave."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for flag in (
        "--weapon-count",
        "--weapon-types",
        "--fleet-count",
        "--fleet-size-tier",
        "--fleet-style-coherence",
    ):
        assert flag in out


def test_generator_without_new_params_falls_back(monkeypatch, tmp_path: Path, capsys):
    """If ``generate`` doesn't accept ``hull_style``/``engine_style``/
    ``greeble_density``, the CLI falls back to the legacy signature and
    emits a warning on stderr."""
    import numpy as np

    from spaceship_generator.generator import GenerationResult

    calls: list[dict] = []

    def _legacy_generate(seed, **kwargs):
        # Refuse the new kwargs on the first call; accept on the retry.
        for new_kwarg in ("hull_style", "engine_style", "greeble_density"):
            if new_kwarg in kwargs:
                raise TypeError(
                    f"generate() got an unexpected keyword argument {new_kwarg!r}"
                )
        calls.append({"seed": seed, **kwargs})
        out_dir = kwargs.get("out_dir")
        filename = kwargs.get("filename") or f"ship_{seed}.litematic"
        path = Path(out_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub")
        return GenerationResult(
            seed=seed,
            palette_name="stub_palette",
            litematic_path=path,
            role_grid=np.zeros((2, 2, 2), dtype=np.int8),
        )

    monkeypatch.setattr(cli, "generate", _legacy_generate)

    rc = main(
        [
            "--seed",
            "21",
            "--hull-style",
            "arrow",
            "--engine-style",
            "ring",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    # The second (legacy) call succeeded.
    assert len(calls) == 1
    # Legacy signature has none of the new kwargs.
    assert "hull_style" not in calls[0]
    assert "engine_style" not in calls[0]
    # Warning surfaced to stderr.
    err = capsys.readouterr().err
    assert "Warning" in err and "--hull-style" in err


# ----------- --cockpit-style flag -----------


def test_list_styles_includes_all_cockpit_styles(capsys):
    """``--list-styles`` prints a ``Cockpit styles:`` section listing every
    :class:`CockpitStyle` value (3 originals + 3 new = 6 total)."""
    from spaceship_generator.shape import CockpitStyle

    rc = main(["--list-styles"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Cockpit styles:" in out
    expected = {
        "bubble",
        "pointed",
        "integrated",
        "canopy_dome",
        "wrap_bridge",
        "offset_turret",
    }
    # Sanity-check the enum itself carries exactly these 6 values.
    assert {c.value for c in CockpitStyle} == expected
    for value in expected:
        assert value in out


def test_cockpit_style_bubble_forwards_to_generate(monkeypatch, tmp_path: Path):
    """``--cockpit-style bubble`` forwards ``CockpitStyle.BUBBLE`` to
    ``generate()`` and sets it on ``ShapeParams`` too."""
    from spaceship_generator.shape import CockpitStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "51",
            "--cockpit-style",
            "bubble",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cockpit_style"] == CockpitStyle.BUBBLE
    assert calls[0]["shape_params"].cockpit_style == CockpitStyle.BUBBLE


def test_cockpit_style_wrap_bridge_forwards_to_generate(
    monkeypatch, tmp_path: Path
):
    """``--cockpit-style wrap_bridge`` forwards the new enum member through."""
    from spaceship_generator.shape import CockpitStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "53",
            "--cockpit-style",
            "wrap_bridge",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cockpit_style"] == CockpitStyle.WRAP_BRIDGE
    assert calls[0]["shape_params"].cockpit_style == CockpitStyle.WRAP_BRIDGE


def test_invalid_cockpit_style_exits_non_zero(capsys):
    """``--cockpit-style foo`` must be rejected by argparse (exit code 2)."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--cockpit-style", "foo"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "--cockpit-style" in err or "invalid choice" in err


def test_cockpit_style_omitted_preserves_legacy_behavior(
    monkeypatch, tmp_path: Path
):
    """Without ``--cockpit-style``, the CLI does NOT forward a
    ``cockpit_style`` kwarg and ``ShapeParams.cockpit_style`` falls back to
    the ``--cockpit`` default (``BUBBLE``). This keeps the legacy
    auto-selection path byte-for-byte identical."""
    from spaceship_generator.shape import CockpitStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(["--seed", "57", "--out", str(tmp_path), "--quiet"])
    assert rc == 0
    assert len(calls) == 1
    # No new-style override forwarded when the flag is omitted.
    assert "cockpit_style" not in calls[0]
    # ShapeParams still gets the legacy ``--cockpit`` default.
    assert calls[0]["shape_params"].cockpit_style == CockpitStyle.BUBBLE


def test_cockpit_style_typeerror_fallback_warns_and_retries(
    monkeypatch, tmp_path: Path, capsys
):
    """If ``generate`` rejects ``cockpit_style`` kwarg, the CLI warns on
    stderr and retries with the legacy signature — mirroring the
    hull/engine/greeble fallback."""
    import numpy as np

    from spaceship_generator.generator import GenerationResult

    calls: list[dict] = []

    def _legacy_generate(seed, **kwargs):
        if "cockpit_style" in kwargs:
            raise TypeError(
                "generate() got an unexpected keyword argument 'cockpit_style'"
            )
        calls.append({"seed": seed, **kwargs})
        out_dir = kwargs.get("out_dir")
        filename = kwargs.get("filename") or f"ship_{seed}.litematic"
        path = Path(out_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub")
        return GenerationResult(
            seed=seed,
            palette_name="stub_palette",
            litematic_path=path,
            role_grid=np.zeros((2, 2, 2), dtype=np.int8),
        )

    monkeypatch.setattr(cli, "generate", _legacy_generate)

    rc = main(
        [
            "--seed",
            "59",
            "--cockpit-style",
            "offset_turret",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    # The retry (legacy) call succeeded exactly once.
    assert len(calls) == 1
    assert "cockpit_style" not in calls[0]
    err = capsys.readouterr().err
    assert "Warning" in err and "--cockpit-style" in err


# ----------- --preset / --list-presets flags -----------


def test_list_presets_prints_all_names_and_exits_zero(capsys):
    """``--list-presets`` prints all 6 preset names, one per line, exit 0."""
    from spaceship_generator.presets import list_presets

    rc = main(["--list-presets"])
    assert rc == 0
    out = capsys.readouterr().out
    expected = set(list_presets())
    # Sanity-check there are exactly 6 built-in presets.
    assert expected == {
        "corvette",
        "dropship",
        "science_vessel",
        "gunship",
        "freighter_heavy",
        "interceptor",
    }
    for name in expected:
        assert name in out


def test_preset_corvette_sets_hull_engine_wing_cockpit(monkeypatch, tmp_path: Path):
    """``--preset corvette`` forwards corvette's hull/engine/wing/cockpit
    enum members to ``generate()``."""
    from spaceship_generator.engine_styles import EngineStyle
    from spaceship_generator.shape import CockpitStyle
    from spaceship_generator.structure_styles import HullStyle
    from spaceship_generator.wing_styles import WingStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "71",
            "--preset",
            "corvette",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    # Preset 'corvette' → DAGGER / TWIN_NACELLE / SWEPT / BUBBLE.
    assert calls[0]["hull_style"] == HullStyle.DAGGER
    assert calls[0]["engine_style"] == EngineStyle.TWIN_NACELLE
    assert calls[0]["shape_params"].wing_style == WingStyle.SWEPT
    assert calls[0]["shape_params"].cockpit_style == CockpitStyle.BUBBLE


def test_preset_with_explicit_hull_style_override(monkeypatch, tmp_path: Path):
    """``--preset corvette --hull-style saucer`` overrides the preset hull to
    SAUCER but keeps the rest of the preset (engine/wing/cockpit)."""
    from spaceship_generator.engine_styles import EngineStyle
    from spaceship_generator.structure_styles import HullStyle
    from spaceship_generator.wing_styles import WingStyle

    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    rc = main(
        [
            "--seed",
            "73",
            "--preset",
            "corvette",
            "--hull-style",
            "saucer",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    # Explicit flag wins — hull is SAUCER not DAGGER.
    assert calls[0]["hull_style"] == HullStyle.SAUCER
    # Remaining preset fields are preserved.
    assert calls[0]["engine_style"] == EngineStyle.TWIN_NACELLE
    assert calls[0]["shape_params"].wing_style == WingStyle.SWEPT


def test_preset_nonexistent_exits_non_zero(capsys):
    """``--preset nonexistent`` is rejected by argparse (exit code 2) because
    the choices list is restricted to the known preset names."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--preset", "nonexistent"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "--preset" in err or "invalid choice" in err


def test_preset_module_missing_fallback_does_not_crash(
    monkeypatch, tmp_path: Path, capsys
):
    """If ``presets`` is missing (partial rollout), the CLI must not crash:
    ``--list-presets`` warns and exits 0, and a normal run (no ``--preset``)
    continues to work."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    # Simulate the presets module being unavailable. We don't rebuild the
    # parser (choices were frozen at module-load), but the fallback code
    # paths in ``main`` handle a ``None`` module gracefully.
    monkeypatch.setattr(cli, "_presets", None)
    monkeypatch.setattr(cli, "_presets_error", "simulated missing")

    # --list-presets returns 0 with a stderr warning.
    rc = main(["--list-presets"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "presets unavailable" in err
    assert "simulated missing" in err

    # A normal run (no --preset) still works end-to-end.
    rc = main(
        [
            "--seed",
            "79",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1


def test_preset_greeble_weapon_overrides(monkeypatch, tmp_path: Path):
    """Individual ``--greeble-density`` and ``--weapon-count`` flags override
    the preset's values."""
    calls: list[dict] = []
    _stub_generate(monkeypatch, calls)

    # corvette preset sets greeble_density=0.1 and weapon_count=2.
    rc = main(
        [
            "--seed",
            "83",
            "--preset",
            "corvette",
            "--greeble-density",
            "0.5",
            "--weapon-count",
            "0",
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert rc == 0
    assert len(calls) == 1
    # Greeble override → 0.5 (both generator-level and shape_params).
    assert calls[0]["greeble_density"] == pytest.approx(0.5)
    assert calls[0]["shape_params"].greeble_density == pytest.approx(0.5)


def test_help_documents_preset_flags(capsys):
    """``--help`` output lists the new ``--preset`` and ``--list-presets`` flags."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--preset" in out
    assert "--list-presets" in out
