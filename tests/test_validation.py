import struct

import manifold3d as m
import numpy as np
import pytest
from test_presets import make_bin

from gridfinity_rebase import RebaseError
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import Grid, detect_grid, donor_base, replace_base
from gridfinity_rebase.presets import preset_base
from gridfinity_rebase.stl import FACET, read_stl, write_stl


def test_incorrect_pitch_incomplete_grid_and_units():
    foot = preset_base("standard", Grid(1, 1, 0, 0, 0))
    bad_pitch = foot + foot.translate((40, 0, 0))
    with pytest.raises(RebaseError, match="42 mm grid"):
        detect_grid(bad_pitch)
    l_shape = foot + foot.translate((42, 0, 0)) + foot.translate((0, 42, 0))
    with pytest.raises(RebaseError, match="complete rectangular grid"):
        detect_grid(l_shape)
    with pytest.raises(RebaseError, match="not Gridfinity"):
        detect_grid(make_bin().scale((0.001, 0.001, 0.001)))
    with pytest.raises(RebaseError, match="not Gridfinity"):
        detect_grid(make_bin().rotate((180, 0, 0)))


def test_square_corner_frustum_is_not_a_gridfinity_foot():
    rings = []
    for z, width in [(0, 35.6), (0.8, 37.2), (2.6, 37.2), (4.75, 41.5)]:
        rings.extend(
            [
                (x * width / 2, y * width / 2, z)
                for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]
            ]
        )
    # Hull of the lower two and upper two rings retains the vertical stage.
    points = np.asarray(rings, dtype=np.float64)
    solid = (
        m.Manifold.hull_points(points[:8])
        + m.Manifold.hull_points(points[4:12])
        + m.Manifold.hull_points(points[8:])
    )
    with pytest.raises(RebaseError, match="rounded corners"):
        detect_grid(solid)


def test_donor_and_seam_incompatibility():
    source = make_bin()
    grid = detect_grid(source)
    short = preset_base("standard", grid)
    with pytest.raises(RebaseError, match="shorter"):
        donor_base(short, grid, grid, 7)
    off_axis = short.translate((1, 0, 0))
    with pytest.raises(RebaseError, match="does not fit"):
        replace_base(source, off_axis, grid)
    disconnected = short.translate((0, 0, -0.01))
    with pytest.raises(RebaseError, match="disconnected feet"):
        replace_base(source, disconnected, grid)


def test_non_finite_and_truncated_binary_and_solid_header(tmp_path):
    path = tmp_path / "mesh.stl"
    write_stl(m.Manifold.cube((1, 2, 3)), path)
    good = path.read_bytes()
    path.write_bytes(b"solid looks ascii".ljust(80, b" ") + good[80:])
    assert read_stl(path).volume() == pytest.approx(6)
    path.write_bytes(good[:-1])
    with pytest.raises(RebaseError, match="truncated"):
        read_stl(path)
    records = np.frombuffer(good, dtype=FACET, offset=84).copy()
    records["vertices"][0, 0, 0] = float("nan")
    path.write_bytes(good[:80] + struct.pack("<I", len(records)) + records.tobytes())
    with pytest.raises(RebaseError, match="NaN"):
        read_stl(path)


@pytest.mark.parametrize("segments", [0, 31, 33, 264])
def test_bad_resolution_is_rejected(segments, tmp_path, capsys):
    source = tmp_path / "source.stl"
    write_stl(make_bin(), source)
    assert (
        main(
            ["rebase", str(source), "--preset", "rebuilt", "--segments", str(segments)]
        )
        == 2
    )
    assert "Segments" in capsys.readouterr().err
    assert not list(tmp_path.glob("source-rebased*.stl"))


def test_missing_files_and_output_directory(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "missing.stl")]) == 2
    assert "Cannot read" in capsys.readouterr().err
    source = tmp_path / "source.stl"
    write_stl(make_bin(), source)
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "rebuilt",
                "-o",
                str(tmp_path / "absent" / "result.stl"),
            ]
        )
        == 2
    )
    assert "Cannot write" in capsys.readouterr().err
