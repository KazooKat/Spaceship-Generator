"""Tests for the ``--output-json`` CLI flag.

Each test invokes :func:`main` directly (no subprocess) and captures stdout
via ``capsys`` so the JSON lines can be parsed and asserted on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from spaceship_generator.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SMALL_ARGS = [
    "--palette", "sci_fi_industrial",
    "--length", "20",
    "--width", "10",
    "--height", "8",
]

_REQUIRED_KEYS = {"seed", "palette", "shape", "blocks", "path"}


# ---------------------------------------------------------------------------
# --output-json: single seed
# ---------------------------------------------------------------------------


def test_output_json_single(tmp_path: Path, capsys):
    """``--seed 42 --output-json`` emits exactly one valid JSON line on stdout
    with the required keys: seed, palette, shape, blocks, path."""
    rc = main(
        ["--seed", "42", "--output-json", "--out", str(tmp_path)] + _SMALL_ARGS
    )
    assert rc == 0

    captured = capsys.readouterr()
    # Collect non-empty lines that look like JSON (start with '{').
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(json_lines) == 1, (
        f"Expected exactly 1 JSON line, got {len(json_lines)}:\n{captured.out}"
    )

    obj = json.loads(json_lines[0])
    assert _REQUIRED_KEYS <= obj.keys(), (
        f"Missing keys {_REQUIRED_KEYS - obj.keys()} in: {obj}"
    )
    assert obj["seed"] == 42
    assert isinstance(obj["palette"], str)
    assert isinstance(obj["shape"], list) and len(obj["shape"]) == 3
    assert isinstance(obj["blocks"], int) and obj["blocks"] > 0
    assert obj["path"].endswith(".litematic")


# ---------------------------------------------------------------------------
# --output-json: multi-seed (NDJSON)
# ---------------------------------------------------------------------------


def test_output_json_multi(tmp_path: Path, capsys):
    """``--seeds 1,2 --output-json`` emits two JSON lines (one per ship),
    each valid and carrying the required keys."""
    rc = main(
        ["--seeds", "1,2", "--output-json", "--out", str(tmp_path)] + _SMALL_ARGS
    )
    assert rc == 0

    captured = capsys.readouterr()
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(json_lines) == 2, (
        f"Expected exactly 2 JSON lines, got {len(json_lines)}:\n{captured.out}"
    )

    seeds_seen: set[int] = set()
    for raw in json_lines:
        obj = json.loads(raw)
        assert _REQUIRED_KEYS <= obj.keys(), (
            f"Missing keys {_REQUIRED_KEYS - obj.keys()} in: {obj}"
        )
        assert isinstance(obj["seed"], int)
        assert isinstance(obj["palette"], str)
        assert isinstance(obj["shape"], list) and len(obj["shape"]) == 3
        assert isinstance(obj["blocks"], int) and obj["blocks"] > 0
        assert obj["path"].endswith(".litematic")
        seeds_seen.add(obj["seed"])

    # The two lines must correspond to the two distinct requested seeds.
    assert seeds_seen == {1, 2}


# ---------------------------------------------------------------------------
# --seed-phrase
# ---------------------------------------------------------------------------


def test_seed_phrase_deterministic(tmp_path):
    """Same phrase resolves to the same integer seed both times."""
    import hashlib
    import subprocess

    subprocess.run(
        [
            sys.executable,
            "-m",
            "spaceship_generator",
            "--seed-phrase",
            "enterprise",
            "--out",
            str(tmp_path / "a"),
        ]
        + _SMALL_ARGS,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "spaceship_generator",
            "--seed-phrase",
            "enterprise",
            "--out",
            str(tmp_path / "b"),
        ]
        + _SMALL_ARGS,
        capture_output=True,
        check=True,
    )
    # Both runs must produce a litematic file.
    files_a = list((tmp_path / "a").glob("*.litematic"))
    files_b = list((tmp_path / "b").glob("*.litematic"))
    assert files_a and files_b
    # The resolved seed must be deterministic: same filename (seed embedded).
    assert files_a[0].name == files_b[0].name
    # The expected seed value is the SHA-256 hash mod 2^31-1.
    expected_seed = (
        int(hashlib.sha256(b"enterprise").hexdigest(), 16) % (2**31 - 1)
    )
    assert f"ship_{expected_seed}.litematic" == files_a[0].name


def test_seed_phrase_mutually_exclusive_with_seed(tmp_path):
    """--seed-phrase and --seed together must exit non-zero."""
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "spaceship_generator",
            "--seed",
            "42",
            "--seed-phrase",
            "hello",
            "--out",
            str(tmp_path),
        ]
        + _SMALL_ARGS,
        capture_output=True,
    )
    assert result.returncode != 0
