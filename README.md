# Gridfinity Rebase

Fast CLI for replacing the base of a standard Gridfinity bin STL with an offline preset or a base copied from another STL. Powered by the native Manifold geometry engine.

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/). From this repository:

```sh
uv tool install .
```

## Usage

```sh
# Use a preset → bin-rebased-rebuilt.stl
gridfinity-rebase rebase bin.stl --preset rebuilt

# Copy a base from another bin
gridfinity-rebase rebase bin.stl --base donor.stl -o result.stl

# Inspect a model or list presets
gridfinity-rebase inspect bin.stl
gridfinity-rebase presets
```

## Presets

| Preset | Base |
| --- | --- |
| `plain` | No magnet or screw holes |
| `rebuilt` | Side-loading magnet pockets |
| `rebuilt-screws` | Side-loading magnet pockets and screw holes |
| `press-fit` | Bottom-loading magnet pockets with crush ribs |

Aliases: `refined` → `rebuilt`, `standard` → `plain`.

## Key details

- Supports standard rectangular Gridfinity bins on a 42 mm grid. STL units must be **mm**, with feet at the bottom and **Z pointing up**.
- Automatically detects the base and cut height, preserving the bin interior and geometry above the cut. Invalid meshes, incompatible bases and ambiguous models are rejected.
- Donors can match the input grid, have swapped X/Y dimensions, or be 1×1 and tiled across the input.
- Default output: `bin-rebased-PRESET.stl` for presets, `bin-rebased.stl` for donors. Use `-o` to choose a filename and `--overwrite` to replace an existing output.
- `--base-height MM` overrides automatic detection for custom models and replaces everything below that height. Minimum: 4.75 mm.

More: [preset details](docs/presets.md) · [benchmarks](docs/performance.md) · `gridfinity-rebase --help`

MIT. See [third-party notices](THIRD_PARTY_NOTICES.md).
