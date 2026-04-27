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


# ---------------------------------------------------------------------------
# --no-greebles shortcut
# ---------------------------------------------------------------------------


def test_cli_no_greebles_shortcut_runs(tmp_path: Path):
    """``--no-greebles`` runs cleanly (equivalent to ``--greeble-density 0``)
    and writes a .litematic file with no traceback."""
    rc = main(
        ["--no-greebles", "--seed", "42", "--out", str(tmp_path)] + _SMALL_ARGS
    )
    assert rc == 0
    files = list(tmp_path.glob("*.litematic"))
    assert files, "expected at least one .litematic written under --no-greebles"


def test_cli_no_greebles_conflicts_with_density(tmp_path: Path, capsys):
    """Passing both ``--no-greebles`` and ``--greeble-density`` exits non-zero
    via ``parser.error`` with the mutual-exclusion message."""
    import pytest

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--no-greebles",
                "--greeble-density",
                "0.3",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    # argparse's parser.error() exits with status 2.
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    # Error message lands on stderr.
    assert "--no-greebles" in captured.err
    assert "--greeble-density" in captured.err
    assert "mutually exclusive" in captured.err


# ---------------------------------------------------------------------------
# --hull-style-front / --hull-style-rear (shapes-B)
# ---------------------------------------------------------------------------


def test_cli_hull_blend_flags_run(tmp_path: Path):
    """``--hull-style-front X --hull-style-rear Y`` runs cleanly and writes a file."""
    rc = main(
        [
            "--hull-style-front",
            "arrow",
            "--hull-style-rear",
            "saucer",
            "--seed",
            "42",
            "--out",
            str(tmp_path),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0
    files = list(tmp_path.glob("*.litematic"))
    assert files, "expected at least one .litematic for the blend run"


def test_cli_hull_blend_invalid_choice_rejected(tmp_path: Path, capsys):
    """An unknown style name on either flag must be rejected by argparse.

    argparse prints to stderr and raises ``SystemExit(2)`` on bad choices.
    """
    import pytest

    with pytest.raises(SystemExit):
        main(
            [
                "--hull-style-front",
                "not_a_real_style",
                "--hull-style-rear",
                "saucer",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    err = capsys.readouterr().err
    # argparse error mentions the offending flag.
    assert "--hull-style-front" in err or "invalid choice" in err


def test_cli_hull_blend_deterministic_per_seed(tmp_path: Path, capsys):
    """Same seed + same blend flags emit identical ``--output-json`` summaries.

    The litematic file format embeds a creation timestamp inside its NBT
    metadata, so byte-comparing two saved schematics will always disagree.
    Instead we drive the CLI's ``--output-json`` flag — its summary lines
    are stable for a given (seed, palette, shape, blocks) tuple — and pin
    that two runs with the same blend flags emit identical JSON payloads.
    """
    import json

    args_common = [
        "--hull-style-front",
        "arrow",
        "--hull-style-rear",
        "saucer",
        "--seed",
        "1234",
        "--quiet",
        "--output-json",
    ] + _SMALL_ARGS

    rc_a = main(args_common + ["--out", str(tmp_path / "a")])
    out_a = capsys.readouterr().out
    rc_b = main(args_common + ["--out", str(tmp_path / "b")])
    out_b = capsys.readouterr().out
    assert rc_a == 0 and rc_b == 0

    obj_a = json.loads(
        next(line for line in out_a.splitlines() if line.startswith("{"))
    )
    obj_b = json.loads(
        next(line for line in out_b.splitlines() if line.startswith("{"))
    )
    # ``path`` differs only by the parent dir; the blend-determined fields
    # — seed, palette, shape, blocks — must match exactly.
    for key in ("seed", "palette", "shape", "blocks"):
        assert obj_a[key] == obj_b[key], (
            f"blend run is not deterministic on key {key!r}: "
            f"{obj_a[key]} != {obj_b[key]}"
        )


def test_cli_hull_blend_only_front_falls_back_to_legacy(tmp_path: Path, capsys):
    """Passing only ``--hull-style-front`` (no rear) must NOT engage the blend.

    Per the documented contract, the run must produce the same generated
    voxel grid as a fully-default run on the same seed. We compare the
    summary fields exposed by ``--output-json`` rather than raw schematic
    bytes (the litematic NBT carries a per-write creation timestamp).
    """
    import json

    args_common = [
        "--seed",
        "9001",
        "--quiet",
        "--output-json",
    ] + _SMALL_ARGS

    # Front-only: should fall back to legacy hull, identical to no flag.
    rc_partial = main(
        args_common
        + ["--hull-style-front", "arrow", "--out", str(tmp_path / "partial")]
    )
    out_partial = capsys.readouterr().out
    rc_baseline = main(args_common + ["--out", str(tmp_path / "baseline")])
    out_baseline = capsys.readouterr().out
    assert rc_partial == 0 and rc_baseline == 0

    obj_p = json.loads(
        next(line for line in out_partial.splitlines() if line.startswith("{"))
    )
    obj_b = json.loads(
        next(line for line in out_baseline.splitlines() if line.startswith("{"))
    )
    # Same shape and same blocks count — proves the legacy hull placer ran
    # in both cases (a real blend would change the voxel count).
    for key in ("seed", "palette", "shape", "blocks"):
        assert obj_p[key] == obj_b[key], (
            f"partial blend pair must fall back to legacy single-style "
            f"behaviour, but {key!r} differs: {obj_p[key]} != {obj_b[key]}"
        )


# ---------------------------------------------------------------------------
# --hull-noise (shapes-E)
# ---------------------------------------------------------------------------


def test_cli_hull_noise_runs(tmp_path: Path):
    """``--hull-noise 0.5`` runs cleanly and writes a litematic file."""
    rc = main(
        [
            "--hull-noise",
            "0.5",
            "--seed",
            "42",
            "--out",
            str(tmp_path),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0
    files = list(tmp_path.glob("*.litematic"))
    assert files, "expected at least one .litematic for the noise run"


def test_cli_hull_noise_rejects_negative(tmp_path: Path, capsys):
    """``--hull-noise -0.1`` is rejected by argparse (exit code 2)."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--hull-noise",
                "-0.1",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "--hull-noise" in err or "[0.0, 1.0]" in err


def test_cli_hull_noise_rejects_above_one(tmp_path: Path, capsys):
    """``--hull-noise 1.5`` is rejected by argparse (exit code 2)."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--hull-noise",
                "1.5",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    assert exc_info.value.code == 2


def test_cli_hull_noise_zero_matches_baseline(tmp_path: Path, capsys):
    """``--hull-noise 0.0`` must produce the same JSON summary as no flag.

    The .litematic file embeds a creation timestamp so we compare the
    ``--output-json`` summary fields instead of raw bytes — those are
    stable for a given (seed, palette, shape, blocks) tuple.
    """
    args_common = [
        "--seed",
        "9911",
        "--quiet",
        "--output-json",
    ] + _SMALL_ARGS

    rc_zero = main(
        args_common + ["--hull-noise", "0.0", "--out", str(tmp_path / "z")]
    )
    out_zero = capsys.readouterr().out
    rc_baseline = main(args_common + ["--out", str(tmp_path / "b")])
    out_baseline = capsys.readouterr().out
    assert rc_zero == 0 and rc_baseline == 0

    obj_z = json.loads(
        next(line for line in out_zero.splitlines() if line.startswith("{"))
    )
    obj_b = json.loads(
        next(line for line in out_baseline.splitlines() if line.startswith("{"))
    )
    for key in ("seed", "palette", "shape", "blocks"):
        assert obj_z[key] == obj_b[key], (
            f"--hull-noise 0.0 must match no-flag baseline, but "
            f"{key!r} differs: {obj_z[key]} != {obj_b[key]}"
        )


def test_cli_hull_noise_changes_block_count(tmp_path: Path, capsys):
    """``--hull-noise 0.7`` perturbs the grid → block count differs."""
    args_common = [
        "--seed",
        "9912",
        "--quiet",
        "--output-json",
    ] + _SMALL_ARGS

    rc_noisy = main(
        args_common + ["--hull-noise", "0.7", "--out", str(tmp_path / "n")]
    )
    out_noisy = capsys.readouterr().out
    rc_baseline = main(args_common + ["--out", str(tmp_path / "b")])
    out_baseline = capsys.readouterr().out
    assert rc_noisy == 0 and rc_baseline == 0

    obj_n = json.loads(
        next(line for line in out_noisy.splitlines() if line.startswith("{"))
    )
    obj_b = json.loads(
        next(line for line in out_baseline.splitlines() if line.startswith("{"))
    )
    # Same seed + same dims → seed/palette/shape stay equal, but the noise
    # post-pass eroded/grew at least one cell so the total block count
    # cannot match exactly.
    assert obj_n["seed"] == obj_b["seed"]
    assert obj_n["shape"] == obj_b["shape"]
    assert obj_n["blocks"] != obj_b["blocks"]


# ---------------------------------------------------------------------------
# --list-shape-styles
# ---------------------------------------------------------------------------


def test_cli_list_shape_styles(capsys):
    """``--list-shape-styles`` prints HullStyle / EngineStyle / WingStyle
    grouped, one member per line, in enum-declaration order, exit 0.

    Membership is asserted via enum iteration (no hard-coded string lists)
    so the test does not drift when a new style is added.
    """
    from spaceship_generator.engine_styles import EngineStyle
    from spaceship_generator.structure_styles import HullStyle
    from spaceship_generator.wing_styles import WingStyle

    rc = main(["--list-shape-styles"])
    assert rc == 0

    out = capsys.readouterr().out
    lines = out.splitlines()

    # All three group headers present.
    assert "Hull styles:" in lines
    assert "Engine styles:" in lines
    assert "Wing styles:" in lines

    # Every enum member appears in the output (indent-by-two format).
    for h in HullStyle:
        assert f"  {h.value}" in lines, f"missing HullStyle.{h.name}"
    for e in EngineStyle:
        assert f"  {e.value}" in lines, f"missing EngineStyle.{e.name}"
    for w in WingStyle:
        assert f"  {w.value}" in lines, f"missing WingStyle.{w.name}"

    # Deterministic order: members appear in enum-declaration order under
    # their respective headers.
    def _slice_under(header: str) -> list[str]:
        i = lines.index(header)
        # Collect indented lines that follow until the next group header
        # (or EOF). Headers are unindented, members are indented by two.
        out: list[str] = []
        for line in lines[i + 1 :]:
            if line.startswith("  "):
                out.append(line[2:])
            else:
                break
        return out

    assert _slice_under("Hull styles:") == [h.value for h in HullStyle]
    assert _slice_under("Engine styles:") == [e.value for e in EngineStyle]
    assert _slice_under("Wing styles:") == [w.value for w in WingStyle]

    # Narrower than --list-styles: cockpit/weapon sections must NOT appear.
    assert "Cockpit styles:" not in lines
    assert "Weapon types:" not in lines
