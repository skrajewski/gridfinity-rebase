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
    presets = sub.add_parser("presets", help="List offline base presets and their geometry")
    presets.add_argument("--json", action="store_true")
    inspect = sub.add_parser("inspect", help="Validate an STL and detect its Gridfinity grid")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--json", action="store_true")
    rebase = sub.add_parser("rebase", help="Replace the bottom of an STL with a donor's feet")
    rebase.add_argument("input", type=Path)
    choice = rebase.add_mutually_exclusive_group(required=True)
    choice.add_argument("--base", type=Path, help="STL providing the replacement base")
    from .catalog import PRESETS
    choice.add_argument("--preset", choices=PRESETS, help="Generate the base natively, offline")
    rebase.add_argument("--segments", type=int, default=64, help="Curve resolution: multiple of 8, 32–256 (default: 64)")
    rebase.add_argument("-o", "--output", type=Path, help="Default: INPUT-rebased.stl")
    rebase.add_argument("--base-height", type=float, default=4.75, help="Replace this many mm from the bottom (default: 4.75)")
    rebase.add_argument("--overwrite", action="store_true")
    rebase.add_argument("--json", action="store_true")
    return p


def main(argv=None):
    start = perf_counter()
    args = parser().parse_args(argv)
    try:
        from .catalog import PRESETS
        if args.command == "presets":
            print(json.dumps(PRESETS) if args.json else "\n".join(f"{name:16} {description}" for name, description in PRESETS.items()))
            return 0
        from .presets import preset_base
        from .geometry import detect_grid, donor_base, replace_base, validate_height
        from .stl import read_stl, write_stl
        solid = read_stl(args.input)
        grid = detect_grid(solid, str(args.input))
        report = {"input": str(args.input), **grid.describe(), "triangles": solid.num_tri()}
        if args.command == "rebase":
            output = args.output or args.input.with_name(f"{args.input.stem}-rebased.stl")
            sources = [args.input] + ([args.base] if args.base else [])
            if output.resolve() in [p.resolve() for p in sources]:
                raise RebaseError("Output must differ from both source files")
            if output.exists() and not args.overwrite:
                raise RebaseError(f"Output already exists: {output}; use --overwrite")
            validate_height(solid, grid, args.base_height)
            if args.preset:
                replacement = preset_base(args.preset, grid, args.base_height, args.segments)
            else:
                donor = read_stl(args.base)
                donor_grid = detect_grid(donor, str(args.base))
                replacement = donor_base(donor, donor_grid, grid, args.base_height)
            result = replace_base(solid, replacement, grid, args.base_height)
            write_stl(result, output, overwrite=args.overwrite)
            report.update(output=str(output), base=args.preset or str(args.base), base_height_mm=args.base_height, triangles=result.num_tri())
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
