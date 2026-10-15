"""Measure real process latency separately from the warmed native engine."""

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import manifold3d as m

from gridfinity_rebase.geometry import (
    Grid,
    detect_grid,
    detect_standard_base,
    donor_base,
    replace_base,
    validate_height,
)
from gridfinity_rebase.presets import preset_base, rounded_prism
from gridfinity_rebase.stl import read_stl, write_stl

SEGMENTS = 64


def synthetic_bin(nx, ny):
    grid = Grid(nx, ny, 0, 0, 0)
    base = preset_base("rebuilt", grid, 7, segments=SEGMENTS)
    body = rounded_prism(nx * 42 - 0.5, ny * 42 - 0.5, 3.75, 7, 28, segments=SEGMENTS)
    body = body.translate(((nx - 1) * 21, (ny - 1) * 21, 0))
    cavity = m.Manifold.cube((nx * 42 - 4.5, ny * 42 - 4.5, 28)).translate(
        (-18.75, -18.75, 8)
    )
    return (base + body) - cavity


def run_engine(source, option, output):
    solid = read_stl(source)
    grid = detect_grid(solid)
    height = detect_standard_base(solid, grid).height
    validate_height(solid, grid, height)
    if option[0] == "--preset":
        base = preset_base(option[1], grid, height, segments=SEGMENTS)
    else:
        other = read_stl(option[1])
        donor_grid = detect_grid(other)
        assert detect_standard_base(other, donor_grid).height >= height
        base = donor_base(other, donor_grid, grid, height)
    result = replace_base(solid, base, grid, height)
    write_stl(result, output, overwrite=True)


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
        example = folder / "1x1.stl"
        write_stl(synthetic_bin(1, 1), example)
        donor = folder / "donor.stl"
        write_stl(synthetic_bin(1, 1), donor)
        large = folder / "6x6.stl"
        write_stl(synthetic_bin(6, 6), large)
        inputs = {
            name: {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "triangles": read_stl(path).num_tri(),
            }
            for name, path in (("1x1", example), ("donor", donor), ("6x6", large))
        }
        scenarios = [
            ("1x1/" + preset, example, ["--preset", preset])
            for preset in (
                "plain",
                "magnet-holes",
                "rebuilt",
                "press-fit",
            )
        ]
        scenarios.extend(
            [
                ("1x1/donor", example, ["--base", str(donor)]),
                ("6x6/rebuilt", large, ["--preset", "rebuilt"]),
            ]
        )
        for name, source, option in scenarios:
            process_times, engine_times = [], []
            output = folder / "result.stl"
            command = [
                sys.executable,
                "-m",
                "gridfinity_rebase",
                "rebase",
                str(source),
                *option,
                "--segments",
                str(SEGMENTS),
                "-o",
                str(output),
                "--overwrite",
                "--json",
            ]
            # Exclude one complete warm-up of each path for every scenario.
            subprocess.run(command, check=True, capture_output=True, text=True)
            run_engine(source, option, output)
            for _ in range(args.runs):
                start = perf_counter()
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                process_times.append((perf_counter() - start) * 1000)
                start = perf_counter()
                run_engine(source, option, output)
                engine_times.append((perf_counter() - start) * 1000)
            results.append(
                {
                    "scenario": name,
                    "input_triangles": inputs[name.split("/")[0]]["triangles"],
                    "process_median_ms": round(statistics.median(process_times), 2),
                    "process_min_ms": round(min(process_times), 2),
                    "process_max_ms": round(max(process_times), 2),
                    "warm_engine_median_ms": round(statistics.median(engine_times), 2),
                    "process_samples_ms": process_times,
                    "warm_engine_samples_ms": engine_times,
                }
            )
    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "python": platform.python_version(),
        "dependencies": {
            name: version(name) for name in ("gridfinity-rebase", "manifold3d", "numpy")
        },
        "runs": args.runs,
        "warmups_per_scenario": 1,
        "segments": SEGMENTS,
        "inputs": inputs,
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
