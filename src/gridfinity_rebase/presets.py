"""Native tessellation of the published Gridfinity/Rebuilt foot geometry.

Dimensions: kennetek/gridfinity-rebuilt-openscad, src/core/standard.scad.
Refined side-load pocket: src/core/gridfinity-rebuilt-holes.scad (MIT).
See docs/presets.md and THIRD_PARTY_NOTICES.md for sources and attribution.
"""

from functools import lru_cache

import manifold3d as m
import numpy as np

from . import RebaseError
from .catalog import PRESETS
from .geometry import PITCH, PROFILE_HEIGHT, Grid


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


def refined_pocket(segments):
    # Port of Rebuilt's refined_hole(): opening toward +X, bottom at 0.4.
    pocket = cylinder(2.93, 0.4, 2.3, segments) + m.Manifold.cube(
        (11, 5.86, 1.9)
    ).translate((0, -2.93, 0.4))
    removal = cylinder(1.25, -0.2, 2.3, segments).translate((-6.93, 0, 0))
    removal += m.Manifold.cube((4.4, 2.5, 2.5)).translate((-6.93, -1.25, -0.2))
    return pocket + removal


@lru_cache(maxsize=32)
def single_foot(preset, segments):
    rings = []
    for z, radius in [(0, 0.8), (0.8, 1.6), (2.6, 1.6), (4.75, 3.75)]:
        width = 34 + 2 * radius
        ring = rounded_ring(width, width, radius, segments)
        rings.append(np.column_stack((ring, np.full(len(ring), z))))
    foot = loft_rings(rings)
    if preset == "standard":
        return foot
    if preset == "refined":
        hole = refined_pocket(segments)
    elif preset == "press-fit":
        angle = np.linspace(0, 2 * np.pi, segments, endpoint=False)
        radius = 3.1 + 0.15 * np.sin(8 * angle)
        hole = (
            m.CrossSection(
                [np.column_stack((radius * np.cos(angle), radius * np.sin(angle)))]
            )
            .extrude(2.41)
            .translate((0, 0, -0.01))
        )
    else:
        hole = cylinder(3.25, -0.01, 2.4, segments)
        if preset == "rebuilt-screws":
            hole += cylinder(1.5, -0.01, PROFILE_HEIGHT + 0.01, segments)
    holes = []
    for x in (-13, 13):
        for y in (-13, 13):
            oriented = hole
            if preset == "refined":
                # Both left and right openings point to the nearest outside edge.
                oriented = hole.rotate((0, 0, 180 if x < 0 else 0))
            holes.append(oriented.translate((x, y, 0)))
    return m.Manifold.batch_boolean([foot, *holes], m.OpType.Subtract)


def preset_base(preset: str, grid: Grid, height=PROFILE_HEIGHT, segments=64):
    if preset not in PRESETS:
        raise RebaseError(f"Unknown preset: {preset}")
    if segments < 32 or segments > 256 or segments % 8:
        raise RebaseError("Segments must be a multiple of 8 between 32 and 256")
    parts = [
        single_foot(preset, segments).translate((x, y, grid.z)) for x, y in grid.cells
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
        if preset == "rebuilt-screws":
            holes = [
                cylinder(
                    1.5,
                    grid.z + PROFILE_HEIGHT - 0.01,
                    grid.z + min(height, 7) + 0.01,
                    segments,
                ).translate((x + dx, y + dy, 0))
                for x, y in grid.cells
                for dx in (-13, 13)
                for dy in (-13, 13)
            ]
            bridge = m.Manifold.batch_boolean([bridge, *holes], m.OpType.Subtract)
        parts.append(bridge)
    return m.Manifold.batch_boolean(parts, m.OpType.Add)
