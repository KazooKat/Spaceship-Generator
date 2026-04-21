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
