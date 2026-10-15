# README graphics

Each PNG contains one model or one close-up, without embedded text. The main
README places the images in tables with descriptions and the corresponding CLI
options. Clicking a thumbnail opens the full-size image.
The `thumbnails/` directory contains 260 px previews, so the README can use
standard Markdown image links without HTML sizing attributes.

The `base-*-2x3.png` images show the underside of the same synthetic 2×3 example
bin, using `generate_base()` and the CLI's resolved geometry options. They use
the same body, camera, orthographic scale and lighting. The `detail-*.png` images
show crops of those same models. Magnification varies between details.

The four preset images are `base-plain-2x3.png`,
`base-magnet-holes-2x3.png`, `base-rebuilt-2x3.png` and
`base-press-fit-2x3.png`. `refined` shares the `rebuilt` image because it is
an alias. Other base images illustrate combinations of geometry flags,
such as `rebuilt` with `--screws`.
The `detail-magnet-holes.png` and `detail-crush-ribs.png` close-ups show
the difference between smooth magnet pockets and `press-fit`.

The `detail-segments-{32,64,256}.png` images compare a central threaded
hole in a generated 1×1 base at three curve resolutions. All three use the same
camera, scale and lighting. Only the base's segment count changes.

Regenerate from the repository root:

```sh
uv run --with pillow python scripts/render_readme.py
```

Regenerate only the three resolution comparisons and their thumbnails:

```sh
uv run --with pillow python scripts/render_readme.py --segments-only
```

The renderer uses NumPy and Pillow with a triangle depth buffer. It needs no
display, GPU or external CAD renderer. The command installs Pillow as a temporary
dependency. Preset and geometry option illustrations use 256 segments by default
for close-ups, independently of the CLI's default of 64. The resolution
comparisons always use 32, 64 and 256, regardless of the renderer's `--segments`
argument. Edit descriptions and options in the README.

The shared example body is 21 mm high, with a cavity starting at 8 mm. Its base
extends to 7 mm. The body has no stacking lip because these illustrations
focus on the feet and mounting options.
