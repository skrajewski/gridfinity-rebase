# Presets and sources

Presets change the bin feet that fit into Gridfinity sockets.
Baseplates, such as Clickfinity, are separate parts. Replacing a bin's feet
does not change the plate underneath it.

Sources were reviewed on October 11, 2026. Rebuilt had around 2,300 GitHub
stars at the time. [Vector76](https://github.com/vector76/gridfinity_openscad)
describes its implementation as a recreation of the original with optional
magnet pockets and screw holes. The star count does not establish a popularity
ranking for bin feet.

| Preset | Geometry |
| --- | --- |
| `plain` | Standard profile without magnet pockets or screw holes. |
| `magnet-holes` | Smooth bottom-loading Ø6.5 mm magnet pockets, 2.4 mm deep, without crush ribs. |
| `rebuilt` | Side-loading magnet pockets with a floor and removal slot, arranged in a fan pattern with one opening per edge of the foot. |
| `press-fit` | Bottom-loading pockets with eight crush ribs for press-fitting magnets. |
| `refined` | An alias for `rebuilt`, with identical side-loading magnet geometry. |

`press-fit` creates the same bottom-loading pockets as
`--preset magnet-holes --crush-ribs`. Each pocket has eight ribs to grip the magnet.

`rebuilt` and `refined` use the same Rebuilt/Refined side-pocket geometry:
5.86 mm wide, 2.1 mm high, with a 0.4 mm floor. Add `--screws` to any
preset to include Ø3 mm screw bores.

All side-loading pockets default to 2.1 mm high. This matches the measured
Perplexing Labs reference `gf-rebuilt-bin-1x1x6-s1x1-Standard-42ae2.stl`.
The pinned upstream version uses a 1.9 mm height, which leaves
0.1 mm vertical interference for a 2 mm thick magnet. The default
applies to `rebuilt`, `refined` and `--magnets side`.
Use an explicit height to reproduce the previous geometry:

```sh
gridfinity-rebase bin.stl --preset rebuilt
gridfinity-rebase bin.stl --preset rebuilt --side-pocket-height 1.9
```

The pocket remains 5.86 mm wide with a 0.4 mm floor. Its roof is 2.5 mm above
the foot bottom. The removal slit reaches the same roof.
The 5.86 mm width still squeezes a nominal 6 mm magnet horizontally.
The vertical clearance does not guarantee a fit for every print.

## Independent geometry options

A preset is a group of geometry settings. The CLI starts with the `plain`
defaults, applies the selected preset, then applies explicit flags. Running
`rebase` without a preset or donor generates a `plain` base.

- `--magnets none|side|bottom` selects the magnet pocket style.
- `--side-pocket-height MM` sets the side-pocket height, independently
  of nominal magnet thickness. It requires side pockets and must be positive,
  finite and below 4.35 mm. This limit leaves material above the pocket in the foot.
- `--screws` and `--no-screws` enable or disable Ø3 mm screw bores,
  independently of magnets. Their depth is the cut height, up to 7 mm.
- `--crush-ribs` and `--no-crush-ribs` control ribs in bottom-loading pockets.
- `--only-corners` limits magnet pockets and Ø3 mm screw bores to the four
  outer corners of the whole bin, regardless of grid size. It applies to
  side-loading pockets and their removal slots, and to bottom-loading pockets
  with or without ribs. A 1×1 bin keeps all four holes. 1×N and N×1 grids
  keep two at each end.
- `--thumbscrew` and `--no-thumbscrew` control the central threaded hole.

Omitted flags keep the preset's settings. `magnet-holes` and `--magnets bottom`
without a preset generate smooth Ø6.5 mm pockets, 2.4 mm deep. Enabling ribs produces
`press-fit` geometry, with eight ribs and a diameter range of 5.9 to 6.5 mm.
Explicit `--crush-ribs` requires `--magnets bottom`. Changing a preset's
magnet style to `none` or `side` clears inherited ribs. Explicitly enabling
ribs with either style produces an error.

```sh
# Create screw bores without magnet pockets.
gridfinity-rebase bin.stl --screws

# Create side-loading magnet pockets and screw bores.
gridfinity-rebase bin.stl --magnets side --screws

# Create ribbed bottom-loading pockets and screw bores.
gridfinity-rebase bin.stl --preset press-fit --screws

# Place magnet pockets and screw bores only at the four outer corners of the bin.
gridfinity-rebase bin.stl --preset rebuilt --screws --only-corners

# Create bottom-loading pockets without ribs.
gridfinity-rebase bin.stl --preset magnet-holes

# Override a preset setting.
gridfinity-rebase bin.stl --preset press-fit --no-crush-ribs
```

Unmodified presets use `bin-rebased-PRESET.stl`. To reproduce the earlier
1.9 mm side-pocket height, use `--side-pocket-height 1.9`.
The CLI gives modified configurations a descriptive filename, such as
`bin-rebased-screws.stl` or `bin-rebased-magnets-bottom-crush-ribs-screws.stl`.
The JSON report includes a `geometry` object with the resolved `magnets`,
`screws`, `crush_ribs`, `thumbscrew` and `only_corners` settings. The `base`
field identifies the starting preset or donor path. The default preset is `plain`.
The `geometry.side_pocket_height_mm` field reports the effective height
or `null` without side pockets. The default height is 2.1 mm.
A custom height appears in the output filename.

`--only-corners` selects hole positions without enabling magnets or screws
by itself. The CLI appends `-only-corners` to the output filename, for example,
`bin-rebased-magnets-side-screws-only-corners.stl`. Central `--thumbscrew` holes
still appear in every foot.

With `--base`, the CLI copies the donor geometry and rejects all explicit
geometry flags, including flags that disable an option. The `geometry` field is `null`.

## Side-loading pockets and the central hole

The CLI rotates each foot's four pockets by 0°, 90°, 180° and 270°,
following Rebuilt's `_base_holes()`. The opening directions use local XY coordinates:

- The pocket at X = +13, Y = +13 opens toward +X.
- The pocket at X = −13, Y = +13 opens toward +Y.
- The pocket at X = −13, Y = −13 opens toward −X.
- The pocket at X = +13, Y = −13 opens toward −Y.

Each pocket opens onto one of the two nearest edges of its foot.
The same arrangement repeats across the grid. The removal slot rotates
with its pocket. This keeps openings in adjacent feet from facing each other
along the same axis.

`--thumbscrew` adds a central, right-handed M15×1.5 threaded hole to every
foot of a generated base. It matches the Gridfinity Refined implementation in
Rebuilt. To combine it with side-loading magnet pockets:

```sh
gridfinity-rebase bin.stl --preset refined --thumbscrew
```

The hole is 4.75 mm deep and ends at the top of the foot profile.
The bridge above remains solid. The hole's geometry follows `_base_thumbscrew()` and
`ScrewThread()`. The nominal thread is M15×1.5 with a 60° tooth angle.
The tolerance parameter is 0.4 mm. A 15.65 mm tool diameter and 0.1 mm shrinkage
correction give a maximum hole diameter of 15.75 mm. `--segments` sets the thread
resolution along with the other curves. You need a compatible baseplate and
Refined thumbscrew. The CLI generates only the hole.

The option also works without `--preset`. With `--base`, the CLI copies donor
holes unchanged. For an otherwise unmodified preset, the output filename
is `bin-rebased-PRESET-thumbscrew.stl`. The report's top-level `thumbscrew`
field is `true` or `false` for generated bases and `null` for donors, because
the tool does not identify a donor's mounting style.

Preset names identify specific configurations in this tool. The CLI does not
expose other upstream Customizer options. All presets preserve the same mating
profile for the baseplate. The CLI generates them locally, without downloading
STL files or running OpenSCAD.

Technical sources, pinned to revision `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [Rebuilt standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): mating profile, grid, radii and hole dimensions.
- [Rebuilt gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): Refined side-loading pockets and press-fit crush ribs.
- [Rebuilt base.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/base.scad): the four-pocket fan arrangement in `_base_holes()` and the `_base_thumbscrew()` thread.
- [threads-scad threads.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/external/threads-scad/threads.scad): `ScrewThread()` profile and mesh by Ryan A. Colyer, released under CC0.
- [Gridfinity Refined, grizzie17](https://www.printables.com/model/413761-gridfinity-refined): the project credited by Rebuilt as the source of Refined.
- [Gridfinity catalog](https://github.com/jeffbarr/gridfinity-catalog): a list of Gridfinity projects, including baseplates.

See the [README](../README.md#acknowledgements) for attribution and
[LICENSE](../LICENSE) for the MIT license and copyright notices.
