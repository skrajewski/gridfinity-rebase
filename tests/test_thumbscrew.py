import json

import manifold3d as m
import numpy as np
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase.catalog import PRESETS
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import detect_grid, detect_standard_base, replace_base
from gridfinity_rebase.presets import preset_base, thumbscrew_hole
from gridfinity_rebase.stl import read_stl, write_stl


@pytest.mark.parametrize("segments", [32, 64, 256])
def test_thread_dimensions_pitch_and_handedness(segments):
    cutter = thumbscrew_hole(segments)
    assert cutter.status() == m.Error.NoError
    assert cutter.bounding_box()[2::3] == (0, 4.75)
    # Independent expected dimensions from Rebuilt's ScrewThread call:
    # 15.65 mm nominal cutter + 0.1 mm shrink correction; 60 degree tooth.
    root = (15.65 - 1.5 * np.sqrt(3)) / 2
    for z in (0.25, 1.0, 2.125, 3.625):
        points = np.asarray(cutter.slice(z).to_polygons()[0])
        angle = np.arctan2(points[:, 1], points[:, 0]) % (2 * np.pi)
        phase = (z / 1.5 - angle / (2 * np.pi)) % 1
        expected = root + (7.875 - root) * (1 - np.abs(2 * phase - 1))
        # Upstream has a small seam transition in the last two angular steps.
        keep = angle < 2 * np.pi - 3 * 2 * np.pi / segments
        assert (
            np.max(np.abs(np.linalg.norm(points[keep], axis=1) - expected[keep])) < 0.04
        )
    first, turn = cutter.slice(1), cutter.slice(2.5)
    assert (first - turn).area() + (turn - first).area() < 1e-6
    half = cutter.slice(1.75)
    assert (first.rotate(180) - half).area() + (half - first.rotate(180)).area() < 0.05
    # Rotation is real thread geometry, rather than a smooth circular bore.
    assert (first - half).area() > 10


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("size", [(1, 3), (2, 3)])
@pytest.mark.parametrize("segments", [32, 256])
def test_threaded_presets_preserve_bridge_and_export(preset, size, segments, tmp_path):
    source = make_bin(*size, origin=(105, -23, -11))
    grid = detect_grid(source)
    base = preset_base(preset, grid, 7, segments, thumbscrew=True)
    plain = preset_base(preset, grid, 7, segments)
    assert detect_grid(base) == grid
    for x, y in grid.cells:
        # Includes the bottom face: no membrane obstructs entry of the screw.
        opening = m.Manifold.cylinder(4.75, 6, circular_segments=32).translate(
            (x, y, grid.z)
        )
        assert (base ^ opening).volume() < 1e-8
        roof = m.Manifold.cube((2, 2, 0.2)).translate((x - 1, y - 1, grid.z + 4.75))
        assert (base ^ roof).volume() == pytest.approx(0.8)
    above = grid.z + 4.7501
    assert (base.trim_by_plane((0, 0, 1), above) - plain).volume() < 1e-8
    assert base.slice(grid.z + 6).area() == pytest.approx(
        plain.slice(grid.z + 6).area()
    )
    result = replace_base(source, base, grid, 7)
    assert detect_standard_base(result, grid).height == 7
    upper = result.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    expected = source.trim_by_plane((0, 0, 1), grid.z + 7.0001)
    assert (upper - expected).volume() + (expected - upper).volume() < 1e-7
    output = tmp_path / "result.stl"
    write_stl(result, output)
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1
    exported = detect_grid(read_stl(output))
    assert (exported.nx, exported.ny) == size
    assert (exported.x, exported.y, exported.z) == pytest.approx(
        (grid.x, grid.y, grid.z), abs=1e-5
    )


@pytest.mark.parametrize("height", [None, 4.75, 6.9, 7, 9])
def test_cli_thumbscrew_and_subsequent_removal(height, tmp_path, capsys):
    source = tmp_path / "bin.stl"
    # A tall enough solid floor also exercises a manual cut above 7 mm.
    solid = make_bin(1, 3)
    if height == 9:
        solid += m.Manifold.cube((30, 114, 2)).translate((-15, -15, 8))
    write_stl(solid, source)
    original = source.read_bytes()
    args = ["rebase", str(source), "--preset", "refined", "--thumbscrew", "--json"]
    if height is not None:
        args += ["--base-height", str(height)]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    output = tmp_path / "bin-rebased-refined-thumbscrew.stl"
    assert report["output"] == str(output)
    assert report["thumbscrew"] is True
    assert report["base_height_mm"] == (7 if height is None else height)
    assert source.read_bytes() == original
    # A threaded input remains recognizable and can be rebased back to plain.
    assert main(["rebase", str(output), "--preset", "plain", "--json"]) == 0
    removed = json.loads(capsys.readouterr().out)
    assert removed["thumbscrew"] is False
    result = read_stl(removed["output"])
    centre = m.Manifold.cylinder(4.75, 6, circular_segments=32)
    assert (result ^ centre).volume() == pytest.approx(centre.volume(), abs=0.001)


def test_cli_rejects_thumbscrew_with_donor_before_writing(tmp_path, capsys):
    source = tmp_path / "missing.stl"
    output = tmp_path / "existing.stl"
    output.write_bytes(b"keep me")
    assert (
        main(
            [
                "rebase",
                str(source),
                "--base",
                str(source),
                "--thumbscrew",
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


def test_threaded_alias_has_identical_geometry():
    grid = detect_grid(make_bin())
    refined = preset_base("refined", grid, 7, thumbscrew=True)
    rebuilt = preset_base("rebuilt", grid, 7, thumbscrew=True)
    assert (refined - rebuilt).volume() + (rebuilt - refined).volume() < 1e-8
