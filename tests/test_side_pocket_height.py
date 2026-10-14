import json
from pathlib import Path

import manifold3d as m
import numpy as np
import pytest
from test_presets import make_bin

from gridfinity_rebase import BaseOptions, RebaseError, resolve_options
from gridfinity_rebase.cli import main
from gridfinity_rebase.geometry import detect_grid
from gridfinity_rebase.presets import generate_base
from gridfinity_rebase.stl import read_stl, write_stl


@pytest.mark.parametrize(
    "flags,suffix",
    [
        (["--preset", "rebuilt"], "rebuilt"),
        (["--preset", "refined"], "refined"),
        (["--magnets", "side"], "magnets-side"),
        (["--preset", "side-2mm"], "side-2mm"),
        (
            ["--preset", "rebuilt", "--side-pocket-height", "2.1"],
            "magnets-side",
        ),
    ],
)
def test_cli_export_matches_reference_height_and_preserves_body(
    flags, suffix, tmp_path, capsys
):
    source = make_bin(3, 2, origin=(91.003685, 105.522885, 23.179289))
    path = tmp_path / "laser.stl"
    write_stl(source, path)
    original = path.read_bytes()
    source = read_stl(path)
    grid = detect_grid(source)
    assert main(["rebase", str(path), *flags, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["geometry"]["side_pocket_height_mm"] == 2.1
    assert report["output"] == str(tmp_path / f"laser-rebased-{suffix}.stl")
    result = read_stl(report["output"])
    legacy = generate_base(
        resolve_options("rebuilt", side_pocket_height_mm=1.9), grid, 7
    )
    for cx, cy in grid.cells:
        for (x, y), angle in [
            ((13, 13), 0),
            ((-13, 13), 90),
            ((-13, -13), 180),
            ((13, -13), 270),
        ]:
            local = result.translate((-cx - x, -cy - y, -grid.z)).rotate((0, 0, -angle))
            # Measure the complete throat outside the optional screw bore.
            probe = m.Manifold.cube((0.5, 8, 3.5)).translate((2, -4, 0))
            bounds = np.array((probe - local).bounding_box())
            assert bounds[[1, 2, 4, 5]] == pytest.approx(
                [-2.93, 0.4, 2.93, 2.5], abs=2e-5
            )
            # A 2 mm thickness plus 0.1 mm total vertical clearance fits;
            # the old 1.9 mm pocket must fail the same check. This probe
            # checks Z clearance, not the deliberate 5.86 mm width squeeze.
            thickness = m.Manifold.cube((0.25, 0.25, 2.1))
            thickness = thickness.translate((2, -0.125, 0.4))
            assert (local ^ thickness).volume() < 2e-6
            world = thickness.rotate((0, 0, angle)).translate((cx + x, cy + y, grid.z))
            assert (legacy ^ world).volume() == pytest.approx(0.0125, abs=2e-6)
    above = grid.z + report["base_height_mm"] + 0.0001
    upper = result.trim_by_plane((0, 0, 1), above)
    original_upper = source.trim_by_plane((0, 0, 1), above)
    assert (upper - original_upper).volume() + (original_upper - upper).volume() < 0.002
    assert len(result.decompose()) == 1
    assert path.read_bytes() == original


def test_measured_reference_accepts_same_vertical_clearance():
    path = Path(__file__).parent / "fixtures" / "gf_bin_1x1_h6_bin_v01.stl"
    source = read_stl(path)
    probe = m.Manifold.cube((0.25, 0.25, 2.1)).translate((15, 12.875, 0.4))
    assert (source ^ probe).volume() < 1e-8


@pytest.mark.parametrize("height", [1.7, 2.3, 3.0])
def test_explicit_height_changes_pocket_and_removal_slit_together(height):
    grid = detect_grid(make_bin())
    base = generate_base(
        resolve_options("rebuilt-screws", side_pocket_height_mm=height), grid, 7
    )
    # Check beyond the screw bore and in the underside removal slit.
    for x, floor in [(15, 0.4), (7, 0.0)]:
        probe = m.Manifold.cube((0.1, 0.1, 4)).translate((x, 12.95, 0))
        bounds = (probe - base).bounding_box()
        assert bounds[2] == pytest.approx(floor)
        assert bounds[5] == pytest.approx(0.4 + height)


@pytest.mark.parametrize(
    "height", [0, -1, 4.35, 5, float("nan"), float("inf"), True, "2.1"]
)
def test_invalid_heights_are_rejected(height):
    with pytest.raises(RebaseError) as failure:
        BaseOptions(magnets="side", side_pocket_height_mm=height)
    assert failure.value.code == "invalid_options"
    assert failure.value.details["field"] == "side_pocket_height_mm"


def test_height_overrides_and_magnet_style_changes():
    assert resolve_options("side-2mm").effective_side_pocket_height_mm == 2.1
    assert resolve_options("rebuilt").describe()["side_pocket_height_mm"] == 2.1
    assert (
        resolve_options("side-2mm", side_pocket_height_mm=2.3).side_pocket_height_mm
        == 2.3
    )
    for style in ("none", "bottom"):
        assert resolve_options("side-2mm", magnets=style).side_pocket_height_mm is None
        with pytest.raises(RebaseError, match="requires --magnets side"):
            resolve_options("side-2mm", magnets=style, side_pocket_height_mm=2.1)


@pytest.mark.parametrize(
    "flags,message",
    [
        (["--side-pocket-height", "2.1"], "requires --magnets side"),
        (["--preset", "rebuilt", "--side-pocket-height", "nan"], "must be finite"),
        (
            ["--base", "missing.stl", "--side-pocket-height", "2.1"],
            "cannot be used with --base",
        ),
    ],
)
def test_cli_rejects_invalid_combinations_before_io(flags, message, tmp_path, capsys):
    assert main(["rebase", str(tmp_path / "missing.stl"), *flags, "--json"]) == 2
    assert message in json.loads(capsys.readouterr().err)["error"]
