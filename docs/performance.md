# Performance benchmark

## Reproduce locally

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/), then run the commands
below from the repository root. They select Python 3.11 to match the reference
run and use `uv.lock` to pin dependency versions. `uv` installs the project and
its dependencies automatically on the first run.

```sh
# Print human-readable results.
uv run --locked --python 3.11 python scripts/benchmark.py --runs 5

# Write JSON results with individual timings and input hashes.
uv run --locked --python 3.11 python scripts/benchmark.py --runs 5 --json > benchmark.local.json
```

The benchmark generates all input models and outputs in a temporary directory,
then removes them at the end. You do not need external STL files, OpenSCAD or
local `tmp/` contents. Initial setup downloads any missing dependencies.
The benchmark itself does not access the network.

The script always generates the same models using 64 curve segments:

- The 1×1 input is a synthetic bin with a `rebuilt` base, a 7 mm base height,
  a body extending to 28 mm and a cavity starting at 8 mm.
- The 1×1 donor is a separate copy of the same generated model.
  The benchmark uses it to measure donor-base replacement, including donor
  reading and validation.
- The 6×6 input uses the same construction scaled to a 6×6 grid.

Both input bases have side-loading magnet pockets. The 1×1 input is rebased
with `plain`, `magnet-holes`, `rebuilt`, `press-fit` and a donor.
The 6×6 input uses `rebuilt`. The benchmark excludes input generation from
the timed sections.

## Measurement method

The benchmark starts each scenario with one unmeasured CLI run and one
unmeasured engine run. It then measures `--runs` pairs, with 5 pairs by default.
It uses `perf_counter()` and reports timings in milliseconds.

- The process measurement records wall-clock time for a fresh Python CLI
  subprocess, including startup, imports, input reading, validation, automatic base detection,
  replacement, STL writing and JSON reporting. Every measured process starts
  with a fresh in-memory geometry cache.
- The warm engine measurement covers input reading, validation, automatic base
  detection, replacement and STL writing in the benchmark's existing Python process.
  Libraries are already loaded and the single-foot geometry cache is warm.
  It excludes CLI argument parsing, process startup and report serialization.

The benchmark alternates process and engine measurements, using the same output
path with `--overwrite`. Files remain in the operating system's cache, so neither
timing includes cold disk I/O. The engine warm-up also primes any preset geometry
not already cached by input generation or previous scenarios.

The JSON report records the platform, architecture, logical CPU count, and Python
and package versions. It includes the measurement time, segment count, warm-up
count, and input SHA-256 hashes and triangle counts. It also records all measured
samples, process minima and maxima, and both medians. Compare the input hashes and environment metadata
when comparing runs. Different dependency versions or platforms can change
mesh serialization and hashes even when the intended geometry is the same.

## Reference results

The reference run took place on October 13, 2026, on macOS 26.2 arm64 with
12 logical CPUs, Python 3.11.14, Manifold 3.5.4 and NumPy 2.4.6.
Each scenario ran 5 measured times after the warm-ups described above.

| Scenario | Input triangles | Process median | Warm engine median |
| --- | ---: | ---: | ---: |
| 1x1/plain | 1894 | 94.51 ms | 12.46 ms |
| 1x1/rebuilt | 1894 | 94.41 ms | 14.64 ms |
| 1x1/rebuilt-screws | 1894 | 112.18 ms | 28.16 ms |
| 1x1/refined | 1894 | 87.83 ms | 14.14 ms |
| 1x1/press-fit | 1894 | 87.83 ms | 13.72 ms |
| 1x1/donor | 1894 | 89.76 ms | 18.54 ms |
| 6x6/refined | 58246 | 260.88 ms | 178.35 ms |

These historical results use the earlier preset catalog. The former
`rebuilt-screws` preset is now `--preset rebuilt --screws`. `refined` remains an
alias of `rebuilt`. The current benchmark covers the four presets above.
`magnet-holes` was not included in this reference run.

Full samples and metadata are in [benchmark.json](benchmark.json). These results
replace the earlier measurements that depended on an untracked local example
STL. The 1×1 input now has 1,894 triangles rather than 7,472, so those timings
are not directly comparable.

You can reproduce the procedure and inputs. Exact elapsed times vary with
hardware, system load, power settings and filesystem caching. Larger grids
take longer to process as triangle and foot counts increase. The first invocation
after installation can take longer because of cold system caches and Python
bytecode cache creation. The unmeasured warm-ups exclude that work from these results.
