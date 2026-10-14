# Gridfinity Rebase

Fast CLI for replacing the base of a standard Gridfinity bin STL with configurable, offline geometry or a base copied from another STL. Powered by the native Manifold geometry engine.

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000)](https://buymeacoffee.com/skrajewski)

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/). From this repository:

```sh
uv tool install .
```

## Usage

Run `gridfinity-rebase` without arguments to display help.

```sh
# Use a preset → bin-rebased-rebuilt.stl
gridfinity-rebase rebase bin.stl --preset rebuilt

# Screw holes without magnet pockets → bin-rebased-screws.stl
gridfinity-rebase rebase bin.stl --screws

# Add screw holes to bottom-loading press-fit pockets
gridfinity-rebase rebase bin.stl --preset press-fit --screws

# Magnet and screw holes only at the four outer corners of the whole bin
gridfinity-rebase rebase bin.stl --preset rebuilt-screws --only-corners

# Side-loading magnet pockets + M15x1.5 thumbscrew → bin-rebased-rebuilt-thumbscrew.stl
gridfinity-rebase rebase bin.stl --preset rebuilt --thumbscrew

# Copy a base from another bin
gridfinity-rebase rebase bin.stl --base donor.stl -o result.stl

# Inspect a model or list presets
gridfinity-rebase inspect bin.stl
gridfinity-rebase presets
```

## Presets

Available presets: `plain`, `rebuilt`, `rebuilt-screws`, `side-2mm` and `press-fit`.
All side-loading pockets default to 2.1 mm high, including `rebuilt`,
`rebuilt-screws`, `refined`, `side-2mm` and `--magnets side`. This matches the
measured generator reference for 2 mm thick magnets. The pocket width remains
5.86 mm. Use `--side-pocket-height 1.9` to request the previous upstream height.

Alias: `standard` → `plain`.

Presets are shortcuts to geometry settings. Start from `plain` by default,
or select a preset and override individual settings:

- `--magnets none|side|bottom`: no magnet pockets, side-loading pockets, or bottom-loading pockets.
- `--screws` / `--no-screws`: enable or disable 3 mm screw bores.
- `--crush-ribs` / `--no-crush-ribs`: enable or disable ribs in bottom-loading pockets.
- `--only-corners`: limit magnet pockets and 3 mm screw bores to the four outer corners of the whole bin, regardless of grid size. A 1×1 bin keeps all four holes; central `--thumbscrew` holes still appear in every foot.
- `--thumbscrew` / `--no-thumbscrew`: enable or disable the central threaded hole.

Explicit flags override the preset; omitted flags keep its settings.
For example, `--preset rebuilt-screws --no-screws` keeps only the side-loading
magnet pockets. `--magnets bottom` alone produces smooth 6.5 × 2.4 mm pockets;
add `--crush-ribs` for a press fit. Ribs require bottom-loading pockets.
Changing a preset's magnet style to `none` or `side` clears inherited ribs.
`--only-corners` changes placement without enabling magnets or screws by itself.
Its output filename ends with `-only-corners.stl`, e.g.
`bin-rebased-rebuilt-screws-only-corners.stl`.

Add `--thumbscrew` with or without a preset for a central M15x1.5 threaded hole
in every foot, matching Rebuilt's 4.75 mm depth and clearance. The solid bridge
above the foot is preserved. Requires a compatible
baseplate and thumbscrew. Donor bases retain their own geometry; all explicit
geometry flags, including disabling flags, are rejected with `--base`.

The same 2×3 example bin, viewed from underneath. Click a preview for the full-size image.
Append the options in each row to `gridfinity-rebase rebase bin.stl`.

| Preview | Description | Options |
| --- | --- | --- |
| [![Plain 2×3 bin base](docs/images/thumbnails/base-plain-2x3.png)](docs/images/base-plain-2x3.png) | **Plain**: Standard feet without magnet pockets or screw holes. | `--preset plain` |
| [![2×3 bin base with side-loading magnet pockets](docs/images/thumbnails/base-rebuilt-2x3.png)](docs/images/base-rebuilt-2x3.png) | **Side-loading magnets**: Four pockets per foot, in a fan pattern with one opening per edge. Small underside slots allow magnet removal. | `--preset rebuilt` |
| [![2×3 bin base with side-loading magnet pockets and screw bores](docs/images/thumbnails/base-rebuilt-screws-2x3.png)](docs/images/base-rebuilt-screws-2x3.png) | **Side-loading magnets + screws**: The same side pockets, with an additional Ø3 mm screw bore at each pocket. | `--preset rebuilt-screws` |
| [![2×3 bin base with ribbed bottom-loading magnet pockets](docs/images/thumbnails/base-press-fit-2x3.png)](docs/images/base-press-fit-2x3.png) | **Press-fit magnets**: Four bottom-loading pockets per foot, each with eight crush ribs. | `--preset press-fit` |
| [![2×3 bin base with screw bores only](docs/images/thumbnails/base-screws-2x3.png)](docs/images/base-screws-2x3.png) | **Screws only**: Four Ø3 mm screw bores per foot, without magnet pockets. | `--screws` |
| [![2×3 bin base with smooth bottom-loading magnet pockets](docs/images/thumbnails/base-magnets-bottom-2x3.png)](docs/images/base-magnets-bottom-2x3.png) | **Smooth bottom pockets**: Four Ø6.5 mm magnet pockets per foot, 2.4 mm deep, without crush ribs. | `--magnets bottom` |
| [![2×3 bin base with press-fit magnet pockets and screw bores](docs/images/thumbnails/base-press-fit-screws-2x3.png)](docs/images/base-press-fit-screws-2x3.png) | **Press-fit magnets + screws**: Bottom-loading pockets with crush ribs and screw bores in their floors. | `--preset press-fit --screws` |
| [![2×3 bin base with side-loading magnet pockets and central threads](docs/images/thumbnails/base-rebuilt-thumbscrew-2x3.png)](docs/images/base-rebuilt-thumbscrew-2x3.png) | **Side magnets + thumbscrew**: Side-loading pockets and a central M15×1.5 threaded hole in every foot. | `--preset rebuilt --thumbscrew` |
| [![2×3 bin base with magnet pockets only at the four outer corners](docs/images/thumbnails/base-rebuilt-only-corners-2x3.png)](docs/images/base-rebuilt-only-corners-2x3.png) | **Magnets at outer corners**: Only four side-loading pockets across the whole bin, rather than 24. | `--preset rebuilt --only-corners` |
| [![2×3 bin base with side-loading magnet pockets, screw bores and central threads](docs/images/thumbnails/base-rebuilt-screws-thumbscrew-2x3.png)](docs/images/base-rebuilt-screws-thumbscrew-2x3.png) | **Magnets, screws + thumbscrew**: 24 side pockets, 24 screw bores and six central threaded holes. | `--preset rebuilt-screws --thumbscrew` |
| [![2×3 bin base with four outer-corner magnet pockets and screw bores, plus six central threads](docs/images/thumbnails/base-rebuilt-screws-thumbscrew-only-corners-2x3.png)](docs/images/base-rebuilt-screws-thumbscrew-only-corners-2x3.png) | **Outer corners + thumbscrew**: Four side pockets and four screw bores across the whole bin; the central thread remains in all six feet. | `--preset rebuilt-screws --thumbscrew --only-corners` |

### Close-ups

| Preview | Description | Options |
| --- | --- | --- |
| [![Close-up of a side-loading magnet pocket](docs/images/thumbnails/detail-side-loading.png)](docs/images/detail-side-loading.png) | **Side entry**: The magnet slides through the opening in the edge of the foot. | `--preset rebuilt` |
| [![Close-up of a smooth bottom magnet pocket](docs/images/thumbnails/detail-magnets-bottom.png)](docs/images/detail-magnets-bottom.png) | **Smooth pocket**: A circular recess loaded from underneath. | `--magnets bottom` |
| [![Close-up of the eight crush ribs in a magnet pocket](docs/images/thumbnails/detail-crush-ribs.png)](docs/images/detail-crush-ribs.png) | **Crush ribs**: Eight ribs narrow the pocket for a press fit. | `--preset press-fit` |
| [![Close-up of a central M15×1.5 threaded hole](docs/images/thumbnails/detail-thumbscrew.png)](docs/images/detail-thumbscrew.png) | **Central thread**: M15×1.5, 4.75 mm deep, with a solid bridge above. | `--preset rebuilt --thumbscrew` |

Images are rendered from the CLI's native geometry. [Regenerate the graphics](docs/images/README.md).

See [curve resolution (`--segments`)](docs/segments.md) for settings and visual comparisons.

## Key details

- Supports standard rectangular Gridfinity bins on a 42 mm grid. STL units must be **mm**, with feet at the bottom and **Z pointing up**.
- Automatically detects the base and cut height, preserving the bin interior and geometry above the cut. Invalid meshes, incompatible bases and ambiguous models are rejected.
- Donors can match the input grid, have swapped X/Y dimensions, or be 1×1 and tiled across the input.
- Default output: existing preset filenames are preserved (`bin-rebased-PRESET[-thumbscrew].stl`). Modified settings use a descriptive suffix, e.g. `bin-rebased-magnets-bottom-crush-ribs-screws.stl`; donors use `bin-rebased.stl`. Use `-o` to choose a filename and `--overwrite` to replace an existing output.
- JSON reports include the resolved `geometry` settings. `base` identifies the starting preset (default: `plain`) or donor path; donor geometry is reported as `null`.
- `--base-height MM` overrides automatic detection for custom models and replaces everything below that height. Minimum: 4.75 mm.

Run `gridfinity-rebase rebase --help` for all options.

## Performance

Run the self-contained benchmark from the repository root:

```sh
uv run --locked --python 3.11 python scripts/benchmark.py --runs 5
```

All test models are generated locally; no example STL downloads are required.
See [benchmark instructions, methodology and reference results](docs/performance.md)
for JSON output and environment details.

## License and attribution

The [MIT license](LICENSE) covers this CLI and its adapted preset implementation.
Processing a model does not replace its existing license or attribution
requirements. When sharing a rebased STL, preserve applicable notices and
comply with the licenses of the input model and any donor geometry.

Preset geometry is adapted from the MIT-licensed [Gridfinity Rebuilt implementation](https://github.com/kennetek/gridfinity-rebuilt-openscad/tree/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd)
by Kenneth Hodson, based on Gridfinity by Zack Freedman. Rebuilt credits
[Gridfinity Refined](https://www.printables.com/model/413761-gridfinity-refined)
by grizzie17 as the source of its side-loading magnet pockets.

Rebuilt source files at revision `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): mating profile, grid, radii and hole dimensions.
- [gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): side-loading magnet pockets and crush ribs.
- [base.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/base.scad): fan arrangement of the four pockets and the central threaded hole.

The native thumbscrew thread tessellation derives from `ScrewThread()` in
[threads-scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/external/threads-scad/threads.scad),
created 2016–2017 by Ryan A. Colyer and released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
