import json
from pathlib import Path

import manifold3d as m
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase import RebaseError
from gridfinity_rebase.catalog import PRESETS
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import (
    detect_grid,
    detect_standard_base,
    donor_base,
    replace_base,
)
from gridfinity_rebase.presets import preset_base
from gridfinity_rebase.stl import read_stl, write_stl

EXAMPLE = Path(__file__).resolve().parents[1] / "tmp/gf_bin_1x1_h6_bin_v01.stl"


@pytest.mark.skipif(
    not EXAMPLE.exists(), reason="local standard-bin example unavailable"
)
@pytest.mark.parametrize("preset", list(PRESETS))
def test_reference_bin_auto_replacement_preserves_interior(preset, tmp_path, capsys):
    source = read_stl(EXAMPLE)
    grid = detect_grid(source)
    detected = detect_standard_base(source, grid)
    assert 6.9 <= detected.height < 6.94
    assert detected.interior_start == pytest.approx(6.94, abs=0.02)
    output = tmp_path / "result.stl"
    assert (
        main(["rebase", str(EXAMPLE), "--preset", preset, "-o", str(output), "--json"])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["base_height_mode"] == "auto"
    assert report["base_height_mm"] == detected.height
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert sum(part.volume > 0 for part in mesh.split()) == 1
    result = read_stl(output)
    cut = grid.z + detected.height + 0.0001
    original_upper = source.trim_by_plane((0, 0, 1), cut)
    new_upper = result.trim_by_plane((0, 0, 1), cut)
    assert (original_upper - new_upper).volume() + (
        new_upper - original_upper
    ).volume() < 0.002
    # Complete replacement of the bridge, including old holes/tiny STL voids.
    expected = preset_base(preset, grid, detected.height)
    for height in (0.2, 1.4, 3.5, 5.5, 6.8):
        assert result.slice(height).area() == pytest.approx(
            expected.slice(height).area(), abs=0.002
        )


@pytest.mark.parametrize("size", [(1, 1), (2, 3)])
def test_auto_full_base_removes_old_screw_bores(size, tmp_path, capsys):
    source = make_bin(*size, preset="rebuilt-screws", origin=(105, -23, -11))
    grid = detect_grid(source)
    detected = detect_standard_base(source, grid)
    assert detected.height == 7
    assert detected.interior_start is None
    path = tmp_path / "input.stl"
    output = tmp_path / "plain.stl"
    write_stl(source, path)
    assert (
        main(["rebase", str(path), "--preset", "plain", "-o", str(output), "--json"])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["base_height_mm"] == 7
    result = read_stl(output)
    assert len(result.decompose()) == 1
    expected = preset_base("plain", grid, 7)
    assert result.slice(grid.z + 6).area() == pytest.approx(
        expected.slice(grid.z + 6).area(), abs=0.002
    )


@pytest.mark.parametrize("floor", [5.8, 6.5, 6.94, 7.0])
def test_standard_floor_transition_is_respected(floor):
    source = make_bin()
    cavity = m.Manifold.cube((34, 34, 30)).translate((-17, -17, floor))
    source -= cavity
    grid = detect_grid(source)
    detected = detect_standard_base(source, grid)
    assert floor - 0.04 <= detected.height <= floor - 0.019
    result = replace_base(
        source, preset_base("plain", grid, detected.height), grid, detected.height
    )
    assert result.slice(floor + 0.01).area() == pytest.approx(
        source.slice(floor + 0.01).area()
    )


@pytest.mark.parametrize("preset", ["rebuilt", "rebuilt-screws"])
def test_1x1_donor_provides_continuous_full_bridge(preset, tmp_path):
    source = make_bin(3, 2, origin=(-66, 128, -15))
    donor = make_bin(preset=preset, origin=(200, -100, -4))
    target = detect_grid(source)
    replacement = donor_base(donor, detect_grid(donor), target, 7)
    result = replace_base(source, replacement, target, 7)
    expected = preset_base(preset, target, 7)
    assert result.slice(target.z + 6).area() == pytest.approx(
        expected.slice(target.z + 6).area(), abs=0.002
    )
    # The 0.5 mm inter-cell gap must be filled by a bridge, not copied as a slot.
    probe = m.Manifold.cube((0.4, 1, 1)).translate(
        (target.x + 20.8, target.y, target.z + 5)
    )
    assert (result ^ probe).volume() == pytest.approx(0.4)
    output = tmp_path / "result.stl"
    write_stl(result, output)
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert len(mesh.split()) == 1


@pytest.mark.skipif(
    not EXAMPLE.exists(), reason="local standard-bin example unavailable"
)
def test_auto_rejects_donor_with_lower_floor(tmp_path, capsys):
    path = tmp_path / "input.stl"
    write_stl(make_bin(), path)
    assert main(["rebase", str(path), "--base", str(EXAMPLE), "--json"]) == 2
    assert "Donor base ends" in json.loads(capsys.readouterr().err)["error"]
    assert not (tmp_path / "input-rebased.stl").exists()


@pytest.mark.skipif(
    not EXAMPLE.with_name("test.stl").exists(),
    reason="local custom example unavailable",
)
def test_custom_model_requires_explicit_override(tmp_path, capsys):
    source = EXAMPLE.with_name("test.stl")
    assert main(["inspect", str(source), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["standard_bin"] is False
    output = tmp_path / "custom.stl"
    assert (
        main(["rebase", str(source), "--preset", "plain", "-o", str(output), "--json"])
        == 2
    )
    assert (
        "standard bin base not recognized"
        in json.loads(capsys.readouterr().err)["error"]
    )
    assert not output.exists()
    assert (
        main(
            [
                "rebase",
                str(source),
                "--preset",
                "plain",
                "--base-height",
                "4.75",
                "-o",
                str(output),
            ]
        )
        == 0
    )


def test_auto_rejects_missing_standard_bridge():
    source = make_bin()
    cut = m.Manifold.cube((2, 50, 2)).translate((-1, -25, 4.8))
    source -= cut
    with pytest.raises(RebaseError, match="standard bin base not recognized"):
        detect_standard_base(source, detect_grid(source))
