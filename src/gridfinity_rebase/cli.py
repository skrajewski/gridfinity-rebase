import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

from . import RebaseError, __version__


def parser():
    p = argparse.ArgumentParser(
        description="Replace the mating feet of a Gridfinity bin STL (mm, Z up)."
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    presets = sub.add_parser(
        "presets", help="List offline base presets and their geometry"
    )
    presets.add_argument("--json", action="store_true")
    inspect = sub.add_parser(
        "inspect", help="Validate an STL and detect its Gridfinity grid"
    )
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--json", action="store_true")
    rebase = sub.add_parser(
        "rebase", help="Replace the bottom of an STL with a donor's feet"
    )
    rebase.add_argument("input", type=Path)
    choice = rebase.add_mutually_exclusive_group(required=True)
    choice.add_argument("--base", type=Path, help="STL providing the replacement base")
    from .catalog import PRESETS

    choice.add_argument(
        "--preset", choices=PRESETS, help="Generate the base natively, offline"
    )
    rebase.add_argument(
        "--segments",
        type=int,
        default=64,
        help="Curve resolution: multiple of 8, 32–256 (default: 64)",
    )
    rebase.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Default: INPUT-rebased-PRESET.stl, or INPUT-rebased.stl with a donor",
    )
    rebase.add_argument(
        "--base-height",
        type=float,
        default=None,
        help="Override automatic standard-bin base detection with an explicit height in mm",
    )
    rebase.add_argument("--overwrite", action="store_true")
    rebase.add_argument("--json", action="store_true")
    return p


def main(argv=None):
    start = perf_counter()
    args = parser().parse_args(argv)
    try:
        from .catalog import PRESETS

        if args.command == "presets":
            print(
                json.dumps(PRESETS)
                if args.json
                else "\n".join(
                    f"{name:16} {description}" for name, description in PRESETS.items()
                )
            )
            return 0
        from .geometry import (
            detect_grid,
            detect_standard_base,
            donor_base,
            replace_base,
            validate_height,
        )
        from .presets import preset_base
        from .stl import read_stl, write_stl

        solid = read_stl(args.input)
        grid = detect_grid(solid, str(args.input))
        report = {
            "input": str(args.input),
            **grid.describe(),
            "triangles": solid.num_tri(),
        }
        if args.command == "inspect" or args.base_height is None:
            try:
                standard = detect_standard_base(solid, grid, str(args.input))
            except RebaseError as exc:
                if args.command != "inspect":
                    raise
                report.update(standard_bin=False, base_detection_error=str(exc))
            else:
                report.update(standard.describe())
        if args.command == "rebase":
            preset_suffix = f"-{args.preset}" if args.preset else ""
            output = args.output or args.input.with_name(
                f"{args.input.stem}-rebased{preset_suffix}.stl"
            )
            sources = [args.input] + ([args.base] if args.base else [])
            if output.resolve() in [p.resolve() for p in sources]:
                raise RebaseError("Output must differ from both source files")
            if output.exists() and not args.overwrite:
                raise RebaseError(f"Output already exists: {output}; use --overwrite")
            height = (
                args.base_height if args.base_height is not None else standard.height
            )
            validate_height(solid, grid, height)
            if args.preset:
                replacement = preset_base(args.preset, grid, height, args.segments)
            else:
                donor = read_stl(args.base)
                donor_grid = detect_grid(donor, str(args.base))
                if args.base_height is None:
                    donor_standard = detect_standard_base(
                        donor, donor_grid, str(args.base)
                    )
                    if donor_standard.height < height - 0.001:
                        raise RebaseError(
                            f"Donor base ends at {donor_standard.height:g} mm, before the input's {height:g} mm cut; use a compatible donor or set --base-height explicitly"
                        )
                replacement = donor_base(donor, donor_grid, grid, height)
            result = replace_base(solid, replacement, grid, height)
            triangles = write_stl(result, output, overwrite=args.overwrite)
            report.update(
                output=str(output),
                base=args.preset or str(args.base),
                base_height_mm=height,
                base_height_mode="manual" if args.base_height is not None else "auto",
                triangles=triangles,
            )
        report["elapsed_ms"] = round((perf_counter() - start) * 1000, 2)
        if args.json:
            print(json.dumps(report))
        elif args.command == "inspect":
            detail = (
                f"standard bin, base cut {report['recommended_base_height_mm']:g} mm"
                if report["standard_bin"]
                else "custom model; explicit --base-height required"
            )
            print(
                f"Gridfinity {grid.nx}x{grid.ny}, {detail}, {solid.num_tri():,} triangles ({report['elapsed_ms']:g} ms)"
            )
        else:
            print(
                f"{report['output']} — {grid.nx}x{grid.ny}, {report['triangles']:,} triangles ({report['elapsed_ms']:g} ms)"
            )
        return 0
    except RebaseError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
