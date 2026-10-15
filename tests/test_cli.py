import json
import sys
from pathlib import Path

import pytest

from gridfinity_rebase import __version__
from gridfinity_rebase.cli import main
from gridfinity_rebase.stl import read_stl

EXAMPLE = Path(__file__).parent / "fixtures" / "gf_bin_1x1_h6_bin_v01.stl"


def test_no_arguments_show_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["gridfinity-rebase"])
    assert main() == 0
    help_output = capsys.readouterr()
    assert help_output.err == ""
    assert "gridfinity-rebase INPUT.stl [OPTIONS]" in help_output.out
    assert "default action" in help_output.out
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == help_output.out


@pytest.mark.parametrize("options_first", [False, True])
def test_default_rebase_matches_explicit_command(options_first, tmp_path, capsys):
    default_output = tmp_path / "default.stl"
    explicit_output = tmp_path / "explicit.stl"
    options = ["--preset", "rebuilt", "--screws", "--json"]
    args = [*options, str(EXAMPLE)] if options_first else [str(EXAMPLE), *options]
    assert main([*args, "-o", str(default_output)]) == 0
    default_report = json.loads(capsys.readouterr().out)
    assert main(["rebase", str(EXAMPLE), *options, "-o", str(explicit_output)]) == 0
    explicit_report = json.loads(capsys.readouterr().out)
    for report in (default_report, explicit_report):
        report.pop("output")
        report.pop("elapsed_ms")
    assert default_report == explicit_report
    default_model = read_stl(default_output)
    explicit_model = read_stl(explicit_output)
    assert (default_model - explicit_model).volume() + (
        explicit_model - default_model
    ).volume() < 0.002


def test_explicit_auxiliary_commands(capsys):
    assert main(["presets", "--json"]) == 0
    assert list(json.loads(capsys.readouterr().out)) == [
        "plain",
        "magnet-holes",
        "rebuilt",
        "press-fit",
        "refined",
    ]
    assert main(["inspect", str(EXAMPLE), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["grid"] == [1, 1]
    assert "output" not in report


def test_global_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_default_rebase_help(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([str(EXAMPLE), "--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert "--preset" in output.out
    assert "gridfinity-rebase INPUT.stl [OPTIONS]" in output.out


def test_default_rebase_rejects_unknown_options(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([str(EXAMPLE), "--unknown"])
    assert exit_info.value.code == 2
    assert "unrecognized arguments: --unknown" in capsys.readouterr().err
