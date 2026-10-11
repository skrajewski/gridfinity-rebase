import json

import manifold3d as m
import numpy as np
import pytest
import trimesh

from gridfinity_rebase import RebaseError
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import Grid, detect_grid, donor_base, replace_base
from gridfinity_rebase.presets import PRESETS, preset_base, rounded_prism
from gridfinity_rebase.stl import write_stl


def make_bin(nx=1, ny=1, preset="standard", origin=(0, 0, 0)):
    grid = Grid(nx, ny, 0, 0, 0)
    base = preset_base(preset, grid, 7)
    body = rounded_prism(nx * 42 - 0.5, ny * 42 - 0.5, 3.75, 7, 21)
    body = body.translate(((nx - 1) * 21, (ny - 1) * 21, 0))
    cavity = m.Manifold.cube((nx * 42 - 4.5, ny * 42 - 4.5, 20)).translate(
        (-18.75, -18.75, 8)
    )
    return ((base + body) - cavity).translate(origin)


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("size", [(1, 1), (2, 3)])
def test_every_preset_on_multiple_grids(preset, size, tmp_path):
    source = make_bin(*size, origin=(105, -23, -11))
    grid = detect_grid(source)
    assert (grid.nx, grid.ny) == size
    assert (grid.x, grid.y, grid.z) == (105, -23, -11)
    replacement = preset_base(preset, grid)
    result = replace_base(source, replacement, grid)
    assert detect_grid(result) == grid
    above = result.trim_by_plane((0, 0, 1), grid.z + 4.7501)
    expected = source.trim_by_plane((0, 0, 1), grid.z + 4.7501)
    assert (above - expected).volume() + (expected - above).volume() < 1e-5
    output = tmp_path / "result.stl"
    write_stl(result, output)
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1


@pytest.mark.parametrize("preset", ["rebuilt", "refined", "rebuilt-screws"])
def test_side_loading_opening_and_screw_dimensions(preset):
    grid = Grid(1, 1, 0, 0, 0)
    solid = preset_base("plain", grid)
    base = preset_base(preset, grid)
    screw = preset_base("rebuilt-screws", grid)
    assert solid.slice(3).area() - screw.slice(3).area() == pytest.approx(
        4 * np.pi * 1.5**2, rel=0.002
    )
    if preset != "rebuilt-screws":
        assert base.slice(2.31).area() == pytest.approx(solid.slice(2.31).area())
        # A floor retains the magnet below the side-loading pocket.
        floor = m.Manifold.cube((1, 1, 0.2)).translate((12.5, 12.5, 0.1))
        assert (base ^ floor).volume() == pytest.approx(0.2)
    # Side pocket intersects the +X outer side, while the bottom has a floor.
    probe = m.Manifold.cube((1, 2, 1)).translate((17.5, 12, 0.5))
    assert (base ^ probe).volume() < 1e-8
    assert (solid ^ probe).volume() > 1.9
    # 5.86 mm pocket width and 1.9 mm height, above a 0.4 mm floor.
    cavity = m.Manifold.cube((0.5, 5.86, 1.9)).translate((13.25, 10.07, 0.4))
    assert (base ^ cavity).volume() < 1e-8
    wall = m.Manifold.cube((0.5, 0.2, 1)).translate((12.75, 15.95, 0.5))
    assert (base ^ wall).volume() == pytest.approx(0.1)


@pytest.mark.parametrize(
    "alias,canonical", [("refined", "rebuilt"), ("standard", "plain")]
)
def test_aliases_export_identical_geometry(alias, canonical, tmp_path, capsys):
    source = tmp_path / "input.stl"
    write_stl(make_bin(), source)
    outputs = []
    for preset in (alias, canonical):
        output = tmp_path / f"{preset}.stl"
        assert (
            main(
                ["rebase", str(source), "--preset", preset, "-o", str(output), "--json"]
            )
            == 0
        )
        assert json.loads(capsys.readouterr().out)["base"] == preset
        outputs.append(output.read_bytes())
    assert outputs[0] == outputs[1]


def test_tiled_donor_and_transposed_grid():
    source = make_bin(3, 2, origin=(-66, 128, -15))
    target = detect_grid(source)
    for donor in (
        make_bin(preset="refined", origin=(100, 200, 3)),
        make_bin(2, 3, "refined", origin=(-300, 200, 4)),
    ):
        replacement = donor_base(donor, detect_grid(donor), target, 4.75)
        result = replace_base(source, replacement, target)
        assert (detect_grid(result).nx, detect_grid(result).ny) == (3, 2)
        assert len(result.decompose()) == 1
    bad_donor = make_bin(2, 2)
    with pytest.raises(RebaseError, match="does not match"):
        donor_base(bad_donor, detect_grid(bad_donor), target, 4.75)


def test_bridge_replacement_and_screw_depth():
    source = make_bin(2, 3)
    grid = detect_grid(source)
    result = replace_base(source, preset_base("rebuilt-screws", grid, 7), grid, 7)
    assert len(result.decompose()) == 1
    standard = preset_base("standard", grid, 7)
    assert standard.slice(6).area() - result.slice(6).area() == pytest.approx(
        24 * np.pi * 1.5**2, rel=0.002
    )


def test_enclosed_old_holes_are_not_detached_feet():
    source = make_bin(preset="rebuilt-screws")
    grid = detect_grid(source)
    result = replace_base(source, preset_base("standard", grid), grid)
    assert sum(c.volume() > 0 for c in result.decompose()) == 1
    # The preserved bridge can contain enclosed void shells above the cut.
    assert len(result.decompose()) > 1


@pytest.mark.parametrize("height", [0, 4, 21, float("nan"), float("inf")])
def test_invalid_height_returns_clean_cli_error(height, tmp_path, capsys):
    source = tmp_path / "input.stl"
    write_stl(make_bin(), source)
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "rebuilt",
                "--base-height",
                str(height),
                "--json",
            ]
        )
        == 2
    )
    assert "Base height" in json.loads(capsys.readouterr().err)["error"]
    assert not list(tmp_path.glob("input-rebased*.stl"))


def test_cli_end_to_end_and_safe_source_files(tmp_path, capsys):
    source, output = tmp_path / "input.stl", tmp_path / "out.stl"
    write_stl(make_bin(), source)
    original = source.read_bytes()
    assert (
        main(
            ["rebase", str(source), "--preset", "refined", "-o", str(output), "--json"]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["grid"] == [1, 1] and report["base"] == "refined"
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "refined",
                "-o",
                str(source),
                "--overwrite",
            ]
        )
        == 2
    )
    assert source.read_bytes() == original
    assert main(["rebase", str(source), "--preset", "standard", "-o", str(output)]) == 2
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "standard",
                "-o",
                str(output),
                "--overwrite",
            ]
        )
        == 0
    )
    assert main(["inspect", str(output)]) == 0
    donor = tmp_path / "not-gridfinity.stl"
    write_stl(m.Manifold.cube((41.5, 41.5, 21)), donor)
    assert (
        main(
            [
                "rebase",
                str(source),
                "--base",
                str(donor),
                "-o",
                str(tmp_path / "bad.stl"),
            ]
        )
        == 2
    )
    assert "not Gridfinity" in capsys.readouterr().err
