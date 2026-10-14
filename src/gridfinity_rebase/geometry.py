"""Detect the mating profile, align a donor, and weld the replacement."""

from dataclasses import dataclass

import manifold3d as m
import numpy as np

from .errors import RebaseError

PITCH = 42.0
PROFILE_HEIGHT = 4.75
BASE_HEIGHT = 7.0


@dataclass(frozen=True)
class Grid:
    nx: int
    ny: int
    x: float  # centre of the first foot, not the model's bounding box
    y: float
    z: float

    @property
    def cells(self):
        return [
            (self.x + PITCH * i, self.y + PITCH * j)
            for i in range(self.nx)
            for j in range(self.ny)
        ]

    def describe(self):
        return {"grid": [self.nx, self.ny], "origin_mm": [self.x, self.y, self.z]}


def signed_area(points):
    p = np.asarray(points)
    return float(
        np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1)) * 0.5
    )


def outer_boxes(solid, z):
    boxes = []
    for poly in solid.slice(z).to_polygons():
        if signed_area(poly) > 1:
            points = np.asarray(poly)
            low, high = points.min(axis=0), points.max(axis=0)
            boxes.append((low, high))
    return boxes


def nominal_section(width, centres):
    # Some exported bins keep ~1.6 mm corner fillets through the upper
    # chamfer instead of expanding them. Accept this common variant too.
    radius = min((width - 34) / 2, 1.6)
    contours = []
    for cx, cy in centres:
        points = []
        for quadrant, (sx, sy) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)]):
            angle = np.linspace(quadrant * np.pi / 2, (quadrant + 1) * np.pi / 2, 17)
            points.extend(
                np.column_stack(
                    (
                        cx + sx * (width / 2 - radius) + radius * np.cos(angle),
                        cy + sy * (width / 2 - radius) + radius * np.sin(angle),
                    )
                )
            )
        contours.append(points)
    return m.CrossSection(contours)


def detect_grid(solid: m.Manifold, label="Model", tolerance=0.35) -> Grid:
    """Require individual feet on a 42 mm lattice and all three profile stages."""
    z = solid.bounding_box()[2]
    if solid.bounding_box()[5] - z < PROFILE_HEIGHT - 0.05:
        raise RebaseError(
            f"{label}: not Gridfinity: shorter than the 4.75 mm foot profile"
        )
    boxes = outer_boxes(solid, z + 1.4)
    if not boxes:
        raise RebaseError(
            f"{label}: not Gridfinity: no feet found (use millimetres, Z up)"
        )
    centres = np.array([(lo + hi) / 2 for lo, hi in boxes])
    origin = centres.min(axis=0)
    lattice = np.rint((centres - origin) / PITCH).astype(int)
    if np.max(np.abs(centres - origin - lattice * PITCH)) > tolerance:
        raise RebaseError(f"{label}: not Gridfinity: feet are not on a 42 mm grid")
    nx, ny = (lattice.max(axis=0) + 1).tolist()
    if len(set(map(tuple, lattice))) != nx * ny or len(boxes) != nx * ny:
        raise RebaseError(
            f"{label}: unsupported Gridfinity footprint: expected a complete rectangular grid"
        )
    expected_centres = sorted(map(tuple, centres))
    # Bounds alone would accept an ordinary 41.5 mm box or a baseplate.
    for height, width in [(0.3, 36.2), (1.4, 37.2), (3.5, 39.0), (4.6, 41.2)]:
        sections = outer_boxes(solid, z + height)
        if len(sections) != nx * ny:
            raise RebaseError(
                f"{label}: not Gridfinity: unexpected foot sections at Z+{height:g} mm"
            )
        sections.sort(key=lambda box: tuple((box[0] + box[1]) / 2))
        for (low, high), centre in zip(sections, expected_centres):
            if (
                np.max(np.abs(high - low - width)) > tolerance
                or np.max(np.abs((low + high) / 2 - centre)) > tolerance
            ):
                raise RebaseError(
                    f"{label}: not Gridfinity: incorrect chamfer/profile at Z+{height:g} mm; expected {width:g} mm feet (mm, Z up)"
                )
        filled = m.CrossSection(
            [p for p in solid.slice(z + height).to_polygons() if signed_area(p) > 0]
        )
        envelope = nominal_section(width, centres).offset(tolerance)
        if (filled - envelope).area() > 0.25 * nx * ny:
            raise RebaseError(
                f"{label}: not Gridfinity: feet do not have compatible rounded corners at Z+{height:g} mm"
            )
    return Grid(nx, ny, float(origin[0]), float(origin[1]), float(z))


def lower(solid, height):
    return solid.trim_by_plane((0, 0, -1), -height)


@dataclass(frozen=True)
class StandardBase:
    height: float
    interior_start: float | None = None

    def describe(self):
        return {
            "standard_bin": True,
            "recommended_base_height_mm": self.height,
            "interior_start_mm": self.interior_start,
            "nominal_base_height_mm": BASE_HEIGHT,
        }


def standard_outline(grid: Grid):
    from .presets import rounded_ring

    centre = (grid.x + (grid.nx - 1) * 21, grid.y + (grid.ny - 1) * 21)
    ring = rounded_ring(grid.nx * PITCH - 0.5, grid.ny * PITCH - 0.5, 3.75, 64)
    return m.CrossSection([ring + centre])


def is_hardware_hole(poly, grid: Grid):
    """Recognize circular corner bores and central thumbscrew bores only."""
    points = np.asarray(poly)
    low, high = points.min(axis=0), points.max(axis=0)
    size = high - low
    centre = (high + low) / 2
    if abs(size[0] - size[1]) > 0.5:
        return False
    area = abs(signed_area(points))
    if not 0.65 * size[0] * size[1] <= area <= 0.87 * size[0] * size[1]:
        return False
    i, j = np.rint((centre - (grid.x, grid.y)) / PITCH).astype(int)
    if not (0 <= i < grid.nx and 0 <= j < grid.ny):
        return False
    offset = np.abs(centre - (grid.x + i * PITCH, grid.y + j * PITCH))
    if np.max(size) <= 7.5 and np.max(np.abs(offset - 13)) <= 0.4:
        return True
    return bool(np.max(size) <= 16 and np.max(offset) <= 0.4)


def detect_standard_base(solid, grid: Grid, label="Model") -> StandardBase:
    """Recognize a standard full bridge up to 7 mm, stopping before the interior.

    A small set of slices covers the nominal bridge; binary search refines
    the first interior transition. Custom bases require an explicit height.
    """
    message = f"{label}: standard bin base not recognized; specify --base-height explicitly for a custom model"
    if solid.bounding_box()[5] - grid.z <= BASE_HEIGHT + 0.1:
        raise RebaseError(message)
    envelope = standard_outline(grid)
    expanded_envelope = envelope.offset(0.15)

    def classify(height):
        polygons = solid.slice(grid.z + height).to_polygons()
        outers = [p for p in polygons if signed_area(p) > 0.02]
        if len(outers) != 1:
            return "outline"
        outer = m.CrossSection(outers)
        allowance = 0.25 * grid.nx * grid.ny
        if (outer - expanded_envelope).area() > allowance or (
            envelope - outer.offset(0.15)
        ).area() > allowance:
            return "outline"
        for poly in polygons:
            if signed_area(poly) < -0.02 and not is_hardware_hole(poly, grid):
                return "interior"
        return "base"

    previous = PROFILE_HEIGHT + 0.05
    if classify(previous) != "base":
        raise RebaseError(message)
    for height in (5.0, 5.5, 6.0, 6.5, BASE_HEIGHT):
        kind = classify(height)
        if kind == "outline":
            raise RebaseError(message)
        if kind == "interior":
            low, high = previous, height
            while high - low > 0.001:
                middle = (low + high) / 2
                kind = classify(middle)
                if kind == "outline":
                    raise RebaseError(message)
                if kind == "base":
                    low = middle
                else:
                    high = middle
            # Keep a 0.02 mm margin below the first real interior contour.
            safe_height = np.floor((low - 0.02) * 100) / 100
            if safe_height < 5.0:
                raise RebaseError(message)
            return StandardBase(float(safe_height), round(high, 3))
        previous = height
    return StandardBase(BASE_HEIGHT)


def donor_base(solid, donor: Grid, target: Grid, height: float):
    if solid.bounding_box()[5] < donor.z + height - 1e-5:
        raise RebaseError(
            f"Donor is shorter than the requested {height:g} mm replacement"
        )
    base = lower(solid, donor.z + height).translate((-donor.x, -donor.y, -donor.z))
    if (donor.nx, donor.ny) == (target.nx, target.ny):
        return base.translate((target.x, target.y, target.z))
    if (donor.ny, donor.nx) == (target.nx, target.ny):
        return base.rotate((0, 0, 90)).translate(
            (target.x + (target.nx - 1) * PITCH, target.y, target.z)
        )
    if (donor.nx, donor.ny) == (1, 1):
        if height <= PROFILE_HEIGHT:
            return m.Manifold.batch_boolean(
                [base.translate((x, y, target.z)) for x, y in target.cells],
                m.OpType.Add,
            )
        from .presets import rounded_prism

        # Tile feet and hardware cutouts, then join them with a continuous
        # standard bridge; copying whole 1x1 tiles would leave 0.5 mm slots.
        feet = lower(base, PROFILE_HEIGHT)
        donor_envelope = rounded_prism(41.5, 41.5, 3.75, PROFILE_HEIGHT, height)
        cutouts = donor_envelope - base.trim_by_plane((0, 0, 1), PROFILE_HEIGHT)
        bridge = rounded_prism(
            target.nx * PITCH - 0.5,
            target.ny * PITCH - 0.5,
            3.75,
            PROFILE_HEIGHT,
            height,
        ).translate(((target.nx - 1) * 21, (target.ny - 1) * 21, 0))
        offsets = [
            (i * PITCH, j * PITCH, 0)
            for i in range(target.nx)
            for j in range(target.ny)
        ]
        bridge = m.Manifold.batch_boolean(
            [bridge, *(cutouts.translate(offset) for offset in offsets)],
            m.OpType.Subtract,
        )
        tiled = m.Manifold.batch_boolean(
            [bridge, *(feet.translate(offset) for offset in offsets)], m.OpType.Add
        )
        return tiled.translate((target.x, target.y, target.z))
    raise RebaseError(
        f"Donor grid {donor.nx}x{donor.ny} does not match input {target.nx}x{target.ny}; use a matching donor or 1x1 donor"
    )


def validate_height(solid, grid: Grid, height):
    if (
        not np.isfinite(height)
        or height < PROFILE_HEIGHT
        or height >= solid.bounding_box()[5] - grid.z
    ):
        raise RebaseError(
            "Base height must be at least 4.75 mm and below the top of the input model"
        )


def replace_base(solid, replacement, grid: Grid, height=PROFILE_HEIGHT):
    validate_height(solid, grid, height)
    seam = grid.z + height
    # At this height the foot must connect to a body. An exposed donor top
    # outside the input would create a lip or a disconnected foot.
    original_section = m.CrossSection(
        [p for p in solid.slice(seam + 1e-5).to_polygons() if signed_area(p) > 0]
    )
    replacement_section = m.CrossSection(
        [p for p in replacement.slice(seam - 1e-5).to_polygons() if signed_area(p) > 0]
    )
    if (
        replacement_section - original_section.offset(0.12)
    ).area() > 0.2 * grid.nx * grid.ny:
        raise RebaseError(
            "Replacement does not fit the input at the seam; choose a matching donor or a lower --base-height",
            code="incompatible_seam",
        )
    upper = solid.trim_by_plane((0, 0, 1), seam)

    # Plane trimming can leave cap coordinates a few ULPs off the plane.
    # Snap only those coordinates, so exact face-to-face union stays connected.
    def snap_cap(vertices):
        vertices = vertices.copy()
        vertices[np.abs(vertices[:, 2] - seam) < 1e-8, 2] = seam
        return vertices

    upper = upper.warp_batch(snap_cap)
    replacement = replacement.warp_batch(snap_cap)
    result = upper + replacement
    if result.status() != m.Error.NoError or result.is_empty() or result.volume() <= 0:
        raise RebaseError(
            f"Replacement failed to produce a valid solid: {result.status().name}"
        )
    # A single-body input must stay connected; all tiled feet must be attached.
    # Negative-volume shells are enclosed cavities, not detached solids.
    if sum(part.volume() > 0 for part in result.decompose()) > sum(
        part.volume() > 0 for part in solid.decompose()
    ):
        raise RebaseError(
            "Replacement would leave disconnected feet; check the donor and --base-height",
            code="disconnected_result",
        )
    return result
