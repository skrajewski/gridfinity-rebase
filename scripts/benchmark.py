"""Measure real process latency separately from the warmed native engine."""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

import manifold3d as m

from gridfinity_rebase.geometry import Grid, detect_grid, donor_base, replace_base
from gridfinity_rebase.presets import preset_base, rounded_prism
from gridfinity_rebase.stl import read_stl, write_stl

ROOT = Path(__file__).resolve().parents[1]


def synthetic_bin(nx, ny):
    grid = Grid(nx, ny, 0, 0, 0)
    base = preset_base("rebuilt", grid, 7)
    body = rounded_prism(nx * 42 - 0.5, ny * 42 - 0.5, 3.75, 7, 28)
    body = body.translate(((nx - 1) * 21, (ny - 1) * 21, 0))
    cavity = m.Manifold.cube((nx * 42 - 4.5, ny * 42 - 4.5, 28)).translate(
        (-18.75, -18.75, 8)
    )
    return (base + body) - cavity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    results = []
    with tempfile.TemporaryDirectory(prefix="gridfinity-bench-") as folder:
        folder = Path(folder)
        example = ROOT / "tmp" / "test.stl"
        if not example.exists():
            example = folder / "1x1.stl"
            write_stl(synthetic_bin(1, 1), example)
        donor = folder / "donor.stl"
        write_stl(synthetic_bin(1, 1), donor)
        large = folder / "6x6.stl"
        write_stl(synthetic_bin(6, 6), large)
        scenarios = [
            ("example/" + preset, example, ["--preset", preset])
            for preset in (
                "plain",
                "rebuilt",
                "rebuilt-screws",
                "refined",
                "press-fit",
            )
        ]
        scenarios.extend(
            [
                ("example/donor", example, ["--base", str(donor)]),
                ("6x6/refined", large, ["--preset", "refined"]),
            ]
        )
        for name, source, option in scenarios:
            process_times, engine_times = [], []
            output = folder / "result.stl"
            for _ in range(args.runs):
                start = perf_counter()
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "gridfinity_rebase",
                        "rebase",
                        str(source),
                        *option,
                        "-o",
                        str(output),
                        "--overwrite",
                        "--json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                process_times.append((perf_counter() - start) * 1000)
                start = perf_counter()
                solid = read_stl(source)
                grid = detect_grid(solid)
                if option[0] == "--preset":
                    base = preset_base(option[1], grid)
                else:
                    other = read_stl(option[1])
                    base = donor_base(other, detect_grid(other), grid, 4.75)
                result = replace_base(solid, base, grid)
                write_stl(result, output, overwrite=True)
                engine_times.append((perf_counter() - start) * 1000)
            results.append(
                {
                    "scenario": name,
                    "input_triangles": solid.num_tri(),
                    "process_median_ms": round(statistics.median(process_times), 2),
                    "process_min_ms": round(min(process_times), 2),
                    "process_max_ms": round(max(process_times), 2),
                    "warm_engine_median_ms": round(statistics.median(engine_times), 2),
                }
            )
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runs": args.runs,
        "results": results,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['platform']}, Python {report['python']}, {args.runs} runs/scenario"
        )
        print(
            f"{'Scenario':24} {'Triangles':>10} {'Process median':>16} {'Warm engine':>14}"
        )
        for row in results:
            print(
                f"{row['scenario']:24} {row['input_triangles']:10,} {row['process_median_ms']:13.2f} ms {row['warm_engine_median_ms']:11.2f} ms"
            )


if __name__ == "__main__":
    main()
