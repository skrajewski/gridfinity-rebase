import json

import manifold3d as m
import numpy as np
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase import RebaseError
from gridfinity_rebase.catalog import resolve_options
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import (
    Grid,
    detect_grid,
    detect_standard_base,
    replace_base,
)
from gridfinity_rebase.options import BaseOptions
from gridfinity_rebase.presets import generate_base
from gridfinity_rebase.stl import read_stl, write_stl


@pytest.mark.parametrize("preset", ["rebuilt", "refined"])
def test_explicit_overrides_keep_unmentioned_settings(preset):
    options = resolve_options(preset, screws=False, thumbscrew=True)
    assert options == BaseOptions(magnets="side", thumbscrew=True)
    assert resolve_options("press-fit", screws=True) == BaseOptions(
        magnets="bottom", crush_ribs=True, screws=True
    )
    assert resolve_options("press-fit", crush_ribs=False) == BaseOptions(
        magnets="bottom"
    )


@pytest.mark.parametrize("magnets", ["none", "side"])
def test_changing_magnet_style_clears_inherited_ribs(magnets):
    assert resolve_options("press-fit", magnets=magnets) == BaseOptions(magnets=magnets)
    with pytest.raises(RebaseError, match="requires --magnets bottom"):
        resolve_options("press-fit", magnets=magnets, crush_ribs=True)


@pytest.mark.parametrize(
    "magnets,ribs",
    [("none", False), ("side", False), ("bottom", False), ("bottom", True)],
)
@pytest.mark.parametrize("screws", [False, True])
@pytest.mark.parametrize("thumbscrew", [False, True])
@pytest.mark.parametrize("size", [(1, 1), (2, 3)])
def test_independent_geometry_is_printable_and_preserves_upper_bin(
    magnets, ribs, screws, thumbscrew, size, tmp_path
):
    source = make_bin(*size, origin=(105, -23, -11))
    grid = detect_grid(source)
    options = BaseOptions(magnets, screws, ribs, thumbscrew)
    base = generate_base(options, grid, 7)
    solid = generate_base(BaseOptions(thumbscrew=thumbscrew), grid, 7)
    assert detect_grid(base) == grid
    assert solid.slice(grid.z + 3).area() - base.slice(
        grid.z + 3
    ).area() == pytest.approx(
        4 * size[0] * size[1] * np.pi * 1.5**2 if screws else 0, rel=0.002, abs=1e-6
    )
    assert solid.slice(grid.z + 6).area() - base.slice(
        grid.z + 6
    ).area() == pytest.approx(
        4 * size[0] * size[1] * np.pi * 1.5**2 if screws else 0, rel=0.002, abs=1e-6
    )
    for x, y in grid.cells:
        side = m.Manifold.cube((1, 2, 1)).translate((x + 17.5, y + 12, grid.z + 1))
        assert (base ^ side).volume() == pytest.approx(0 if magnets == "side" else 2)
        centre = m.Manifold.cube((1, 1, 1)).translate(
            (x + 12.5, y + 12.5, grid.z + 0.5)
        )
        assert (base ^ centre).volume() == pytest.approx(
            1 if magnets == "none" and not screws else 0
        )
    if magnets == "bottom":
        removed = solid.slice(grid.z + 1.5).area() - base.slice(grid.z + 1.5).area()
        full_circles = 4 * size[0] * size[1] * np.pi * 3.25**2
        if ribs:
            assert removed < full_circles * 0.95
        else:
            assert removed == pytest.approx(full_circles, rel=0.002)
    result = replace_base(source, base, grid, 7)
    assert detect_standard_base(result, grid).height == 7
    upper = result.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    expected = source.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    assert (upper - expected).volume() + (expected - upper).volume() < 1e-7
    path = tmp_path / "result.stl"
    write_stl(result, path)
    mesh = trimesh.load_mesh(path)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1


@pytest.mark.parametrize("height", [4.75, 6, 7, 9])
def test_screw_only_depth_is_limited_to_cut_or_seven_mm(height):
    grid = Grid(1, 1, 0, 0, 0)
    base = generate_base(BaseOptions(screws=True), grid, height)
    probe = m.Manifold.cylinder(min(height, 7), 1, circular_segments=32).translate(
        (13, 13, 0)
    )
    assert (base ^ probe).volume() < 1e-8
    if height > 7:
        roof = m.Manifold.cube((1, 1, 1)).translate((12.5, 12.5, 7.1))
        assert (base ^ roof).volume() == pytest.approx(1)


@pytest.mark.parametrize(
    "flags,expected,suffix",
    [
        ([], BaseOptions(), "plain"),
        (
            ["--preset", "magnet-holes"],
            BaseOptions(magnets="bottom"),
            "magnet-holes",
        ),
        (
            ["--preset", "magnet-holes", "--crush-ribs"],
            BaseOptions(magnets="bottom", crush_ribs=True),
            "magnets-bottom-crush-ribs",
        ),
        (["--screws"], BaseOptions(screws=True), "screws"),
        (
            ["--magnets", "side", "--screws"],
            BaseOptions(magnets="side", screws=True),
            "magnets-side-screws",
        ),
        (
            ["--magnets", "bottom", "--crush-ribs", "--screws"],
            BaseOptions(magnets="bottom", crush_ribs=True, screws=True),
            "magnets-bottom-crush-ribs-screws",
        ),
        (
            ["--magnets", "bottom", "--no-crush-ribs"],
            BaseOptions(magnets="bottom"),
            "magnets-bottom",
        ),
        (
            ["--preset", "rebuilt", "--no-screws"],
            BaseOptions(magnets="side"),
            "rebuilt",
        ),
        (
            ["--preset", "press-fit", "--screws"],
            BaseOptions(magnets="bottom", crush_ribs=True, screws=True),
            "magnets-bottom-crush-ribs-screws",
        ),
        (["--preset", "press-fit", "--magnets", "none"], BaseOptions(), "plain"),
        (["--thumbscrew"], BaseOptions(thumbscrew=True), "plain-thumbscrew"),
        (
            ["--preset", "refined", "--no-thumbscrew"],
            BaseOptions(magnets="side"),
            "refined",
        ),
    ],
)
def test_cli_resolves_options_reports_geometry_and_names_output(
    flags, expected, suffix, tmp_path, capsys
):
    source = tmp_path / "bin.stl"
    write_stl(make_bin(), source)
    original = source.read_bytes()
    assert main(["rebase", str(source), *flags, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["geometry"] == expected.describe()
    assert report["thumbscrew"] == expected.thumbscrew
    assert report["output"] == str(tmp_path / f"bin-rebased-{suffix}.stl")
    result = read_stl(report["output"])
    # Slice below the body verifies the flags affected the exported mesh.
    actual = result.slice(1.5)
    wanted = generate_base(expected, Grid(1, 1, 0, 0, 0), 7).slice(1.5)
    assert (actual - wanted).area() + (wanted - actual).area() < 0.001
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "flags",
    [
        ["--magnets", "none"],
        ["--magnets", "side"],
        ["--screws"],
        ["--no-screws"],
        ["--crush-ribs"],
        ["--no-crush-ribs"],
        ["--thumbscrew"],
        ["--no-thumbscrew"],
        ["--only-corners"],
    ],
)
def test_donor_rejects_all_explicit_geometry_flags_before_io(flags, tmp_path, capsys):
    missing = tmp_path / "missing.stl"
    output = tmp_path / "existing.stl"
    output.write_bytes(b"keep me")
    assert (
        main(
            [
                "rebase",
                str(missing),
                "--base",
                str(missing),
                *flags,
                "-o",
                str(output),
                "--overwrite",
                "--json",
            ]
        )
        == 2
    )
    assert "cannot be used with --base" in json.loads(capsys.readouterr().err)["error"]
    assert output.read_bytes() == b"keep me"


@pytest.mark.parametrize(
    "flags", [["--crush-ribs"], ["--magnets", "side", "--crush-ribs"]]
)
def test_cli_rejects_ribs_without_bottom_pockets_before_io(flags, tmp_path, capsys):
    assert main(["rebase", str(tmp_path / "missing.stl"), *flags, "--json"]) == 2
    assert "requires --magnets bottom" in json.loads(capsys.readouterr().err)["error"]


def test_donor_report_does_not_claim_generated_geometry(tmp_path, capsys):
    source = tmp_path / "bin.stl"
    donor = tmp_path / "donor.stl"
    write_stl(make_bin(), source)
    write_stl(make_bin(preset="rebuilt", screws=True), donor)
    assert main(["rebase", str(source), "--base", str(donor), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["base"] == str(donor)
    assert report["geometry"] is None and report["thumbscrew"] is None
    assert report["output"] == str(tmp_path / "bin-rebased.stl")
