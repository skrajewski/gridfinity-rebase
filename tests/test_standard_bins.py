import json
from pathlib import Path

import manifold3d as m
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase import (
    DonorBase,
    GeneratedBase,
    RebaseError,
    load_stl,
    rebase,
    save_stl,
)
from gridfinity_rebase.catalog import PRESETS, resolve_options
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import (
    Grid,
    detect_grid,
    detect_standard_base,
    donor_base,
    replace_base,
)
from gridfinity_rebase.presets import generate_base, preset_base, rounded_prism
from gridfinity_rebase.stl import read_stl, write_stl

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLE = FIXTURES / "gf_bin_1x1_h6_bin_v01.stl"


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
    source = make_bin(*size, preset="rebuilt", screws=True, origin=(105, -23, -11))
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


@pytest.mark.parametrize("screws", [False, True])
def test_1x1_donor_provides_continuous_full_bridge(screws, tmp_path):
    source = make_bin(3, 2, origin=(-66, 128, -15))
    donor = make_bin(preset="rebuilt", screws=screws, origin=(200, -100, -4))
    target = detect_grid(source)
    replacement = donor_base(donor, detect_grid(donor), target, 7)
    result = replace_base(source, replacement, target, 7)
    expected = generate_base(resolve_options("rebuilt", screws=screws), target, 7)
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


def test_auto_rejects_donor_with_lower_floor(tmp_path, capsys):
    path = tmp_path / "input.stl"
    write_stl(make_bin(), path)
    assert main(["rebase", str(path), "--base", str(EXAMPLE), "--json"]) == 2
    assert "Donor base ends" in json.loads(capsys.readouterr().err)["error"]
    assert not (tmp_path / "input-rebased.stl").exists()


@pytest.mark.parametrize("json_output", [False, True])
def test_custom_model_warns_and_replaces_only_feet(tmp_path, capsys, json_output):
    source = FIXTURES / "test.stl"
    assert main(["inspect", str(source), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["standard_bin"] is False
    output = tmp_path / "custom.stl"
    flags = ["--json"] if json_output else []
    assert main([str(source), "--preset", "plain", "-o", str(output), *flags]) == 0
    captured = capsys.readouterr()
    if json_output:
        report = json.loads(captured.out)
        assert report["standard_bin"] is False
        assert report["base_height_mode"] == "auto"
        assert report["base_height_mm"] == 4.75
        assert len(report["warnings"]) == 1
        assert "old holes" in report["warnings"][0]
        assert captured.err == ""
    else:
        assert "Warning: Standard bin base not recognized" in captured.err
        assert "4.75 mm" in captured.err
        assert str(output) in captured.out
    original = read_stl(source).trim_by_plane((0, 0, 1), 4.7501)
    upper = read_stl(output).trim_by_plane((0, 0, 1), 4.7501)
    assert (original - upper).volume() + (upper - original).volume() < 0.002
    manual_output = tmp_path / "manual.stl"
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
                str(manual_output),
            ]
        )
        == 0
    )
    assert capsys.readouterr().err == ""


def test_auto_rejects_missing_standard_bridge():
    source = make_bin()
    cut = m.Manifold.cube((2, 50, 2)).translate((-1, -25, 4.8))
    source -= cut
    with pytest.raises(RebaseError, match="standard bin base not recognized"):
        detect_standard_base(source, detect_grid(source))


def make_open_holder(ny=3):
    # Like the ruler holder: feet remain separate until Z=5, then a full
    # bridge supports slots opening through both ends above Z=5.75.
    feet = m.Manifold.batch_boolean(
        [preset_base("plain", Grid(1, 1, 0, 42 * j, 0), 5) for j in range(ny)],
        m.OpType.Add,
    )
    body = rounded_prism(41.5, ny * 42 - 0.5, 3.75, 5, 14).translate(
        (0, (ny - 1) * 21, 0)
    )
    for x in (-10, 0, 10):
        body -= m.Manifold.cube((2, ny * 42 + 14, 10)).translate((x - 1, -25, 5.75))
    return feet + body


@pytest.mark.parametrize("origin", [(0, 0, 0), (105, -23, -11)])
def test_fallback_preserves_delayed_bridge_and_open_slots(tmp_path, origin):
    source = make_open_holder().translate(origin)
    path = tmp_path / "holder.stl"
    write_stl(source, path)
    model = load_stl(path)
    grid = detect_grid(source)
    options = resolve_options("rebuilt", only_corners=True)
    result = rebase(model, base=GeneratedBase(options))
    assert result.report.base_height_mode == "auto"
    assert result.report.base_height_mm == 4.75
    assert result.report.warnings
    output = tmp_path / "rebased.stl"
    save_stl(result.model, output)
    actual = read_stl(output)
    cut = grid.z + 4.7501
    original_upper = source.trim_by_plane((0, 0, 1), cut)
    new_upper = actual.trim_by_plane((0, 0, 1), cut)
    assert (original_upper - new_upper).volume() + (
        new_upper - original_upper
    ).volume() < 0.006
    expected = generate_base(options, grid, 4.75)
    for height in (0.3, 1.4, 3.5, 4.6):
        assert actual.slice(grid.z + height).area() == pytest.approx(
            expected.slice(grid.z + height).area(), abs=0.006
        )
    mesh = trimesh.load_mesh(output)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert sum(part.volume > 0 for part in mesh.split()) == 1


@pytest.mark.parametrize("donor_ny", [1, 3])
def test_fallback_can_copy_custom_donor_feet(tmp_path, donor_ny):
    path = tmp_path / "holder.stl"
    source = make_open_holder()
    write_stl(source, path)
    donor_path = tmp_path / "donor.stl"
    write_stl(make_open_holder(donor_ny), donor_path)
    result = rebase(load_stl(path), base=DonorBase(load_stl(donor_path)))
    assert result.report.base_height_mode == "auto"
    assert result.report.geometry is None
    output = tmp_path / "result.stl"
    save_stl(result.model, output)
    assert sum(part.volume() > 0 for part in read_stl(output).decompose()) == 1


def test_fallback_still_rejects_incompatible_seam(tmp_path, capsys):
    source = make_bin()
    source -= m.Manifold.cube((5, 50, 30)).translate((18, -25, 4.75))
    path = tmp_path / "bad-seam.stl"
    write_stl(source, path)
    with pytest.raises(RebaseError) as failure:
        rebase(load_stl(path), base=GeneratedBase())
    assert failure.value.code == "incompatible_seam"
    assert main([str(path), "--json"]) == 2
    assert "does not fit" in json.loads(capsys.readouterr().err)["error"]
    assert not (tmp_path / "bad-seam-rebased-plain.stl").exists()
