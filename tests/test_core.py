from pathlib import Path

import manifold3d as m
import numpy as np
import pytest
import trimesh
from trimesh.exchange.stl import export_stl, export_stl_ascii

from gridfinity_rebase import RebaseError
from gridfinity_rebase.catalog import PRESETS
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import detect_grid, donor_base, replace_base
from gridfinity_rebase.stl import read_stl, write_stl

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_real_donor_preserves_body(tmp_path):
    source = read_stl(FIXTURES / "test.stl")
    donor = read_stl(FIXTURES / "test-rebased.stl")
    grid = detect_grid(source)
    assert (grid.nx, grid.ny) == (1, 1)
    base = donor_base(donor, detect_grid(donor), grid, 4.75)
    result = replace_base(source, base, grid)
    upper = result.trim_by_plane((0, 0, 1), grid.z + 4.7501)
    expected = source.trim_by_plane((0, 0, 1), grid.z + 4.7501)
    assert (upper - expected).volume() + (expected - upper).volume() < 0.001
    assert abs(result.slice(1).area() - donor.slice(1).area()) < 0.001
    output = tmp_path / "out.stl"
    write_stl(result, output)
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1


@pytest.mark.parametrize("size", [(41.5, 41.5, 21), (42, 42, 7), (37.2, 37.2, 10)])
def test_reject_plain_boxes_and_baseplates(size):
    with pytest.raises(RebaseError, match="not Gridfinity"):
        detect_grid(m.Manifold.cube(size))


def test_stl_roundtrip_and_atomic_write(tmp_path):
    path = tmp_path / "cube.stl"
    original = m.Manifold.cube((10, 20, 30))
    write_stl(original, path)
    assert read_stl(path).volume() == pytest.approx(6000)
    data = path.read_bytes()
    with pytest.raises(RebaseError, match="already exists"):
        write_stl(m.Manifold.cube((1, 1, 1)), path)
    assert path.read_bytes() == data
    write_stl(original, path, overwrite=True)
    assert not list(tmp_path.glob(".cube.stl.*"))


def test_ascii_and_broken_stl(tmp_path):
    path = tmp_path / "cube.stl"
    cube = trimesh.creation.box()
    path.write_text(export_stl_ascii(cube))
    assert read_stl(path).volume() == pytest.approx(1)
    path.write_bytes(b"solid broken\nfacet normal 0 0 0\nvertex 1 2 3\nendsolid")
    with pytest.raises(RebaseError, match="incomplete"):
        read_stl(path)
    path.write_bytes(b"invalid")
    with pytest.raises(RebaseError, match="invalid STL"):
        read_stl(path)
    cube.update_faces(list(range(len(cube.faces) - 1)))
    path.write_bytes(export_stl(cube))
    with pytest.raises(RebaseError, match="not a closed"):
        read_stl(path)


def test_cli_rejects_non_gridfinity(tmp_path, capsys):
    path = tmp_path / "cube.stl"
    write_stl(m.Manifold.cube((41.5, 41.5, 21)), path)
    assert main(["inspect", str(path), "--json"]) == 2
    assert "not Gridfinity" in capsys.readouterr().err


@pytest.mark.parametrize("filename", ["test.stl", "test-rebased.stl"])
@pytest.mark.parametrize("preset", list(PRESETS))
def test_all_real_exports_remain_watertight_at_float32(filename, preset, tmp_path):
    from gridfinity_rebase.presets import preset_base

    source = read_stl(FIXTURES / filename)
    grid = detect_grid(source)
    result = replace_base(source, preset_base(preset, grid), grid)
    output = tmp_path / "result.stl"
    count = write_stl(result, output)
    mesh = trimesh.load_mesh(output)
    assert count == len(mesh.faces)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert np.all(mesh.area_faces > 0)
    assert sum(part.volume > 0 for part in mesh.split()) == 1
    expected = source.trim_by_plane((0, 0, 1), grid.z + 4.7501)
    exported = read_stl(output).trim_by_plane((0, 0, 1), grid.z + 4.7501)
    assert (expected - exported).volume() + (exported - expected).volume() < 0.002
