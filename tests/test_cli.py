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
# --no-weapons shortcut
# ---------------------------------------------------------------------------


def test_cli_no_weapons_resolves_to_weapon_count_zero(tmp_path: Path, capsys):
    """``--no-weapons`` end-to-end resolves to ``weapon_count=0`` — the
    written ``.litematic`` matches a baseline run with ``--weapon-count 0``
    in block count, and a separate ``--weapon-count 5`` armed run produces
    strictly more blocks (proves the weapon pass would have fired absent
    the shortcut)."""
    import json as _json

    # ``--no-weapons`` run: capture --output-json so we can read the block
    # count without poking at the .litematic.
    out_no = tmp_path / "no_weapons"
    out_no.mkdir()
    rc = main(
        [
            "--no-weapons",
            "--seed",
            "42",
            "--output-json",
            "--out",
            str(out_no),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0
    captured = capsys.readouterr()
    no_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(no_lines) == 1, (
        f"expected one --output-json line under --no-weapons, got "
        f"{len(no_lines)}:\n{captured.out}"
    )
    no_blocks = _json.loads(no_lines[0])["blocks"]
    files = list(out_no.glob("*.litematic"))
    assert files, "expected at least one .litematic written under --no-weapons"

    # Equivalent ``--weapon-count 0`` run — must produce the same block count
    # (the shortcut is byte-equivalent, modulo filename, to passing 0 explicitly).
    out_zero = tmp_path / "weapon_count_zero"
    out_zero.mkdir()
    rc = main(
        [
            "--weapon-count",
            "0",
            "--seed",
            "42",
            "--output-json",
            "--out",
            str(out_zero),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0
    captured = capsys.readouterr()
    zero_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(zero_lines) == 1
    zero_blocks = _json.loads(zero_lines[0])["blocks"]
    assert no_blocks == zero_blocks, (
        f"--no-weapons ({no_blocks}) must produce same block count as "
        f"--weapon-count 0 ({zero_blocks})"
    )

    # Sanity check: a ``--weapon-count 5`` run must add cells, otherwise
    # the equivalence check above would be vacuously satisfied (e.g. if
    # ``--no-weapons`` silently failed and weapon scatter never fired).
    out_armed = tmp_path / "armed"
    out_armed.mkdir()
    rc = main(
        [
            "--weapon-count",
            "5",
            "--seed",
            "42",
            "--output-json",
            "--out",
            str(out_armed),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0
    captured = capsys.readouterr()
    armed_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(armed_lines) == 1
    armed_blocks = _json.loads(armed_lines[0])["blocks"]
    assert armed_blocks > no_blocks, (
        f"weapon scatter should add cells; armed={armed_blocks} "
        f"no_weapons={no_blocks}"
    )


def test_cli_no_weapons_conflicts_with_weapon_count(tmp_path: Path, capsys):
    """Passing both ``--no-weapons`` and ``--weapon-count`` exits non-zero
    via ``parser.error`` with the mutual-exclusion message."""
    import pytest

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--no-weapons",
                "--weapon-count",
                "3",
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
    assert "--no-weapons" in captured.err
    assert "--weapon-count" in captured.err
    assert "mutually exclusive" in captured.err


def test_cli_no_weapons_help_mentions_both_flags():
    """``--help`` text must document both ``--no-weapons`` and
    ``--weapon-count`` so users can discover the shortcut."""
    from spaceship_generator.cli import build_parser

    help_text = build_parser().format_help()
    assert "--no-weapons" in help_text
    assert "--weapon-count" in help_text


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


# ---------------------------------------------------------------------------
# --list-greeble-types
# ---------------------------------------------------------------------------


def test_cli_list_greeble_types(capsys):
    """``--list-greeble-types`` prints every ``GreebleType`` value on its
    own line in enum-declaration order, exit 0.

    Membership is asserted via enum iteration (no hard-coded string list)
    so the test does not drift when a new greeble type is added. Narrower
    sibling of ``--list-shape-styles`` — no group header/indent prefix
    since there's only one enum to emit.
    """
    from spaceship_generator.greeble_styles import GreebleType

    rc = main(["--list-greeble-types"])
    assert rc == 0

    out = capsys.readouterr().out
    lines = out.splitlines()

    # Every enum member appears on its own line, no prefix/indent.
    for g in GreebleType:
        assert g.value in lines, f"missing GreebleType.{g.name}"

    # Deterministic enum-declaration order — the printed lines (modulo any
    # blank trailers) match the enum's own iteration order exactly.
    expected = [g.value for g in GreebleType]
    assert [line for line in lines if line] == expected

    # Narrower than --list-styles: hull/engine/wing/cockpit/weapon section
    # headers must NOT appear.
    assert "Hull styles:" not in lines
    assert "Engine styles:" not in lines
    assert "Wing styles:" not in lines
    assert "Cockpit styles:" not in lines
    assert "Weapon types:" not in lines


# ---------------------------------------------------------------------------
# --quiet / -q
# ---------------------------------------------------------------------------


def test_cli_quiet_dry_run_silences_stdout(capsys):
    """``--quiet --seed 1 --dry-run`` produces empty stdout (no JSON, no banner).

    --dry-run normally prints a one-line JSON summary; --quiet must suppress
    that on the success path. Exit code stays 0.
    """
    rc = main(["--quiet", "--seed", "1", "--dry-run"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "", (
        f"--quiet --dry-run leaked stdout: {captured.out!r}"
    )


def test_cli_dry_run_without_quiet_emits_stdout(capsys):
    """Regression guard: plain ``--seed 1 --dry-run`` (no --quiet) still emits
    JSON on stdout. This pins the baseline that --quiet must silence."""
    rc = main(["--seed", "1", "--dry-run"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() != "", (
        "--dry-run without --quiet should still print JSON to stdout"
    )
    # Sanity: it's a single JSON object containing the seed we passed.
    obj = json.loads(captured.out.strip())
    assert obj["seed"] == 1
    assert obj["dry_run"] is True


def test_cli_quiet_q_short_flag_argparse_error_keeps_stdout_empty(
    tmp_path: Path, capsys
):
    """Using the ``-q`` short alias with an argparse-rejected flag value
    routes the error to stderr while stdout stays empty.

    Argparse exits with code 2 when a typed value fails validation
    (here: ``--hull-noise -0.1`` violates the ``[0.0, 1.0]`` interval).
    --quiet/-q must not muffle the stderr error message.
    """
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "-q",
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
    captured = capsys.readouterr()
    assert captured.out == "", (
        f"-q must keep stdout empty on argparse error: {captured.out!r}"
    )
    assert captured.err.strip() != "", (
        "argparse error should still surface on stderr under -q"
    )


# ---------------------------------------------------------------------------
# --version / -V
# ---------------------------------------------------------------------------


def test_cli_version_long_flag(capsys):
    """``--version`` prints exactly ``spaceship_generator <ver>\\n`` to stdout
    and exits 0. Argparse's ``version`` action raises ``SystemExit`` after
    printing, so the test catches it explicitly to assert the exit code.
    """
    import pytest

    from spaceship_generator import __version__ as pkg_version

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert captured.out == f"spaceship_generator {pkg_version}\n", (
        f"unexpected --version stdout: {captured.out!r}"
    )
    assert captured.err == "", (
        f"--version must not write to stderr: {captured.err!r}"
    )


def test_cli_version_short_flag(capsys):
    """``-V`` short alias prints the same line and exits 0 as ``--version``."""
    import pytest

    from spaceship_generator import __version__ as pkg_version

    with pytest.raises(SystemExit) as exc_info:
        main(["-V"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert captured.out == f"spaceship_generator {pkg_version}\n", (
        f"unexpected -V stdout: {captured.out!r}"
    )
    assert captured.err == "", (
        f"-V must not write to stderr: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# --output - (stdout streaming)
# ---------------------------------------------------------------------------


def test_cli_output_dash_streams_litematic_bytes(tmp_path: Path, capfdbinary):
    """``--output -`` writes the raw .litematic payload to ``sys.stdout.buffer``.

    The litematic format is gzipped NBT — payload starts with the gzip magic
    bytes ``\\x1f\\x8b`` — so we assert non-empty + magic-prefix on the
    captured binary stdout. ``--out`` is unused (generation lands in a temp
    dir under the hood) but supplying it keeps the test parallel to the other
    CLI tests.
    """
    # Use a small ship to keep the test fast.
    rc = main(
        ["--seed", "1", "--output", "-", "--out", str(tmp_path)] + _SMALL_ARGS
    )
    assert rc == 0

    captured = capfdbinary.readouterr()
    payload = captured.out
    # Non-empty binary payload landed on stdout.
    assert len(payload) > 0, "expected --output - to emit non-empty bytes"
    # Litematic = NBT inside gzip → starts with the gzip magic.
    assert payload[:2] == b"\x1f\x8b", (
        f"expected gzip magic at start of .litematic stream, "
        f"got {payload[:2]!r}"
    )


def test_cli_output_dash_conflicts_with_repeat(tmp_path: Path, capsys):
    """``--output - --repeat 2`` is rejected with a clear stderr message."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--output",
                "-",
                "--repeat",
                "2",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    # parser.error() exits with code 2.
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "--output -" in err
    assert "--repeat" in err


def test_cli_output_dash_conflicts_with_fleet_count(tmp_path: Path, capsys):
    """``--output - --fleet-count 2`` is rejected with a clear stderr message."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--output",
                "-",
                "--fleet-count",
                "2",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "--output -" in err
    assert "--fleet-count" in err


# ---------------------------------------------------------------------------
# --stats-json
# ---------------------------------------------------------------------------

_STATS_JSON_REQUIRED_KEYS = {
    "seed",
    "palette",
    "shape",
    "total_blocks",
    "density",
    "total_cells",
    "roles",
}


def test_cli_stats_json_emits_parseable_json(tmp_path: Path, capsys):
    """``--stats-json`` prints exactly one JSON document with the expected
    keys (block counts, dims, role tallies) and exits 0."""
    rc = main(
        ["--stats-json", "--seed", "1001", "--out", str(tmp_path)] + _SMALL_ARGS
    )
    assert rc == 0

    captured = capsys.readouterr()
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(json_lines) == 1, (
        f"Expected exactly 1 JSON line for --stats-json, got "
        f"{len(json_lines)}:\n{captured.out}"
    )

    obj = json.loads(json_lines[0])
    missing = _STATS_JSON_REQUIRED_KEYS - obj.keys()
    assert not missing, f"Missing keys {missing} in --stats-json output: {obj}"

    # Spot-check every field's shape so a regression in _compute_stats
    # surfaces here rather than via parsers downstream.
    assert obj["seed"] == 1001
    assert isinstance(obj["palette"], str) and obj["palette"]
    assert isinstance(obj["shape"], list) and len(obj["shape"]) == 3
    assert all(isinstance(d, int) and d > 0 for d in obj["shape"])
    assert isinstance(obj["total_blocks"], int) and obj["total_blocks"] > 0
    assert isinstance(obj["total_cells"], int) and obj["total_cells"] > 0
    assert obj["total_blocks"] <= obj["total_cells"]
    assert isinstance(obj["density"], float) and 0.0 < obj["density"] < 1.0
    assert isinstance(obj["roles"], list) and obj["roles"]
    # Every role entry has the role name + count + pct, and counts are
    # sorted descending (mirrors --stats human-format ordering).
    role_names = {r["role"] for r in obj["roles"]}
    assert "EMPTY" not in role_names, "EMPTY must be skipped from roles list"
    counts = [r["count"] for r in obj["roles"]]
    assert counts == sorted(counts, reverse=True), (
        f"roles must be sorted by count desc, got {counts}"
    )
    assert sum(counts) == obj["total_blocks"]


def test_cli_stats_json_not_silenced_by_quiet(tmp_path: Path, capsys):
    """``--quiet --stats-json`` must still emit the JSON document on stdout
    (carve-out parallels ``--quiet --output-json``)."""
    rc = main(
        [
            "--quiet",
            "--stats-json",
            "--seed",
            "1002",
            "--out",
            str(tmp_path),
        ]
        + _SMALL_ARGS
    )
    assert rc == 0

    captured = capsys.readouterr()
    # Under --quiet, the only thing on stdout should be the JSON document —
    # no Seed:/Palette:/Wrote: success lines, no "Role distribution:" header.
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    assert len(json_lines) == 1, (
        f"Expected exactly 1 JSON line under --quiet --stats-json, got "
        f"{len(json_lines)}:\n{captured.out}"
    )
    assert "Role distribution:" not in captured.out
    assert "Seed:" not in captured.out

    obj = json.loads(json_lines[0])
    assert obj["seed"] == 1002
    assert _STATS_JSON_REQUIRED_KEYS <= obj.keys()


# ---------------------------------------------------------------------------
# --help snapshot: every declared flag must be referenced in --help text
# ---------------------------------------------------------------------------


def test_cli_help_text_mentions_every_declared_flag():
    """Snapshot-style guard: ``build_parser().format_help()`` must reference
    every long/short flag declared on the parser.

    Walks ``parser._actions`` (the canonical list of registered argparse
    actions) so the test auto-discovers new flags — adding a new
    ``add_argument`` to ``cli.py`` automatically widens this assertion
    instead of needing a hand-edited list. Catches the silent-removal /
    silent-rename failure mode where someone deletes an ``add_argument``
    or renames its ``--flag`` string and the help text drifts out of sync.

    Each flag's ``option_strings`` (e.g. ``["--quiet", "-q"]``) must each
    appear verbatim in the help string. On miss the assertion lists the
    offending flag(s) so the failure is unambiguous.
    """
    from spaceship_generator.cli import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    # Sanity: help is non-empty and mentions the package / program name.
    assert help_text.strip(), "build_parser().format_help() returned empty string"
    assert "spaceship" in help_text.lower(), (
        "help text should mention the package/program name 'spaceship'; "
        f"got prog={parser.prog!r}"
    )

    # Walk every registered action; an action with non-empty option_strings
    # is a flag (positionals have option_strings == []). Collect every
    # declared flag name (long form, short alias, etc.) so renames surface.
    declared_flags: list[str] = []
    for action in parser._actions:
        for flag in action.option_strings:
            declared_flags.append(flag)

    # Defensive sanity check: the parser must declare at least a few flags
    # (--help is always there, and this CLI declares dozens). If this trips
    # the test itself is broken, not the help text.
    assert len(declared_flags) >= 5, (
        f"expected build_parser() to declare many flags, got only "
        f"{declared_flags!r} — test logic is wrong"
    )

    missing = [flag for flag in declared_flags if flag not in help_text]
    assert not missing, (
        f"--help text is missing references to declared flag(s): {missing}. "
        f"Either the flag was silently renamed/removed, or its help= string "
        f"was suppressed. Re-check build_parser() in cli.py."
    )


def test_cli_stats_json_conflicts_with_stats(tmp_path: Path, capsys):
    """Passing both ``--stats`` and ``--stats-json`` exits non-zero via
    ``parser.error`` with a clear stderr message (mirrors the
    ``--no-greebles`` vs ``--greeble-density`` pattern)."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--stats",
                "--stats-json",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
            ]
            + _SMALL_ARGS
        )
    # argparse's parser.error() exits with status 2.
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "--stats" in err
    assert "--stats-json" in err
    assert "mutually exclusive" in err
