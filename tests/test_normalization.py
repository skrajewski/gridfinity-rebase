"""Z rotation must not change validation, rebasing or source coordinates."""

import json
from pathlib import Path

import manifold3d as m
import numpy as np
import pytest
import trimesh
from test_presets import make_bin
from test_standard_bins import make_open_holder

from gridfinity_rebase import (
    DonorBase,
    GeneratedBase,
    RebaseError,
    inspect_model,
    load_stl,
    rebase,
    resolve_options,
    save_stl,
)
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import Grid, detect_grid, normalize_model
from gridfinity_rebase.presets import preset_base
from gridfinity_rebase.stl import read_stl, write_stl


def difference(a, b):
    return abs((a - b).volume()) + abs((b - a).volume())


def assert_valid_stl(path):
    mesh = trimesh.load_mesh(path)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert np.all(mesh.area_faces > 0)
    assert len(mesh.split()) == 1


def stl_volume_budget(a, b):
    # The two paths quantize at different stages. A one-ULP displacement
    # over each surface bounds their float32 roundoff contribution to volume.
    coordinate = max(abs(v) for solid in (a, b) for v in solid.bounding_box())
    ulp = float(np.spacing(np.float32(coordinate)))
    return (a.surface_area() + b.surface_area()) * ulp


@pytest.mark.parametrize("size", [(1, 1), (1, 6), (6, 1), (2, 3), (3, 3)])
@pytest.mark.parametrize(
    "angle", [0, 0.01, 17.3, -33.7, 44.999, 45, 45.001, 89.9, 90, 147.25, 270]
)
def test_local_frame_for_any_z_angle(size, angle, tmp_path):
    origin = (105.125, -23.375, -11.5)
    path = tmp_path / "input.stl"
    write_stl(make_bin(*size).rotate((0, 0, angle)).translate(origin), path)
    source = read_stl(path)
    normalized = normalize_model(source)
    canonical = (angle + 45) % 90 - 45
    quarter_turns = round((angle - canonical) / 90)
    expected_size = size[::-1] if quarter_turns % 2 else size
    assert normalized.grid == Grid(*expected_size, 0, 0, 0)
    detected = detect_grid(normalized.solid)
    assert (detected.nx, detected.ny) == expected_size
    assert (detected.x, detected.y, detected.z) == pytest.approx((0, 0, 0), abs=1e-7)
    assert normalized.frame.rotation_z_deg == pytest.approx(canonical, abs=0.00001)
    assert normalized.solid.bounding_box()[2] == 0
    np.testing.assert_allclose(
        normalized.frame.to_source(normalized.solid).to_mesh64().vert_properties,
        source.to_mesh64().vert_properties,
        atol=1e-11,
        rtol=0,
    )
    if quarter_turns == 0:
        assert normalized.frame.origin_mm == pytest.approx(origin, abs=0.00002)
    # Both directions use the same frame, including nonzero/negative source Z.
    np.testing.assert_allclose(
        normalized.frame.to_local(source).to_mesh64().vert_properties,
        normalized.solid.to_mesh64().vert_properties,
        atol=1e-11,
        rtol=0,
    )


def test_frame_uses_feet_instead_of_body_axes(tmp_path):
    # An asymmetric extension changes the bounding box and principal axes.
    source = make_bin() + m.Manifold.cube((65, 12, 8)).translate((0, 0, 12))
    path = tmp_path / "asymmetric.stl"
    write_stl(source.rotate((0, 0, 23.4567)).translate((-200, 300, 8)), path)
    info = inspect_model(load_stl(path))
    assert info.grid == (1, 1)
    assert info.rotation_z_deg == pytest.approx(23.4567, abs=0.0001)
    assert info.origin_mm == pytest.approx((-200, 300, 8), abs=0.00002)


@pytest.mark.parametrize(
    "size,angle,height",
    [
        ((1, 1), 17.3, None),
        ((1, 6), -45, None),
        ((2, 3), 147.25, None),
        ((3, 3), -33.7, 4.75),
    ],
)
def test_rebase_restores_pose_and_preserves_body(size, angle, height, tmp_path):
    origin = (105, -23, -11)
    path = tmp_path / "rotated.stl"
    write_stl(make_bin(*size).rotate((0, 0, angle)).translate(origin), path)
    data = path.read_bytes()
    model = load_stl(path)
    original_mesh = model.to_mesh()
    options = resolve_options("rebuilt", only_corners=True, screws=True)
    result = rebase(model, base=GeneratedBase(options), base_height_mm=height)
    info = inspect_model(model)
    assert result.report.origin_mm == info.origin_mm
    assert result.report.rotation_z_deg == info.rotation_z_deg
    assert result.report.describe()["rotation_z_deg"] == info.rotation_z_deg
    if height is None:
        assert result.report.inspection == info
        assert result.report.base_height_mm == 7
        assert result.report.warnings == ()
    else:
        assert result.report.inspection is None
    output = tmp_path / "result.stl"
    save_stl(result.model, output)
    assert_valid_stl(output)
    actual = read_stl(output)
    source = read_stl(path)
    cut = origin[2] + result.report.base_height_mm + 0.0001
    assert (
        difference(
            actual.trim_by_plane((0, 0, 1), cut),
            source.trim_by_plane((0, 0, 1), cut),
        )
        < 0.003 * size[0] * size[1]
    )
    assert sum(p.volume() > 0 for p in actual.decompose()) == 1
    # Compare the entire operation with rebasing first, then rotating it.
    reference_path = tmp_path / "reference.stl"
    write_stl(make_bin(*size), reference_path)
    reference = rebase(
        load_stl(reference_path), base=GeneratedBase(options), base_height_mm=height
    )
    expected = reference.model._solid.rotate((0, 0, angle)).translate(origin)
    assert difference(actual, expected) < stl_volume_budget(actual, expected)
    assert path.read_bytes() == data
    for before, after in zip(original_mesh, model.to_mesh()):
        np.testing.assert_array_equal(before, after)


@pytest.mark.parametrize("donor_size", [(1, 1), (2, 3), (3, 2)])
def test_independently_rotated_donor(donor_size, tmp_path):
    target_path, donor_path = tmp_path / "target.stl", tmp_path / "donor.stl"
    angle, origin = 17.3, (105, -23, -11)
    write_stl(make_bin(2, 3).rotate((0, 0, angle)).translate(origin), target_path)
    write_stl(
        make_bin(*donor_size, preset="rebuilt", screws=True)
        .rotate((0, 0, -62.8))
        .translate((-300, 200, 15)),
        donor_path,
    )
    donor = load_stl(donor_path)
    donor_mesh = donor.to_mesh()
    result = rebase(load_stl(target_path), base=DonorBase(donor))
    reference_path = tmp_path / "reference.stl"
    write_stl(make_bin(2, 3), reference_path)
    reference = rebase(
        load_stl(reference_path),
        base=GeneratedBase(resolve_options("rebuilt", screws=True)),
    )
    output = tmp_path / "result.stl"
    save_stl(result.model, output)
    assert_valid_stl(output)
    actual = read_stl(output)
    expected = reference.model._solid.rotate((0, 0, angle)).translate(origin)
    assert len(actual.decompose()) == 1
    assert difference(actual, expected) < stl_volume_budget(actual, expected)
    for before, after in zip(donor_mesh, donor.to_mesh()):
        np.testing.assert_array_equal(before, after)


def test_donor_export_collapses_float32_degenerate_seam_faces(tmp_path):
    # A donor seam can contain extremely thin boolean faces that become
    # collinear when transformed back and quantized to STL coordinates.
    target, donor, output = (
        tmp_path / name for name in ("target.stl", "donor.stl", "out.stl")
    )
    write_stl(make_bin(2, 3, origin=(105, -23, -11)), target)
    write_stl(
        make_bin(2, 3, preset="rebuilt", screws=True, origin=(-66, 128, -15)), donor
    )
    result = rebase(load_stl(target), base=DonorBase(load_stl(donor)))
    save_stl(result.model, output)
    assert_valid_stl(output)
    assert (
        difference(
            read_stl(target).trim_by_plane((0, 0, 1), -3.9999),
            read_stl(output).trim_by_plane((0, 0, 1), -3.9999),
        )
        < 0.002
    )


def test_cli_rotated_custom_holder_fallback(tmp_path, capsys):
    path, output = tmp_path / "holder.stl", tmp_path / "result.stl"
    write_stl(
        make_open_holder(ny=6).rotate((0, 0, 17.3)).translate((128, 128, 5)), path
    )
    assert main(["inspect", str(path), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["grid"] == [1, 6]
    assert info["rotation_z_deg"] == pytest.approx(17.3, abs=0.00001)
    assert not info["standard_bin"]
    assert (
        main(
            [
                str(path),
                "--preset",
                "rebuilt",
                "--only-corners",
                "--json",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["base_height_mm"] == 4.75
    assert report["warnings"]
    assert_valid_stl(output)
    source, actual = read_stl(path), read_stl(output)
    assert len(actual.decompose()) == 1
    assert (
        difference(
            source.trim_by_plane((0, 0, 1), 9.7501),
            actual.trim_by_plane((0, 0, 1), 9.7501),
        )
        < 0.018
    )


@pytest.mark.parametrize("angle", [17.3, -45, 89.9])
@pytest.mark.parametrize(
    "fault", ["pitch", "incomplete", "box", "scale", "upside_down"]
)
def test_rotation_does_not_relax_validation(angle, fault, tmp_path):
    foot = preset_base("plain", Grid(1, 1, 0, 0, 0))
    sources = {
        "pitch": foot + foot.translate((40, 0, 0)),
        "incomplete": foot + foot.translate((42, 0, 0)) + foot.translate((0, 42, 0)),
        "box": m.Manifold.cube((41.5, 41.5, 21)),
        "scale": make_bin().scale((0.8, 0.8, 0.8)),
        "upside_down": make_bin().rotate((180, 0, 0)),
    }
    path = tmp_path / "invalid.stl"
    write_stl(sources[fault].rotate((0, 0, angle)), path)
    model = load_stl(path)
    for operation in [inspect_model, lambda model: rebase(model, base=GeneratedBase())]:
        with pytest.raises(RebaseError) as failure:
            operation(model)
        assert failure.value.code == "invalid_grid"


@pytest.mark.parametrize("name", ["test.stl", "gf_bin_1x1_h6_bin_v01.stl"])
def test_rotated_real_exports(name, tmp_path):
    source = read_stl(Path(__file__).parent / "fixtures" / name)
    path = tmp_path / "rotated.stl"
    write_stl(source.rotate((0, 0, 23.4567)), path)
    model = load_stl(path)
    result = rebase(model, base=GeneratedBase(resolve_options("rebuilt")))
    output = tmp_path / "result.stl"
    save_stl(result.model, output)
    assert_valid_stl(output)
    actual = read_stl(output)
    cut = result.report.origin_mm[2] + result.report.base_height_mm + 0.0001
    assert (
        difference(
            read_stl(path).trim_by_plane((0, 0, 1), cut),
            actual.trim_by_plane((0, 0, 1), cut),
        )
        < 0.003
    )
