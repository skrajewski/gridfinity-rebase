# README graphics

Each PNG contains one model or one close-up, without embedded text. The main
README places the images in tables with descriptions and the corresponding CLI
options. Clicking a thumbnail opens the full-size image.
The `thumbnails/` directory contains 260 px previews, so the README can use
standard Markdown image links without HTML sizing attributes.

The `base-*-2x3.png` images show the underside of the same synthetic 2×3 example
bin, using `generate_base()` and the CLI's resolved geometry options. They use
the same body, camera, orthographic scale and lighting. The `detail-*.png` images
show crops of those same models; magnification varies between features.
The `detail-segments-{32,64,256}.png` images instead compare a central threaded
hole in a generated 1×1 base at three curve resolutions. All three use the same
camera, scale and lighting; only the base's segment count changes.

Regenerate from the repository root:

```sh
uv run --with pillow python scripts/render_readme.py
```

Regenerate only the three resolution comparisons and their thumbnails:

```sh
uv run --with pillow python scripts/render_readme.py --segments-only
```

The renderer uses NumPy and Pillow with a triangle depth buffer; it needs no
display, GPU or external CAD renderer. Pillow is a temporary dependency of this
command. Preset and feature illustrations use 256 segments by default for legible
close-ups, independent of the CLI's default tessellation. The resolution
comparisons always use 32, 64 and 256, regardless of the renderer's `--segments`
argument. Descriptions and options are kept in the README rather
than baked into the images.

The shared example body is 21 mm high, with a cavity starting at 8 mm. Its base
is generated up to 7 mm. The body has no stacking lip because these illustrations
focus on the feet and mounting options.
