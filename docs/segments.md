# Curve resolution with `--segments`

`--segments N` sets the number of straight edges used to approximate curves
in the generated base. A circular hole uses N segments around its circumference.
Each rounded 90° corner uses N / 4 segments. The setting applies to the foot
profile, the rounded bridge above the feet, magnet pockets and their crush ribs,
screw bores and the central `--thumbscrew` thread. It is not the total number of
triangles in the model.

The default is 64. The CLI accepts multiples of 8 from 32 to 256,
such as 32, 64, 96, 128 or 256. Higher values make curved outlines and
surfaces smoother. They also add triangles, increase STL file sizes and usually
take longer to process. Doubling this value does not necessarily double the
final triangle count or processing time. Both also depend on the selected
geometry options, grid size and input mesh.

| Setting | Segments per 90° corner | When to use it |
| --- | --- | --- |
| `--segments 32` | 8 | Use for quick previews and smaller meshes. Facets are more visible, especially on the thread. |
| `--segments 64` | 16 | Start with this default for everyday models. |
| `--segments 128` | 32 | Use for finer curves when faceting is still noticeable at 64. |
| `--segments 256` | 64 | Use the maximum supported resolution for detailed close-ups and fine curved geometry. |

The three images below show the same M15×1.5 threaded hole from underneath,
with identical camera, magnification and lighting. Click to inspect the full-size
renders. Differences are easier to see there than in the thumbnails.

| 32 segments | 64 segments, the default | 256 segments |
| --- | --- | --- |
| [![Thread close-up at 32 segments, showing coarser facets](images/thumbnails/detail-segments-32.png)](images/detail-segments-32.png) | [![Thread close-up at the default 64 segments](images/thumbnails/detail-segments-64.png)](images/detail-segments-64.png) | [![Thread close-up at 256 segments, showing finer curves](images/thumbnails/detail-segments-256.png)](images/detail-segments-256.png) |

```sh
gridfinity-rebase bin.stl --preset rebuilt --thumbscrew --segments 128
```

This changes the number of straight edges used to approximate curves.
It keeps the nominal dimensions, thread pitch and configured clearances.
Coarse polygonal curves can still affect the fit of printed holes and threads.
A higher value alone does not guarantee a better fit. Printing accuracy also
affects the result. Only newly generated geometry uses this setting.
It does not smooth the retained input mesh and has no effect when the CLI
copies a donor base with `--base`.

`--segments` does not add a suffix to the output filename. Use `-o` with distinct
names to keep several resolutions for comparison.

