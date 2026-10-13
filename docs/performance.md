# Performance benchmark

## Reproduce locally

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/). Run from the
repository root. The commands below select Python 3.11 to match the reference
run and use `uv.lock` to pin dependency versions. `uv` installs the project and
its dependencies automatically on the first run.

```sh
# Human-readable results
uv run --locked --python 3.11 python scripts/benchmark.py --runs 5

# Machine-readable results, including individual timings and input hashes
uv run --locked --python 3.11 python scripts/benchmark.py --runs 5 --json > benchmark.local.json
```

No external STL files, OpenSCAD or local `tmp/` contents are needed. All input
models and outputs are created in a temporary directory and removed at the end.
Dependencies must be available locally or downloaded during initial setup;
the benchmark itself does not access the network.

The script always generates the same models using 64 curve segments:

- **1×1 input:** a synthetic bin with a `rebuilt` base, a 7 mm base height,
  a body extending to 28 mm and a cavity starting at 8 mm.
- **1×1 donor:** a separately saved copy of the same generated model, used
  to measure the donor-base path, including donor reading and validation.
- **6×6 input:** the same construction scaled to a 6×6 grid.

Both input bases have side-loading magnet pockets. The 1×1 input is rebased
with `plain`, `rebuilt`, `rebuilt-screws`, `refined`, `press-fit` and a donor;
the 6×6 input uses `refined`. `refined` is an alias of `rebuilt`, so differences
between their timings reflect measurement variation, not different geometry.
Input generation is outside the timed sections.

## Measurement method

Each scenario receives one complete, unmeasured CLI run and one unmeasured
engine run, followed by `--runs` measured pairs (default: 5). Timings use
`perf_counter()` and are reported in milliseconds.

- **Process:** wall-clock time for a fresh Python CLI subprocess, including
  startup, imports, input reading, validation, automatic base detection,
  replacement, STL writing and JSON reporting. Every measured process starts
  with a fresh in-memory geometry cache.
- **Warm engine:** input reading, validation, automatic base detection,
  replacement and STL writing in the benchmark's existing Python process.
  Libraries are already loaded and the single-foot geometry cache is warm.
  CLI argument parsing, process startup and report serialization are excluded.

Measurements alternate process then engine, using the same output path with
`--overwrite`. Files remain in the operating system's cache; neither path
measures cold disk I/O. The engine warm-up also primes any preset geometry
not already cached by input generation or previous scenarios.

The JSON report records the platform, architecture, logical CPU count, Python
and package versions, measurement time, segment count, warm-up count, input
SHA-256 hashes and triangle counts, all measured samples, process minima and
maxima, and both medians. Compare the input hashes and environment metadata
when comparing runs. Different dependency versions or platforms can change
mesh serialization and hashes even when the intended geometry is the same.

## Reference results

Measured on October 13, 2026, on macOS 26.2 arm64 (12 logical CPUs),
Python 3.11.14, Manifold 3.5.4 and NumPy 2.4.6. Each scenario ran 5 measured
times after the warm-ups described above.

| Scenario | Input triangles | Process median | Warm engine median |
| --- | ---: | ---: | ---: |
| 1x1/plain | 1894 | 94.51 ms | 12.46 ms |
| 1x1/rebuilt | 1894 | 94.41 ms | 14.64 ms |
| 1x1/rebuilt-screws | 1894 | 112.18 ms | 28.16 ms |
| 1x1/refined | 1894 | 87.83 ms | 14.14 ms |
| 1x1/press-fit | 1894 | 87.83 ms | 13.72 ms |
| 1x1/donor | 1894 | 89.76 ms | 18.54 ms |
| 6x6/refined | 58246 | 260.88 ms | 178.35 ms |

Full samples and metadata are in [benchmark.json](benchmark.json). These results
replace the earlier measurements that depended on an untracked local example
STL; the 1×1 input now has 1,894 triangles rather than 7,472, so those timings
are not directly comparable.

The procedure and inputs can be reproduced; exact elapsed times vary with
hardware, system load, power settings and filesystem caching. Larger grids
cost more as triangle and foot counts increase. The first invocation after
installation can take longer because of cold system caches and Python bytecode
cache creation; the unmeasured warm-ups exclude that work from these results.
