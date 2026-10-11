import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

from . import RebaseError, __version__


def parser():
    p = argparse.ArgumentParser(description="Replace the mating feet of a Gridfinity bin STL (mm, Z up).")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Validate an STL and detect its Gridfinity grid")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--json", action="store_true")
    rebase = sub.add_parser("rebase", help="Replace the bottom of an STL with a donor's feet")
    rebase.add_argument("input", type=Path)
    rebase.add_argument("--base", type=Path, required=True, help="STL providing the replacement base")
    rebase.add_argument("-o", "--output", type=Path, help="Default: INPUT-rebased.stl")
    rebase.add_argument("--base-height", type=float, default=4.75, help="Replace this many mm from the bottom (default: 4.75)")
    rebase.add_argument("--overwrite", action="store_true")
    rebase.add_argument("--json", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    start = perf_counter()
    try:
        from .geometry import detect_grid, donor_base, replace_base, validate_height
        from .stl import read_stl, write_stl
        solid = read_stl(args.input)
        grid = detect_grid(solid, str(args.input))
        report = {"input": str(args.input), **grid.describe(), "triangles": solid.num_tri()}
        if args.command == "rebase":
            output = args.output or args.input.with_name(f"{args.input.stem}-rebased.stl")
            if output.resolve() in (args.input.resolve(), args.base.resolve()):
                raise RebaseError("Output must differ from both source files")
            if output.exists() and not args.overwrite:
                raise RebaseError(f"Output already exists: {output}; use --overwrite")
            validate_height(solid, grid, args.base_height)
            donor = read_stl(args.base)
            donor_grid = detect_grid(donor, str(args.base))
            replacement = donor_base(donor, donor_grid, grid, args.base_height)
            result = replace_base(solid, replacement, grid, args.base_height)
            write_stl(result, output, overwrite=args.overwrite)
            report.update(output=str(output), base=str(args.base), base_height_mm=args.base_height, triangles=result.num_tri())
        report["elapsed_ms"] = round((perf_counter() - start) * 1000, 2)
        if args.json:
            print(json.dumps(report))
        elif args.command == "inspect":
            print(f"Gridfinity {grid.nx}x{grid.ny}, {solid.num_tri():,} triangles ({report['elapsed_ms']:g} ms)")
        else:
            print(f"{report['output']} — {grid.nx}x{grid.ny}, {report['triangles']:,} triangles ({report['elapsed_ms']:g} ms)")
        return 0
    except RebaseError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
