import json

import manifold3d as m
import numpy as np
import pytest
import trimesh

from gridfinity_rebase import RebaseError
from gridfinity_rebase.catalog import resolve_options
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import Grid, detect_grid, donor_base, replace_base
from gridfinity_rebase.presets import PRESETS, generate_base, preset_base, rounded_prism
from gridfinity_rebase.stl import write_stl


def make_bin(nx=1, ny=1, preset="plain", origin=(0, 0, 0), *, screws=None):
    grid = Grid(nx, ny, 0, 0, 0)
    base = generate_base(resolve_options(preset, screws=screws), grid, 7)
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


def test_magnet_holes_dimensions():
    grid = Grid(1, 1, 0, 0, 0)
    plain = preset_base("plain", grid)
    base = preset_base("magnet-holes", grid)
    for x, y in ((13, 13), (-13, 13), (-13, -13), (13, -13)):
        probe = m.Manifold.cube((8, 8, 3)).translate((x - 4, y - 4, 0))
        assert (probe - base).bounding_box() == pytest.approx(
            (x - 3.25, y - 3.25, 0, x + 3.25, y + 3.25, 2.4)
        )
    assert plain.slice(1).area() - base.slice(1).area() == pytest.approx(
        4 * np.pi * 3.25**2, rel=0.002
    )
    assert base.slice(2.41).area() == pytest.approx(plain.slice(2.41).area())


@pytest.mark.parametrize("preset", ["rebuilt", "refined"])
@pytest.mark.parametrize("screws", [False, True])
def test_side_loading_opening_and_screw_dimensions(preset, screws):
    grid = Grid(1, 1, 0, 0, 0)
    solid = preset_base("plain", grid)
    base = generate_base(resolve_options(preset, screws=screws), grid)
    screw = generate_base(resolve_options("rebuilt", screws=True), grid)
    assert solid.slice(3).area() - screw.slice(3).area() == pytest.approx(
        4 * np.pi * 1.5**2, rel=0.002
    )
    if not screws:
        assert base.slice(2.51).area() == pytest.approx(solid.slice(2.51).area())
        # A floor retains the magnet below the side-loading pocket.
        floor = m.Manifold.cube((1, 1, 0.2)).translate((12.5, 12.5, 0.1))
        assert (base ^ floor).volume() == pytest.approx(0.2)
    # Side pocket intersects the +X outer side, while the bottom has a floor.
    probe = m.Manifold.cube((1, 2, 1)).translate((17.5, 12, 0.5))
    assert (base ^ probe).volume() < 1e-8
    assert (solid ^ probe).volume() > 1.9
    # 5.86 mm pocket width and 2.1 mm height, above a 0.4 mm floor.
    cavity = m.Manifold.cube((0.5, 5.86, 2.1)).translate((13.25, 10.07, 0.4))
    assert (base ^ cavity).volume() < 1e-8
    wall = m.Manifold.cube((0.5, 0.2, 1)).translate((12.75, 15.95, 0.5))
    assert (base ^ wall).volume() == pytest.approx(0.1)


@pytest.mark.parametrize("preset", ["rebuilt", "refined"])
@pytest.mark.parametrize("screws", [False, True])
@pytest.mark.parametrize("size", [(1, 1), (1, 3), (3, 1), (2, 3), (3, 2), (3, 3)])
@pytest.mark.parametrize("segments", [32, 64, 256])
def test_side_loading_fan_on_every_foot(
    preset, screws, size: tuple[int, int], segments
):
    grid = Grid(*size, 105, -23, -11)
    base = generate_base(resolve_options(preset, screws=screws), grid, 7, segments)
    # Independent expected directions from Rebuilt's _base_holes().
    corners = [
        ((13, 13), (1, 0)),
        ((-13, 13), (0, 1)),
        ((-13, -13), (-1, 0)),
        ((13, -13), (0, -1)),
    ]
    for cx, cy in grid.cells:
        for (x, y), (dx, dy) in corners:
            centre = np.array((cx + x, cy + y, grid.z))
            opening = centre + (5 * dx, 5 * dy, 0.9)
            probe = m.Manifold.cube((0.5, 0.5, 1)).translate(opening - (0.25, 0.25, 0))
            assert (base ^ probe).volume() < 1e-8
            # The other equally near edge stays closed: this catches mirrored
            # left/right pairs and accidentally cutting both outward directions.
            other_edge = centre + (
                0 if dx else np.sign(x) * 5,
                0 if dy else np.sign(y) * 5,
                0.9,
            )
            wall = m.Manifold.cube((0.5, 0.5, 1)).translate(
                other_edge - (0.25, 0.25, 0)
            )
            assert (base ^ wall).volume() == pytest.approx(0.25)
            # The bottom removal slit must follow the pocket's rotation too.
            removal = centre + (-6 * dx, -6 * dy, 0.1)
            slit = m.Manifold.cube((0.5, 0.5, 0.2)).translate(removal - (0.25, 0.25, 0))
            assert (base ^ slit).volume() < 1e-8


@pytest.mark.parametrize("alias,canonical", [("refined", "rebuilt")])
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
    result = replace_base(
        source, generate_base(resolve_options("rebuilt", screws=True), grid, 7), grid, 7
    )
    assert len(result.decompose()) == 1
    standard = preset_base("plain", grid, 7)
    assert standard.slice(6).area() - result.slice(6).area() == pytest.approx(
        24 * np.pi * 1.5**2, rel=0.002
    )


def test_enclosed_old_holes_are_not_detached_feet():
    source = make_bin(preset="rebuilt", screws=True)
    grid = detect_grid(source)
    result = replace_base(source, preset_base("plain", grid), grid)
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
    assert main(["rebase", str(source), "--preset", "plain", "-o", str(output)]) == 2
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "plain",
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
