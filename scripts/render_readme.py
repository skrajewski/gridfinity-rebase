"""Render README comparisons from the CLI's native geometry, without a GPU.

Run from the repository root:
    uv run --with pillow python scripts/render_readme.py

Only documentation PNGs are written. Pillow is a temporary rendering dependency;
the CLI's runtime dependencies are unchanged. Views use orthographic projection,
a triangle depth buffer, and screen-space shading to make recesses readable.
"""

import argparse
from pathlib import Path

import manifold3d as m
import numpy as np
from PIL import Image, ImageFilter

from gridfinity_rebase.catalog import resolve_options
from gridfinity_rebase.geometry import Grid, detect_grid
from gridfinity_rebase.options import BaseOptions
from gridfinity_rebase.presets import generate_base, rounded_prism

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = "#f4f6f5"
MODEL_COLOR = (255, 150, 28)


def example_bin(options, segments):
    """One identical 2x3 example body for all replacement bases (mm, Z up)."""
    grid = Grid(2, 3, -21, -42, 0)
    base = generate_base(options, grid, height=7, segments=segments)
    wall = rounded_prism(83.5, 125.5, 3.75, 7, 21, segments)
    cavity = rounded_prism(79.5, 121.5, 1.75, 8, 22, segments)
    solid = (base + wall) - cavity
    if solid.status() != m.Error.NoError or len(solid.decompose()) != 1:
        raise RuntimeError("Example bin must be a single valid solid")
    detected = detect_grid(solid)
    if (detected.nx, detected.ny) != (2, 3):
        raise RuntimeError("Example bin must have a 2x3 Gridfinity base")
    return solid


def render(
    solid, size=(720, 520), *, azimuth=-32, elevation=-58, target=None, span=None
):
    """Rasterize visible native triangles, resolving occlusion per pixel."""
    ss = 2
    width, height = (value * ss for value in size)
    mesh = solid.to_mesh64()
    vertices = np.asarray(mesh.vert_properties)[:, :3]
    faces = np.asarray(mesh.tri_verts)
    triangles = vertices[faces]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    length = np.linalg.norm(normals, axis=1)
    normals /= np.maximum(length[:, None], 1e-15)
    a, e = np.radians([azimuth, elevation])
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.cross([0, 0, 1], eye)
    right /= np.linalg.norm(right)
    up = np.cross(eye, right)
    center = (
        (vertices.min(axis=0) + vertices.max(axis=0)) / 2
        if target is None
        else np.array(target)
    )
    vertices = vertices - center
    projected = np.column_stack((vertices @ right, -vertices @ up))
    if span is None:
        low, high = projected.min(axis=0), projected.max(axis=0)
        scale = min(
            (width - 72 * ss) / (high[0] - low[0]),
            (height - 62 * ss) / (high[1] - low[1]),
        )
        projected -= (low + high) / 2
    else:
        scale = width / span
    projected = projected * scale + [width / 2, height / 2]
    depths = vertices @ eye
    zbuffer = np.full((height, width), -np.inf, dtype=np.float32)
    brightness = np.zeros((height, width), dtype=np.float32)
    recess = np.zeros((height, width), dtype=np.float32)
    slope_x = np.zeros((height, width), dtype=np.float32)
    slope_y = np.zeros((height, width), dtype=np.float32)
    light = eye - 0.45 * right + 0.35 * up
    light /= np.linalg.norm(light)
    for index in np.flatnonzero((normals @ eye > 1e-8) & (length > 1e-12)):
        p = projected[faces[index]]
        low = np.maximum(np.floor(p.min(axis=0)).astype(int), [0, 0])
        high = np.minimum(np.ceil(p.max(axis=0)).astype(int), [width - 1, height - 1])
        if np.any(high < low):
            continue
        denominator = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (
            p[2, 0] - p[1, 0]
        ) * (p[0, 1] - p[2, 1])
        if abs(denominator) < 1e-8:
            continue
        xx, yy = np.meshgrid(
            np.arange(low[0], high[0] + 1) + 0.5, np.arange(low[1], high[1] + 1) + 0.5
        )
        ba = (
            (p[1, 1] - p[2, 1]) * (xx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (yy - p[2, 1])
        ) / denominator
        bb = (
            (p[2, 1] - p[0, 1]) * (xx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (yy - p[2, 1])
        ) / denominator
        bc = 1 - ba - bb
        d = depths[faces[index]]
        value = ba * d[0] + bb * d[1] + bc * d[2]
        region = np.s_[low[1] : high[1] + 1, low[0] : high[0] + 1]
        current = zbuffer[region]
        mask = (ba >= -1e-6) & (bb >= -1e-6) & (bc >= -1e-6) & (value > current)
        current[mask] = value[mask]
        brightness[region][mask] = 0.42 + 0.58 * max(0, normals[index] @ light)
        facing = normals[index] @ eye
        slope_x[region][mask] = -(normals[index] @ right) / (facing * scale)
        slope_y[region][mask] = (normals[index] @ up) / (facing * scale)
        # Flat pocket floors receive less light than the exposed underside.
        # Use actual surface height, so this also works for the blind thread.
        if normals[index, 2] < -0.8:
            z = triangles[index, :, 2]
            recess[region][mask] = (ba * z[0] + bb * z[1] + bc * z[2])[mask]
        else:
            recess[region][mask] = 0

    visible = np.isfinite(zbuffer)
    occlusion = np.zeros_like(brightness)
    # Nearby surfaces closer to the camera shade a recess; the depth buffer
    # avoids the false holes produced by sorting whole triangles by depth.
    safe_depth = np.where(visible, zbuffer, -10000)
    for radius in (0.45, 1.0, 2.0):
        pixels = max(1, round(radius * scale))
        for angle in np.arange(8) * np.pi / 4:
            dx, dy = np.rint([np.cos(angle) * pixels, np.sin(angle) * pixels]).astype(
                int
            )
            x0, x1 = max(0, -dx), min(width, width - dx)
            y0, y1 = max(0, -dy), min(height, height - dy)
            region = np.s_[y0:y1, x0:x1]
            neighbor = safe_depth[y0 + dy : y1 + dy, x0 + dx : x1 + dx]
            # Compare against the local surface plane, so the tilted flat
            # underside is not incorrectly treated as a shaded recess.
            difference = (
                neighbor
                - safe_depth[region]
                - dx * slope_x[region]
                - dy * slope_y[region]
            )
            occlusion[region] += (
                (difference > radius * 0.28) & (difference < radius * 6)
            ) / 24
    brightness *= 1 - 0.68 * occlusion
    brightness *= np.exp(-0.22 * recess)
    pixels = np.empty((height, width, 3), dtype=np.uint8)
    for channel, color in enumerate(MODEL_COLOR):
        pixels[:, :, channel] = np.clip(color * brightness + 12, 0, 255)
    rgba = Image.fromarray(pixels).convert("RGBA")
    rgba.putalpha(Image.fromarray(visible.astype(np.uint8) * 255))
    result = Image.new("RGBA", (width, height), BACKGROUND)
    shadow = Image.new("RGBA", (width, height), "#49321f")
    alpha = Image.fromarray((visible * 35).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(9 * ss)
    )
    shadow.putalpha(alpha)
    result.alpha_composite(shadow, (0, 9 * ss))
    result.alpha_composite(rgba)
    return result.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def save_picture(solid, output, **view):
    picture = render(solid, **view)
    picture.save(output, optimize=True)
    thumbnail_dir = output.parent / "thumbnails"
    thumbnail_dir.mkdir(exist_ok=True)
    thumbnail = picture.resize(
        (260, round(picture.height * 260 / picture.width)), Image.Resampling.LANCZOS
    )
    thumbnail.save(thumbnail_dir / output.name, optimize=True)
    print(output, flush=True)


def render_segments_comparison(output_dir):
    """Compare actual thread meshes with identical framing and lighting."""
    options = BaseOptions(thumbscrew=True)
    grid = Grid(1, 1, 0, 0, 0)
    for segments in (32, 64, 256):
        solid = generate_base(options, grid, height=7, segments=segments)
        if solid.status() != m.Error.NoError or len(solid.decompose()) != 1:
            raise RuntimeError("Segments comparison must be a single valid solid")
        save_picture(
            solid,
            output_dir / f"detail-segments-{segments}.png",
            size=(720, 440),
            target=(0, 0, 1.0),
            span=23,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/images")
    parser.add_argument("--segments", type=int, default=256)
    parser.add_argument(
        "--segments-only",
        action="store_true",
        help="Render only the fixed 32/64/256 curve-resolution comparisons",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    render_segments_comparison(args.output_dir)
    if args.segments_only:
        return
    variants = [
        ("plain", resolve_options("plain")),
        ("rebuilt", resolve_options("rebuilt")),
        ("rebuilt-screws", resolve_options("rebuilt-screws")),
        ("press-fit", resolve_options("press-fit")),
        ("screws", BaseOptions(screws=True)),
        ("magnets-bottom", BaseOptions(magnets="bottom")),
        ("press-fit-screws", resolve_options("press-fit", screws=True)),
        ("rebuilt-thumbscrew", resolve_options("rebuilt", thumbscrew=True)),
        ("rebuilt-only-corners", resolve_options("rebuilt", only_corners=True)),
        (
            "rebuilt-screws-thumbscrew",
            resolve_options("rebuilt-screws", thumbscrew=True),
        ),
        (
            "rebuilt-screws-thumbscrew-only-corners",
            resolve_options("rebuilt-screws", thumbscrew=True, only_corners=True),
        ),
    ]
    solids = {}
    for name, options in variants:
        print(f"Rendering {name}...", flush=True)
        solid = example_bin(options, args.segments)
        solids[name] = solid
        save_picture(solid, args.output_dir / f"base-{name}-2x3.png", size=(720, 560))
    details = [
        (
            "side-loading",
            "rebuilt",
            {"azimuth": 20, "elevation": -24, "target": (37, 55, 1.5), "span": 26},
        ),
        ("magnets-bottom", "magnets-bottom", {"target": (34, 55, 0.7), "span": 13}),
        ("crush-ribs", "press-fit", {"target": (34, 55, 0.7), "span": 13}),
        ("thumbscrew", "rebuilt-thumbscrew", {"target": (21, 42, 1.0), "span": 23}),
    ]
    for name, source, view in details:
        save_picture(
            solids[source],
            args.output_dir / f"detail-{name}.png",
            size=(720, 440),
            **view,
        )


if __name__ == "__main__":
    main()
