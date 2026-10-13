"""Native tessellation of the published Gridfinity/Rebuilt foot geometry.

Dimensions: kennetek/gridfinity-rebuilt-openscad, src/core/standard.scad.
Refined side-load pocket: src/core/gridfinity-rebuilt-holes.scad (MIT).
See docs/presets.md, README.md, and LICENSE for sources and attribution.
"""

from functools import lru_cache

import manifold3d as m
import numpy as np

from . import RebaseError
from .catalog import PRESETS, resolve_options
from .geometry import PITCH, PROFILE_HEIGHT, Grid
from .options import BaseOptions

__all__ = ["PRESETS", "generate_base", "preset_base"]

HOLE_CORNERS = ((-13, -13), (-13, 13), (13, -13), (13, 13))


def rounded_ring(width, depth, radius, segments):
    """Same vertex ordering at every profile level allows exact lofting."""
    points = []
    for quadrant, (sx, sy) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)]):
        angles = np.linspace(
            quadrant * np.pi / 2, (quadrant + 1) * np.pi / 2, segments // 4 + 1
        )
        points.extend(
            np.column_stack(
                (
                    sx * (width / 2 - radius) + radius * np.cos(angles),
                    sy * (depth / 2 - radius) + radius * np.sin(angles),
                )
            )
        )
    return np.asarray(points)


def loft_rings(rings):
    """Closed, consistently oriented mesh without a convex-hull operation."""
    count = len(rings[0])
    vertices = np.vstack(
        rings
        + [np.mean(rings[0], axis=0)[None, :], np.mean(rings[-1], axis=0)[None, :]]
    )
    faces = []
    for level in range(len(rings) - 1):
        for i in range(count):
            j = (i + 1) % count
            a, b = level * count + i, level * count + j
            c, d = a + count, b + count
            faces.extend([(a, b, d), (a, d, c)])
    bottom, top = len(vertices) - 2, len(vertices) - 1
    offset = (len(rings) - 1) * count
    for i in range(count):
        j = (i + 1) % count
        faces.extend([(bottom, j, i), (top, offset + i, offset + j)])
    return m.Manifold(
        m.Mesh64(np.array(vertices, dtype=np.float64), np.array(faces, dtype=np.uint64))
    )


def rounded_prism(width, depth, radius, bottom, top, segments=64):
    ring = rounded_ring(width, depth, radius, segments)
    return loft_rings(
        [np.column_stack((ring, np.full(len(ring), z))) for z in (bottom, top)]
    )


def cylinder(radius, bottom, top, segments):
    return m.Manifold.cylinder(
        top - bottom, radius, circular_segments=segments
    ).translate((0, 0, bottom))


def side_loading_pocket(segments):
    # Port of Rebuilt's refined_hole(): opening toward +X, bottom at 0.4.
    pocket = cylinder(2.93, 0.4, 2.3, segments) + m.Manifold.cube(
        (11, 5.86, 1.9)
    ).translate((0, -2.93, 0.4))
    removal = cylinder(1.25, -0.2, 2.3, segments).translate((-6.93, 0, 0))
    removal += m.Manifold.cube((4.4, 2.5, 2.5)).translate((-6.93, -1.25, -0.2))
    return pocket + removal


@lru_cache(maxsize=8)
def thumbscrew_hole(segments):
    """Native port of Rebuilt's M15x1.5 _base_thumbscrew() cutter.

    ScrewThread (Ryan A. Colyer, CC0) uses three helical rings per turn,
    with small offsets at the seam to keep its mesh non-degenerate.
    The hole stops at the top of the 4.75 mm foot, below the solid bridge.
    """
    pitch = 1.5
    tolerance = 0.4
    diameter = 1.01 * 15 + 1.25 * tolerance
    outer_radius = (diameter + 0.25 * tolerance) / 2
    inner_radius = (diameter - pitch / np.tan(np.pi / 6)) / 2
    levels = int(np.ceil(3 * PROFILE_HEIGHT / pitch)) + 6
    fudge = pitch * 0.001
    angle = np.arange(segments) * 2 * np.pi / segments
    rings = []
    for level in range(levels + 1):
        kind = level % 3
        offset = np.zeros(segments)
        if kind == 2:
            offset[-2:] = (pitch / 2, pitch - fudge)
        elif kind == 0:
            offset[-2:] = (fudge, pitch / 2)
        else:
            offset[-2:] = (pitch / 2, pitch / 2 + fudge)
        crest = (0, pitch / 2, pitch - fudge)[kind]
        z = (
            np.floor((level - 3) / 3) * pitch
            + crest
            + angle * pitch / (2 * np.pi)
            - offset
        )
        z = np.clip(z, level * fudge, PROFILE_HEIGHT - (levels - level) * fudge)
        phase = (z / pitch - angle / (2 * np.pi)) % 1
        tooth = 1 - np.abs(2 * phase - 1)
        radius = inner_radius + tooth * (outer_radius - inner_radius)
        rings.append(
            np.column_stack((radius * np.cos(angle), radius * np.sin(angle), z))
        )
    cutter = loft_rings(rings)
    if cutter.status() != m.Error.NoError:
        raise RebaseError(f"Cannot generate thumbscrew thread: {cutter.status().name}")
    return cutter


@lru_cache(maxsize=32)
def single_foot(options: BaseOptions, segments, corners=HOLE_CORNERS):
    rings = []
    for z, radius in [(0, 0.8), (0.8, 1.6), (2.6, 1.6), (4.75, 3.75)]:
        width = 34 + 2 * radius
        ring = rounded_ring(width, width, radius, segments)
        rings.append(np.column_stack((ring, np.full(len(ring), z))))
    foot = loft_rings(rings)
    if options.thumbscrew:
        foot -= thumbscrew_hole(segments)
    if not corners or (options.magnets == "none" and not options.screws):
        return foot
    hole = m.Manifold()
    if options.magnets == "side":
        hole = side_loading_pocket(segments)
    elif options.magnets == "bottom" and options.crush_ribs:
        angle = np.linspace(0, 2 * np.pi, segments, endpoint=False)
        radius = 3.1 + 0.15 * np.sin(8 * angle)
        hole = (
            m.CrossSection(
                [np.column_stack((radius * np.cos(angle), radius * np.sin(angle)))]
            )
            .extrude(2.41)
            .translate((0, 0, -0.01))
        )
    elif options.magnets == "bottom":
        hole = cylinder(3.25, -0.01, 2.4, segments)
    if options.screws:
        hole += cylinder(1.5, -0.01, PROFILE_HEIGHT + 0.01, segments)
    holes = []
    for x, y in corners:
        oriented = hole
        if options.magnets == "side":
            # Rebuilt's _base_holes(): a fan with one opening per foot edge.
            # Rotate the removal slit with the pocket, rather than mirroring
            # pairs of openings toward each other between adjacent feet.
            angle = {
                (13, 13): 0,
                (-13, 13): 90,
                (-13, -13): 180,
                (13, -13): 270,
            }[x, y]
            oriented = hole.rotate((0, 0, angle))
        holes.append(oriented.translate((x, y, 0)))
    return m.Manifold.batch_boolean([foot, *holes], m.OpType.Subtract)


def preset_base(
    preset: str,
    grid: Grid,
    height=PROFILE_HEIGHT,
    segments=64,
    *,
    thumbscrew=False,
    only_corners=False,
):
    """Compatibility entry point for callers using named presets."""
    return generate_base(
        resolve_options(preset, thumbscrew=thumbscrew, only_corners=only_corners),
        grid,
        height,
        segments,
    )


def generate_base(options: BaseOptions, grid: Grid, height=PROFILE_HEIGHT, segments=64):
    """Generate a base using only resolved geometry settings."""
    if segments < 32 or segments > 256 or segments % 8:
        raise RebaseError("Segments must be a multiple of 8 between 32 and 256")
    # Select individual hole positions, not entire corner feet. A 1xN grid
    # has two selected corners at each end, and a 1x1 grid keeps all four.
    cells = [
        (
            grid.x + i * PITCH,
            grid.y + j * PITCH,
            tuple(
                (dx, dy)
                for dx, dy in HOLE_CORNERS
                if not options.only_corners
                or (
                    i == (0 if dx < 0 else grid.nx - 1)
                    and j == (0 if dy < 0 else grid.ny - 1)
                )
            ),
        )
        for i in range(grid.nx)
        for j in range(grid.ny)
    ]
    parts = [
        single_foot(options, segments, corners).translate((x, y, grid.z))
        for x, y, corners in cells
    ]
    if height > PROFILE_HEIGHT:
        bridge = rounded_prism(
            grid.nx * PITCH - 0.5,
            grid.ny * PITCH - 0.5,
            3.75,
            grid.z + PROFILE_HEIGHT,
            grid.z + height,
            segments,
        )
        bridge = bridge.translate(
            (grid.x + (grid.nx - 1) * PITCH / 2, grid.y + (grid.ny - 1) * PITCH / 2, 0)
        )
        if options.screws:
            holes = [
                cylinder(
                    1.5,
                    grid.z + PROFILE_HEIGHT - 0.01,
                    grid.z + min(height, 7) + 0.01,
                    segments,
                ).translate((x + dx, y + dy, 0))
                for x, y, corners in cells
                for dx, dy in corners
            ]
            bridge = m.Manifold.batch_boolean([bridge, *holes], m.OpType.Subtract)
        parts.append(bridge)
    return m.Manifold.batch_boolean(parts, m.OpType.Add)
