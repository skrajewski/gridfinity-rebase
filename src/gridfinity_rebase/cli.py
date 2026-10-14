import argparse
import json
import re
import shutil
import sys
import textwrap
from pathlib import Path
from time import perf_counter
from typing import Any

from . import RebaseError, __version__


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep help readable in a wide terminal and compact option labels."""

    def __init__(self, prog):
        width = min(shutil.get_terminal_size().columns, 96)
        super().__init__(prog, width=width, max_help_position=min(28, width // 3))
        self._action_max_length = self._max_help_position - 2

    def add_text(self, text):
        if not text or "\n  " not in text:
            return super().add_text(text)
        # Render the epilog's blocks through argparse's own section styling.
        for block in text.split("\n\n"):
            heading, separator, body = block.partition("\n")
            if separator and body.startswith("  "):
                self.start_section(heading)
                super().add_text(textwrap.dedent(body))
                self.end_section()
            else:
                super().add_text(block)

    def _styled(self, text, role):
        theme = getattr(self, "_theme", None)
        if theme is None:
            return text
        return getattr(theme, role) + text + theme.reset

    def _fill_text(self, text, width, indent):
        formatted = super()._fill_text(text, width, indent)

        def style_token(match):
            token = match.group()
            if match.lastgroup == "option":
                role = "long_option" if token.startswith("--") else "short_option"
            else:
                role = {"program": "prog", "file": "action", "preset": "label"}[
                    match.lastgroup
                ]
            return self._styled(token, role)

        return re.sub(
            r"(?P<option>--[\w-]+|(?<!\w)-[a-zA-Z]\b)"
            r"|(?P<program>\bgridfinity-rebase\b)"
            r"|(?P<file>\b[\w.-]+\.stl\b)"
            r"|(?P<preset>\b(?:rebuilt-screws|press-fit|rebuilt|refined|standard|plain)\b)",
            style_token,
            formatted,
        )

    def _format_action_invocation(self, action):
        if isinstance(action, argparse.BooleanOptionalAction):
            return self._styled(f"--[no-]{action.option_strings[0][2:]}", "long_option")
        return super()._format_action_invocation(action)

    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            return "".join(
                self._format_action(command) for command in action._get_subactions()
            )
        return super()._format_action(action)


def add_help(p, *, version=False):
    general = p.add_argument_group("General")
    general.add_argument("-h", "--help", action="help", help="Show help and exit")
    if version:
        general.add_argument(
            "--version",
            action="version",
            version=__version__,
            help="Show version and exit",
        )


def parser():
    p = argparse.ArgumentParser(
        prog="gridfinity-rebase",
        usage="%(prog)s COMMAND [OPTIONS]",
        description="Replace a Gridfinity bin's base while preserving its interior.",
        formatter_class=HelpFormatter,
        add_help=False,
        epilog=(
            "Quick start\n"
            "  gridfinity-rebase rebase bin.stl --preset rebuilt\n"
            "  gridfinity-rebase rebase bin.stl --screws\n\n"
            "More help\n"
            "  Run 'gridfinity-rebase COMMAND --help' for command options."
        ),
    )
    sub = p.add_subparsers(prog=p.prog, dest="command", required=True, title="Commands")
    presets = sub.add_parser(
        "presets",
        help="List presets and their geometry",
        usage="%(prog)s [OPTIONS]",
        formatter_class=HelpFormatter,
        add_help=False,
        description="List the built-in base presets and compatibility aliases.",
    )
    presets.add_argument_group("Output").add_argument(
        "--json", action="store_true", help="Print presets as JSON"
    )
    add_help(presets)
    inspect = sub.add_parser(
        "inspect",
        help="Validate an STL and detect its grid",
        usage="%(prog)s INPUT.stl [OPTIONS]",
        formatter_class=HelpFormatter,
        add_help=False,
        description="Check the model's grid, base profile and replacement height.",
    )
    inspect.add_argument_group("Input").add_argument(
        "input", type=Path, metavar="INPUT.stl", help="Bin STL in millimetres, Z up"
    )
    inspect.add_argument_group("Output").add_argument(
        "--json", action="store_true", help="Print the inspection report as JSON"
    )
    add_help(inspect)
    rebase = sub.add_parser(
        "rebase",
        help="Replace the base of a bin STL",
        usage="%(prog)s INPUT.stl [OPTIONS]",
        formatter_class=HelpFormatter,
        add_help=False,
        description=(
            "Generate a new base or copy one from a donor STL.\n"
            "Start from plain or a preset, then override individual geometry settings."
        ),
        epilog=(
            "Presets\n"
            "  plain, rebuilt, rebuilt-screws, press-fit\n"
            "  Aliases: refined = rebuilt; standard = plain\n\n"
            "Examples\n"
            "  gridfinity-rebase rebase bin.stl --screws\n"
            "  gridfinity-rebase rebase bin.stl --preset press-fit --screws\n"
            "  gridfinity-rebase rebase bin.stl --preset rebuilt --only-corners\n"
            "  gridfinity-rebase rebase bin.stl --base donor.stl -o result.stl\n\n"
            "Notes\n"
            "  Use --no-screws, --no-crush-ribs or --no-thumbscrew to disable a setting.\n"
            "  Geometry overrides require a generated base; --base copies the donor as-is."
        ),
    )
    rebase.add_argument_group("Input").add_argument(
        "input",
        type=Path,
        metavar="INPUT.stl",
        help="Bin STL in millimetres, feet down, Z up",
    )
    choice = rebase.add_argument_group("Base").add_mutually_exclusive_group()
    choice.add_argument(
        "--base", type=Path, metavar="FILE", help="Copy the base from a donor STL"
    )
    from . import list_presets

    choice.add_argument(
        "--preset",
        choices=tuple(preset.id for preset in list_presets()),
        metavar="NAME",
        help="Starting settings (default: plain)",
    )
    geometry = rebase.add_argument_group("Geometry")
    geometry.add_argument(
        "--magnets",
        choices=("none", "side", "bottom"),
        metavar="STYLE",
        help="Magnet pockets: none, side, bottom",
    )
    geometry.add_argument(
        "--screws",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="3 mm screw bores (depth up to 7 mm)",
    )
    geometry.add_argument(
        "--crush-ribs",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Press-fit ribs; requires bottom magnet pockets",
    )
    geometry.add_argument(
        "--only-corners",
        action="store_true",
        default=None,
        help="Magnet pockets and screw bores only at the bin's four outer corners",
    )
    geometry.add_argument(
        "--thumbscrew",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Central M15x1.5 threaded hole in each foot",
    )
    output = rebase.add_argument_group("Output")
    output.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="Output STL (default: named from input and settings)",
    )
    output.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output file"
    )
    output.add_argument(
        "--json", action="store_true", help="Print the result report as JSON"
    )
    advanced = rebase.add_argument_group("Advanced")
    advanced.add_argument(
        "--segments",
        type=int,
        default=64,
        metavar="N",
        help="Curve segments: 32–256, multiple of 8 (default: 64)",
    )
    advanced.add_argument(
        "--base-height",
        type=float,
        default=None,
        metavar="MM",
        help="Manual cut height in mm (default: automatic)",
    )
    add_help(rebase)
    add_help(p, version=True)
    return p


def main(argv=None):
    start = perf_counter()
    argv = sys.argv[1:] if argv is None else argv
    argument_parser = parser()
    if not argv:
        argument_parser.print_help()
        return 0
    args = argument_parser.parse_args(argv)
    try:
        from . import list_presets, resolve_options

        options = None
        if args.command == "rebase":
            overrides = {
                name: getattr(args, name)
                for name in (
                    "magnets",
                    "screws",
                    "crush_ribs",
                    "thumbscrew",
                    "only_corners",
                )
            }
            if args.base:
                flags = [
                    ("--no-" if value is False else "--") + name.replace("_", "-")
                    for name, value in overrides.items()
                    if value is not None
                ]
                if flags:
                    raise RebaseError(
                        f"Geometry options ({', '.join(flags)}) cannot be used with --base; donor bases are copied as-is"
                    )
            else:
                options = resolve_options(args.preset or "plain", **overrides)
        if args.command == "presets":
            presets = {preset.id: preset.description for preset in list_presets()}
            print(
                json.dumps(presets)
                if args.json
                else "\n".join(
                    f"{name:16} {description}" for name, description in presets.items()
                )
            )
            return 0
        from . import (
            DonorBase,
            GeneratedBase,
            inspect_model,
            load_stl,
            rebase,
            save_stl,
        )

        model = load_stl(args.input)
        report: dict[str, Any] = {"input": str(args.input)}
        if args.command == "inspect":
            report.update(inspect_model(model).describe())
        if args.command == "rebase":
            preset_suffix = ""
            if options is not None:
                preset = args.preset or "plain"
                if options == resolve_options(
                    preset,
                    thumbscrew=options.thumbscrew,
                    only_corners=options.only_corners,
                ):
                    name = preset + ("-thumbscrew" if options.thumbscrew else "")
                    if options.only_corners:
                        name += "-only-corners"
                else:
                    name = options.filename_suffix()
                preset_suffix = f"-{name}"
            output = args.output or args.input.with_name(
                f"{args.input.stem}-rebased{preset_suffix}.stl"
            )
            sources = [args.input] + ([args.base] if args.base else [])
            if output.resolve() in [p.resolve() for p in sources]:
                raise RebaseError("Output must differ from both source files")
            if output.exists() and not args.overwrite:
                raise RebaseError(f"Output already exists: {output}; use --overwrite")
            base = (
                GeneratedBase(options, args.segments)
                if options is not None
                else DonorBase(load_stl(args.base))
            )
            result = rebase(model, base=base, base_height_mm=args.base_height)
            triangles = save_stl(result.model, output, overwrite=args.overwrite)
            report.update(result.report.describe())
            report.update(
                output=str(output),
                base=(args.preset or "plain")
                if options is not None
                else str(args.base),
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
            nx, ny = report["grid"]
            print(
                f"Gridfinity {nx}x{ny}, {detail}, {report['triangles']:,} triangles ({report['elapsed_ms']:g} ms)"
            )
        else:
            nx, ny = report["grid"]
            print(
                f"{report['output']} — {nx}x{ny}, {report['triangles']:,} triangles ({report['elapsed_ms']:g} ms)"
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
