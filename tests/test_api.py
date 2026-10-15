import json
import subprocess
import sys
from pathlib import Path

import manifold3d as m
import numpy as np
import pytest
import trimesh
from test_presets import make_bin

from gridfinity_rebase import (
    BaseOptions,
    DonorBase,
    GeneratedBase,
    Model,
    RebaseError,
    inspect_model,
    list_presets,
    load_stl,
    rebase,
    resolve_options,
    save_stl,
)
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import detect_grid
from gridfinity_rebase.presets import generate_base
from gridfinity_rebase.stl import read_stl, write_stl

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_bin(tmp_path, name="input", **kwargs):
    path = tmp_path / f"{name}.stl"
    write_stl(make_bin(**kwargs), path)
    return load_stl(path)


def test_reuse_model_without_io_or_mutation(tmp_path, monkeypatch, capsys):
    model = load_bin(tmp_path, origin=(105, -23, -11))
    assert model.source is not None
    original_vertices, original_faces = model.to_mesh()
    original_data = model.source.read_bytes()
    info = inspect_model(model)
    assert info.grid == (1, 1)
    assert info.origin_mm == pytest.approx((105, -23, -11), abs=1e-5)
    assert info.standard_bin and info.recommended_base_height_mm == 7

    def unexpected_read(*args, **kwargs):
        pytest.fail("An in-memory operation reopened the STL")

    monkeypatch.setattr("gridfinity_rebase.api.read_stl", unexpected_read)
    results = [
        rebase(model, base=GeneratedBase(options))
        for options in (
            resolve_options("plain"),
            resolve_options("rebuilt", screws=True),
        )
    ]
    assert all(result.model is not model for result in results)
    assert results[0].report.geometry == BaseOptions()
    assert results[1].report.geometry == BaseOptions(magnets="side", screws=True)
    assert results[0].report.base_height_mode == "auto"
    assert results[0].report.inspection == info
    assert results[0].report.triangles == results[0].model.triangles
    json.dumps(results[0].report.describe())
    vertices, faces = model.to_mesh()
    np.testing.assert_array_equal(vertices, original_vertices)
    np.testing.assert_array_equal(faces, original_faces)
    assert model.source.read_bytes() == original_data
    assert list(tmp_path.iterdir()) == [model.source]
    assert capsys.readouterr() == ("", "")


def test_mesh_copies_and_explicit_atomic_export(tmp_path):
    model = load_bin(tmp_path)
    result = rebase(
        model, base=GeneratedBase(resolve_options("press-fit", screws=True))
    )
    vertices, faces = result.model.to_mesh()
    assert vertices.dtype == np.float64 and faces.dtype == np.uint64
    assert vertices.shape[1] == faces.shape[1] == 3
    assert len(faces) == result.model.triangles
    mesh = trimesh.Trimesh(vertices, faces, process=True)
    assert mesh.is_watertight and mesh.volume > 0
    expected_vertices, expected_faces = vertices.copy(), faces.copy()
    vertices[:] = 0
    faces[:] = 0
    vertices, faces = result.model.to_mesh()
    np.testing.assert_array_equal(vertices, expected_vertices)
    np.testing.assert_array_equal(faces, expected_faces)

    output = tmp_path / "result.stl"
    count = save_stl(result.model, output)
    assert count == load_stl(output).triangles
    saved = output.read_bytes()
    with pytest.raises(RebaseError) as failure:
        save_stl(model, output)
    assert failure.value.code == "output_exists"
    assert failure.value.details["path"] == str(output)
    assert output.read_bytes() == saved
    save_stl(model, output, overwrite=True)
    assert not list(tmp_path.glob(".result.stl.*"))


@pytest.mark.parametrize(
    "donor_size,height", [((1, 1), 4.75), ((2, 3), None), ((3, 2), None)]
)
def test_donor_alignment_and_body_preservation(tmp_path, donor_size, height):
    model = load_bin(tmp_path, nx=2, ny=3, origin=(105, -23, -11))
    donor = load_bin(
        tmp_path,
        "donor",
        nx=donor_size[0],
        ny=donor_size[1],
        preset="rebuilt",
        screws=True,
        origin=(-66, 128, -15),
    )
    original_donor = donor.to_mesh()
    result = rebase(model, base=DonorBase(donor), base_height_mm=height)
    assert result.report.geometry is None
    assert result.report.describe()["thumbscrew"] is None
    assert result.report.grid == (2, 3)
    output = tmp_path / "result.stl"
    save_stl(result.model, output)
    assert model.source is not None
    source = read_stl(model.source)
    solid = read_stl(output)
    grid = detect_grid(source)
    cut = grid.z + result.report.base_height_mm + 0.0001
    original_upper = source.trim_by_plane((0, 0, 1), cut)
    result_upper = solid.trim_by_plane((0, 0, 1), cut)
    assert (original_upper - result_upper).volume() + (
        result_upper - original_upper
    ).volume() < 0.002
    expected = generate_base(
        resolve_options("rebuilt", screws=True), grid, result.report.base_height_mm
    )
    slices = (1.4, 3.5) if height is not None else (1.4, 3.5, 6.0)
    for z in slices:
        assert solid.slice(grid.z + z).area() == pytest.approx(
            expected.slice(grid.z + z).area(), abs=0.002 * grid.nx * grid.ny
        )
    for actual, original in zip(donor.to_mesh(), original_donor):
        np.testing.assert_array_equal(actual, original)


def test_custom_model_inspection_and_manual_override():
    model = load_stl(FIXTURES / "test.stl")
    info = inspect_model(model)
    assert not info.standard_bin
    assert info.recommended_base_height_mm is None
    assert info.base_detection_error_code == "unrecognized_base"
    with pytest.raises(RebaseError) as failure:
        rebase(model, base=GeneratedBase())
    assert failure.value.code == "unrecognized_base"
    result = rebase(model, base=GeneratedBase(), base_height_mm=4.75)
    assert result.report.base_height_mm == 4.75
    assert result.report.base_height_mode == "manual"
    assert result.report.inspection is None
    assert "standard_bin" not in result.report.describe()


@pytest.mark.parametrize("height", [4.7, float("nan"), float("inf"), "7", False])
def test_invalid_height_has_a_code(tmp_path, height):
    model = load_bin(tmp_path)
    with pytest.raises(RebaseError) as failure:
        rebase(model, base=GeneratedBase(), base_height_mm=height)
    assert failure.value.code == "invalid_height"


@pytest.mark.parametrize("segments", [0, 31, 33, 264, 64.0, "64", True])
def test_invalid_segments_have_a_code(segments):
    with pytest.raises(RebaseError) as failure:
        GeneratedBase(segments=segments)
    assert failure.value.code == "invalid_segments"


def test_input_and_donor_errors_have_codes(tmp_path):
    with pytest.raises(RebaseError) as failure:
        load_stl(tmp_path / "missing.stl")
    assert failure.value.code == "read_failed"
    path = tmp_path / "broken.stl"
    path.write_bytes(b"invalid")
    with pytest.raises(RebaseError) as failure:
        load_stl(path)
    assert failure.value.code == "invalid_mesh"
    write_stl(m.Manifold.cube((41.5, 41.5, 21)), path, overwrite=True)
    with pytest.raises(RebaseError) as failure:
        inspect_model(load_stl(path))
    assert failure.value.code == "invalid_grid"

    model = load_bin(tmp_path, nx=2, ny=3)
    donor = load_bin(tmp_path, "donor", nx=2, ny=2)
    with pytest.raises(RebaseError) as failure:
        rebase(model, base=DonorBase(donor))
    assert failure.value.code == "incompatible_donor"
    with pytest.raises(RebaseError) as failure:
        rebase(model, base=DonorBase(load_stl(FIXTURES / "gf_bin_1x1_h6_bin_v01.stl")))
    assert failure.value.code == "incompatible_donor"
    assert failure.value.details["donor_base_height_mm"] < 7


def test_progress_and_callback_exception(tmp_path):
    model = load_bin(tmp_path)
    events = []
    rebase(model, base=GeneratedBase(), on_progress=events.append)
    assert [event.stage for event in events] == [
        "detecting_grid",
        "detecting_base",
        "generating_base",
        "replacing_base",
        "complete",
    ]
    events.clear()
    rebase(model, base=DonorBase(model), base_height_mm=7, on_progress=events.append)
    assert [event.stage for event in events] == [
        "detecting_grid",
        "preparing_donor",
        "replacing_base",
        "complete",
    ]
    events.clear()
    inspect_model(model, on_progress=events.append)
    assert [event.stage for event in events] == [
        "detecting_grid",
        "detecting_base",
        "complete",
    ]
    sentinel = RuntimeError("callback failed")

    def fail(event):
        if event.stage == "generating_base":
            raise sentinel

    with pytest.raises(RuntimeError) as failure:
        rebase(model, base=GeneratedBase(), on_progress=fail)
    assert failure.value is sentinel


def test_presets_and_validation():
    presets = {preset.id: preset for preset in list_presets()}
    assert set(presets) == {"plain", "magnet-holes", "rebuilt", "press-fit", "refined"}
    assert presets["refined"].alias_of == "rebuilt"
    assert presets["refined"].options == presets["rebuilt"].options
    assert presets["plain"].alias_of is None
    assert (
        resolve_options("magnet-holes", crush_ribs=True) == presets["press-fit"].options
    )
    with pytest.raises(RebaseError) as failure:
        resolve_options("missing")
    assert failure.value.code == "unknown_preset"
    with pytest.raises(RebaseError) as failure:
        # Deliberately violate the type contract to test runtime validation.
        BaseOptions(screws="false")  # pyright: ignore[reportArgumentType]
    assert failure.value.code == "invalid_options"
    assert failure.value.details["field"] == "screws"
    with pytest.raises(RebaseError):
        DonorBase("donor.stl")  # pyright: ignore[reportArgumentType]
    with pytest.raises(RebaseError):
        GeneratedBase(options={})  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError, match="load_stl"):
        Model()


@pytest.mark.parametrize("preset", ["rebuilt-screws", "side-2mm", "standard"])
def test_removed_presets_are_rejected(preset):
    with pytest.raises(RebaseError) as failure:
        resolve_options(preset)
    assert failure.value.code == "unknown_preset"


def test_presets_and_help_do_not_load_native_engine():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from gridfinity_rebase import BaseOptions, list_presets, resolve_options
from gridfinity_rebase.cli import main
assert list_presets()
assert resolve_options() == BaseOptions()
assert main([]) == 0
assert main(['presets', '--json']) == 0
assert 'manifold3d' not in sys.modules
assert 'numpy' not in sys.modules
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_and_library_share_report_and_geometry(tmp_path, capsys):
    model = load_bin(tmp_path)
    options = resolve_options("rebuilt", screws=True, only_corners=True)
    result = rebase(model, base=GeneratedBase(options))
    library_output = tmp_path / "library.stl"
    exported_triangles = save_stl(result.model, library_output)
    cli_output = tmp_path / "cli.stl"
    assert (
        main(
            [
                "rebase",
                str(model.source),
                "--preset",
                "rebuilt",
                "--screws",
                "--only-corners",
                "--json",
                "-o",
                str(cli_output),
            ]
        )
        == 0
    )
    cli_report = json.loads(capsys.readouterr().out)
    expected = result.report.describe()
    expected["triangles"] = exported_triangles
    for key, value in expected.items():
        if key != "elapsed_ms":
            assert cli_report[key] == value
    # Native booleans may order triangles differently between runs.
    cli_solid, library_solid = read_stl(cli_output), read_stl(library_output)
    assert (cli_solid - library_solid).volume() + (
        library_solid - cli_solid
    ).volume() < 1e-6
