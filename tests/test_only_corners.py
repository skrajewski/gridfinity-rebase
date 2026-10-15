import json

import manifold3d as m
import numpy as np
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase.catalog import resolve_options
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import Grid, detect_grid, replace_base
from gridfinity_rebase.options import BaseOptions
from gridfinity_rebase.presets import generate_base, preset_base
from gridfinity_rebase.stl import read_stl, write_stl


def assert_corner_centres(base, grid):
    outer = {
        (x, y)
        for x in (grid.x - 13, grid.x + 42 * (grid.nx - 1) + 13)
        for y in (grid.y - 13, grid.y + 42 * (grid.ny - 1) + 13)
    }
    for x, y in grid.cells:
        for dx in (-13, 13):
            for dy in (-13, 13):
                centre = (x + dx, y + dy)
                probe = m.Manifold.cube((0.5, 0.5, 0.5)).translate(
                    (centre[0] - 0.25, centre[1] - 0.25, grid.z + 1)
                )
                assert (base ^ probe).volume() == pytest.approx(
                    0 if centre in outer else 0.125
                )


@pytest.mark.parametrize("size", [(1, 1), (1, 3), (3, 1), (2, 3), (3, 3)])
@pytest.mark.parametrize(
    "magnets,ribs,screws",
    [
        ("none", False, True),
        ("side", False, False),
        ("side", False, True),
        ("bottom", False, False),
        ("bottom", False, True),
        ("bottom", True, False),
        ("bottom", True, True),
    ],
)
def test_only_four_outer_holes_and_printable_export(
    size, magnets, ribs, screws, tmp_path
):
    source = make_bin(*size, origin=(105, -23, -11))
    grid = detect_grid(source)
    options = BaseOptions(magnets, screws, ribs, only_corners=True)
    base = generate_base(options, grid, 7)
    assert_corner_centres(base, grid)
    assert detect_grid(base) == grid
    plain = generate_base(BaseOptions(), grid, 7)
    for z in (3, 6):
        removed = plain.slice(grid.z + z).area() - base.slice(grid.z + z).area()
        assert removed == pytest.approx(
            4 * np.pi * 1.5**2 if screws else 0, rel=0.002, abs=1e-6
        )
    if magnets == "bottom" and not ribs:
        removed = plain.slice(grid.z + 1.5).area() - base.slice(grid.z + 1.5).area()
        assert removed == pytest.approx(4 * np.pi * 3.25**2, rel=0.002)
    if size == (1, 1):
        usual = generate_base(BaseOptions(magnets, screws, ribs), grid, 7)
        assert (base - usual).volume() + (usual - base).volume() < 1e-8
    result = replace_base(source, base, grid, 7)
    upper = result.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    expected = source.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    assert (upper - expected).volume() + (expected - upper).volume() < 1e-7
    path = tmp_path / "corners.stl"
    write_stl(result, path)
    exported = read_stl(path)
    assert_corner_centres(exported, grid)
    mesh = trimesh.load_mesh(path)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1


def test_side_pocket_openings_and_removal_slots_only_at_outer_corners():
    grid = Grid(3, 3, 105, -23, -11)
    base = preset_base("rebuilt", grid, 7, only_corners=True)
    directions = {
        (13, 13): (1, 0),
        (-13, 13): (0, 1),
        (-13, -13): (-1, 0),
        (13, -13): (0, -1),
    }
    for i in range(3):
        for j in range(3):
            for (dx, dy), (vx, vy) in directions.items():
                selected = (i, dx) in ((0, -13), (2, 13)) and (j, dy) in (
                    (0, -13),
                    (2, 13),
                )
                for distance, z in ((5, 1.3), (-5, 0.1)):
                    probe = m.Manifold.cube((0.5, 0.5, 0.1)).translate(
                        (
                            grid.x + 42 * i + dx + distance * vx - 0.25,
                            grid.y + 42 * j + dy + distance * vy - 0.25,
                            grid.z + z,
                        )
                    )
                    assert (base ^ probe).volume() == pytest.approx(
                        0 if selected else 0.025
                    )


@pytest.mark.parametrize("height", [4.75, 6, 7, 9])
def test_corner_screw_depth_and_central_threads(height):
    grid = Grid(3, 2, 105, -23, -11)
    base = generate_base(
        BaseOptions(screws=True, thumbscrew=True, only_corners=True), grid, height
    )
    plain = generate_base(BaseOptions(), grid, height)
    for x, y in grid.cells:
        probe = m.Manifold.cube((1, 1, 1)).translate((x - 0.5, y - 0.5, grid.z + 1))
        assert (base ^ probe).volume() < 1e-8
    for z in (5, 6, 7.1):
        if z < height:
            removed = plain.slice(grid.z + z).area() - base.slice(grid.z + z).area()
            assert removed == pytest.approx(
                4 * np.pi * 1.5**2 if z < 7 else 0, rel=0.002, abs=1e-6
            )


@pytest.mark.parametrize(
    "flags,suffix",
    [
        (["--preset", "rebuilt", "--screws"], "magnets-side-screws-only-corners"),
        (["--preset", "refined"], "refined-only-corners"),
        (
            ["--preset", "press-fit", "--screws"],
            "magnets-bottom-crush-ribs-screws-only-corners",
        ),
        (["--screws"], "screws-only-corners"),
    ],
)
def test_cli_only_corners_replaces_old_holes_and_reports_settings(
    flags, suffix, tmp_path, capsys
):
    path = tmp_path / "bin.stl"
    write_stl(make_bin(2, 3, preset="rebuilt", screws=True), path)
    original = path.read_bytes()
    assert main(["rebase", str(path), *flags, "--only-corners", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["geometry"]["only_corners"] is True
    assert report["output"] == str(tmp_path / f"bin-rebased-{suffix}.stl")
    exported = read_stl(report["output"])
    assert_corner_centres(exported, detect_grid(exported))
    assert path.read_bytes() == original


def test_only_corners_option_resolution():
    assert resolve_options("rebuilt", screws=True, only_corners=True) == BaseOptions(
        magnets="side", screws=True, only_corners=True
    )
    assert resolve_options("press-fit", only_corners=True).crush_ribs is True
    assert resolve_options("rebuilt").only_corners is False
