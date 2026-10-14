# Presets and sources

Presets apply to the **bin feet** that fit into Gridfinity sockets.
Baseplates (such as Clickfinity) are separate parts; replacing a bin's feet
does not change the plate underneath it.

Sources were reviewed on October 11, 2026. Rebuilt is a widely used
implementation (around 2,300 GitHub stars at the time of the review), while
[Vector76](https://github.com/vector76/gridfinity_openscad) describes a
recreation of the original with optional magnet pockets and screw holes.
There is no reliable global popularity ranking for bin feet. The selected
presets represent established variants documented by their creators,
without claiming a download ranking.

| Preset | Geometry |
| --- | --- |
| `plain` | Standard profile without magnet pockets or screw holes. |
| `rebuilt` | Side-loading magnet pockets with a floor and removal slot, arranged in a fan pattern with one opening per edge of the foot. |
| `rebuilt-screws` | Same as `rebuilt`, with additional screw bores extending to the cut height, up to 7 mm. |
| `side-2mm` | Side-loading pockets, 5.86 mm wide and 2.1 mm high above a 0.4 mm floor, matching the measured Perplexing Labs bin. |
| `press-fit` | Bottom-loading pockets with eight crush ribs for press-fitting magnets. |
| `refined` | Alias of `rebuilt`: identical side-loading magnet geometry. |
| `standard` | Alias of `plain`: identical geometry without holes. |

`rebuilt` and `refined` use the same Rebuilt/Refined side-pocket geometry:
5.86 mm wide, 2.1 mm high, with a 0.4 mm floor. `rebuilt-screws` adds screw
bores to those pockets. The older names `refined` and `standard` remain
supported as aliases.

All side-loading pockets now default to 2.1 mm high, matching the measured
Perplexing Labs reference `gf-rebuilt-bin-1x1x6-s1x1-Standard-42ae2.stl`.
This intentionally differs from the pinned upstream's 1.9 mm height, which
implies 0.1 mm vertical interference for a 2 mm thick magnet. The default
applies to `rebuilt`, `rebuilt-screws`, `refined`, `side-2mm` and `--magnets side`.
Use an explicit height to reproduce the previous geometry:

```sh
gridfinity-rebase rebase bin.stl --preset rebuilt
gridfinity-rebase rebase bin.stl --preset rebuilt --side-pocket-height 1.9
```

The default leaves the 5.86 mm pocket width and 0.4 mm floor unchanged; the
roof is at 2.5 mm above the foot bottom. The removal slit reaches the same roof.
`side-2mm` still squeezes a nominal 6 mm magnet horizontally. Its name describes
the intended magnet thickness, not a guarantee of fit for every print.

## Independent geometry options

A preset is a shortcut to a group of settings. Settings are resolved in this
order: defaults (`plain`), the selected preset, then explicit flags. Running
`rebase` without a preset or donor generates a `plain` base.

- `--magnets none|side|bottom` selects the magnet pocket style.
- `--side-pocket-height MM` sets the actual side-pocket height, independently
  of nominal magnet thickness. It requires side pockets and must be positive,
  finite and below 4.35 mm, retaining material above the pocket in the foot.
- `--screws` and `--no-screws` enable or disable Ø3 mm screw bores,
  independently of magnets. Their depth is the cut height, up to 7 mm.
- `--crush-ribs` and `--no-crush-ribs` control ribs in bottom-loading pockets.
- `--only-corners` limits magnet pockets and Ø3 mm screw bores to the four
  outer corners of the whole bin, regardless of grid size. It applies to
  side-loading pockets (including removal slots) and bottom-loading pockets,
  with or without ribs. A 1×1 bin keeps all four holes; 1×N and N×1 grids
  keep two at each end.
- `--thumbscrew` and `--no-thumbscrew` control the central threaded hole.

Omitted flags keep the preset's settings. `--magnets bottom` without a preset
generates smooth Ø6.5 mm pockets, 2.4 mm deep. Enabling ribs produces
`press-fit` geometry: eight ribs with a diameter range of 5.9–6.5 mm.
Explicit `--crush-ribs` requires `--magnets bottom`. Changing a preset's
magnet style to `none` or `side` clears inherited ribs; explicitly enabling
ribs with either style produces an error.

```sh
# Screws only
gridfinity-rebase rebase bin.stl --screws

# Side-loading magnet pockets and screw bores
gridfinity-rebase rebase bin.stl --magnets side --screws

# Ribbed bottom-loading pockets and screw bores
gridfinity-rebase rebase bin.stl --preset press-fit --screws

# Magnets and screws only at the four outer corners of the whole bin
gridfinity-rebase rebase bin.stl --preset rebuilt-screws --only-corners

# Bottom-loading pockets without ribs
gridfinity-rebase rebase bin.stl --magnets bottom --no-crush-ribs

# Override a preset setting
gridfinity-rebase rebase bin.stl --preset rebuilt-screws --no-screws
```

Existing preset output filenames are retained; side-pocket height has changed
from 1.9 to 2.1 mm by default. Use the explicit height above for old geometry.
Modified configurations receive a descriptive filename, such as
`bin-rebased-screws.stl` or `bin-rebased-magnets-bottom-crush-ribs-screws.stl`.
The JSON report includes a `geometry` object with the resolved `magnets`,
`screws`, `crush_ribs`, `thumbscrew` and `only_corners` settings. The `base`
field identifies the starting preset (default: `plain`) or donor path.
The `geometry.side_pocket_height_mm` field reports the effective height
(2.1 mm by default), or `null` without
side pockets. A custom height appears in the output filename.

`--only-corners` selects hole positions without enabling magnets or screws
by itself. The output filename receives an `-only-corners` suffix, such as
`bin-rebased-rebuilt-screws-only-corners.stl`. Central `--thumbscrew` holes
still appear in every foot.

With `--base`, all explicit geometry flags, including disabling flags, are
rejected: the tool copies the donor geometry. The `geometry` field is `null`.

## Side-loading pockets and the central hole

Within each foot, the pockets are rotated by 0°, 90°, 180° and 270°,
following Rebuilt's `_base_holes()`. In local XY coordinates, the openings
point as follows: (+13, +13) → +X, (−13, +13) → +Y, (−13, −13) → −X,
(+13, −13) → −Y. Each pocket opens onto one of the two nearest edges of its
foot; the same arrangement repeats across the grid. The removal slot rotates
with its pocket. This keeps openings in adjacent feet from facing each other
along the same axis.

`--thumbscrew` adds a central, right-handed M15×1.5 threaded hole to every
foot of a generated base, matching the Gridfinity Refined implementation in
Rebuilt. For a base with side-loading magnets:

```sh
gridfinity-rebase rebase bin.stl --preset refined --thumbscrew
```

The hole is 4.75 mm deep and ends at the top of the foot profile; the bridge
above remains solid. Its geometry follows `_base_thumbscrew()` and
`ScrewThread()`: nominal M15×1.5, a 60° tooth angle, a 0.4 mm tolerance
parameter, a 15.65 mm tool diameter and a 0.1 mm shrinkage correction
(maximum hole diameter: 15.75 mm). `--segments` sets the thread resolution
along with the other curves. A compatible baseplate and Refined thumbscrew
are required; the CLI generates the hole, not those separate parts.

The option also works without `--preset`. With `--base`, donor holes are
copied unchanged. For an otherwise unmodified preset, the output filename
is `bin-rebased-PRESET-thumbscrew.stl`. The report's top-level `thumbscrew`
field is `true` or `false` for generated bases and `null` for donors, because
the tool does not identify a donor's mounting style.

Preset names identify specific configurations in this tool; other upstream
Customizer options are not exposed. All presets preserve the same mating
profile for the baseplate. They are generated locally, without downloading
STL files or running OpenSCAD.

Technical sources, pinned to revision `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [Rebuilt — standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): mating profile, grid, radii and hole dimensions.
- [Rebuilt — gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): Refined side-loading pockets and press-fit crush ribs.
- [Rebuilt — base.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/base.scad): the four-pocket fan arrangement in `_base_holes()` and the `_base_thumbscrew()` thread.
- [threads-scad — threads.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/external/threads-scad/threads.scad): `ScrewThread()` profile and mesh (Ryan A. Colyer, CC0).
- [Gridfinity Refined, grizzie17](https://www.printables.com/model/413761-gridfinity-refined): the project credited by Rebuilt as the source of Refined.
- [Gridfinity catalog](https://github.com/jeffbarr/gridfinity-catalog): an overview of the ecosystem, including baseplates.

Attribution: [README](../README.md#license-and-attribution). MIT license and
copyright notices: [LICENSE](../LICENSE).
