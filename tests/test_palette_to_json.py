"""Smoke tests for ``scripts/palette_to_json.py``.

Mirrors the ``subprocess.run([sys.executable, ...])`` style of
``tests/test_palette_diff.py`` and ``tests/test_palette_merge.py`` so
we exercise the real CLI entry point (argparse + ``sys.path``
insertion of ``src/`` and ``scripts/``) rather than importing the
module directly. We deliberately don't pin exact values from the
fixture palette (the corpus evolves over time) — instead we assert
the *shape* of the output: exit 0, stdout parses as JSON, and the
expected top-level keys are present.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from spaceship_generator.palette import palettes_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "palette_to_json.py"
PALETTE = palettes_dir() / "desert_oasis.yaml"


def test_palette_to_json_stdout_parses() -> None:
    """Default invocation exits 0 and stdout parses as JSON with the schema keys.

    Asserts the round-trip contract documented in the script: stdout
    is a clean JSON document (no banner pollution) that ``json.loads``
    returns as a mapping with the canonical palette schema keys
    (``name`` / ``description`` / ``blocks`` / ``preview_colors``).
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    assert PALETTE.is_file(), f"missing palette fixture: {PALETTE}"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(PALETTE)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_to_json.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    out = result.stdout
    assert out.strip(), f"palette_to_json.py produced empty stdout:\n{out!r}"

    # Stdout must parse cleanly as JSON — guards against a regression
    # where the banner / progress lines leak onto stdout and break
    # downstream ``jq`` / ``python -m json.tool`` consumers.
    parsed = json.loads(out)
    assert isinstance(parsed, dict), (
        f"palette_to_json.py stdout must parse as a JSON object, got "
        f"{type(parsed).__name__}:\n{parsed!r}"
    )

    # Canonical palette schema keys — every hand-authored palette has
    # all four. Catches a regression that drops a top-level key during
    # the YAML -> JSON round-trip.
    for key in ("name", "description", "blocks", "preview_colors"):
        assert key in parsed, (
            f"top-level key {key!r} missing from JSON document; "
            f"got keys {sorted(parsed.keys())!r}"
        )

    # ``blocks`` and ``preview_colors`` must remain mappings after the
    # round-trip — catches a regression where one of them gets coerced
    # to a list of pairs or a string.
    assert isinstance(parsed["blocks"], dict), (
        f"'blocks' must be an object in the JSON document, got "
        f"{type(parsed['blocks']).__name__}"
    )
    assert isinstance(parsed["preview_colors"], dict), (
        f"'preview_colors' must be an object in the JSON document, got "
        f"{type(parsed['preview_colors']).__name__}"
    )

    # Banner must be on stderr, not stdout, so the stdout stream stays
    # a clean JSON document.
    assert "palette_to_json.py" in result.stderr, (
        f"banner should be on stderr, got stderr:\n{result.stderr!r}"
    )
    assert "palette_to_json.py" not in out, (
        f"banner leaked onto stdout:\n{out!r}"
    )


def test_palette_to_json_writes_out_file(tmp_path: Path) -> None:
    """``--out PATH`` writes a parseable JSON file with the schema keys.

    The output file must exist on disk after the script returns,
    be non-empty, and parse as a JSON object with the canonical
    palette schema keys — guards against a regression where the
    ``--out`` path silently writes a half-formed document.
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"
    assert PALETTE.is_file(), f"missing palette fixture: {PALETTE}"

    out_path = tmp_path / "desert_oasis.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(PALETTE),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"palette_to_json.py --out exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert out_path.is_file(), (
        f"palette_to_json.py did not create the --out file: {out_path}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert out_path.stat().st_size > 0, (
        f"palette_to_json.py produced empty file at {out_path}"
    )

    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), (
        f"--out file must contain a JSON object, got "
        f"{type(parsed).__name__}"
    )
    for key in ("name", "description", "blocks", "preview_colors"):
        assert key in parsed, (
            f"top-level key {key!r} missing from --out JSON file; "
            f"got keys {sorted(parsed.keys())!r}"
        )


def test_palette_to_json_bad_input_exits_one(tmp_path: Path) -> None:
    """Nonexistent input path exits 1 with a stderr diagnostic.

    Guards the documented exit-1 contract: a load failure must be
    reported to stderr and not silently produce a stdout document.
    """
    assert SCRIPT.is_file(), f"missing script: {SCRIPT}"

    missing = tmp_path / "does_not_exist.yaml"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(missing)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 1, (
        f"palette_to_json.py on a missing file should exit 1, got "
        f"{result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert result.stderr.strip(), (
        "palette_to_json.py on a missing file should write a stderr "
        "diagnostic, got empty stderr"
    )
    assert not result.stdout.strip(), (
        f"palette_to_json.py on a missing file should not write to "
        f"stdout, got:\n{result.stdout!r}"
    )
