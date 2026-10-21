"""In-memory orchestration shared by CLI and other clients.

All coordinates and heights are millimetres, with feet down and Z pointing up.
Operations normalize Z rotation and translation internally; meshes and report
origins retain source coordinates. Cut heights are relative to the underside.
Functions are synchronous and never print or write files implicitly.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from time import perf_counter
from typing import Literal

import manifold3d as m
import numpy as np
from numpy.typing import NDArray

from .errors import RebaseError
from .geometry import (
    PROFILE_HEIGHT,
    NormalizedModel,
    detect_standard_base,
    donor_base,
    normalize_model,
    replace_base,
    validate_height,
)
from .options import BaseOptions
from .presets import generate_base
from .stl import read_stl, write_stl


@dataclass(frozen=True, init=False)
class Model:
    """Validated solid. Obtain through load_stl() or RebaseResult.model.

    The engine representation is private. to_mesh() returns independent arrays
    suitable for rendering, without exposing the geometry engine to callers.
    """

    _solid: m.Manifold = field(repr=False)
    source: Path | None

    def __new__(cls):
        raise TypeError("Models are created through load_stl() or rebase()")

    @classmethod
    def _from_solid(cls, solid: m.Manifold, source: Path | None = None) -> "Model":
        model = object.__new__(cls)
        object.__setattr__(model, "_solid", solid)
        object.__setattr__(model, "source", source)
        return model

    @property
    def triangles(self) -> int:
        return self._solid.num_tri()

    def to_mesh(self) -> tuple[NDArray[np.float64], NDArray[np.uint64]]:
        """Return copies of vertices (N, 3) in mm and triangle indices (M, 3).

        Coordinates retain the input origin and use float64 precision. STL
        export separately quantizes and validates the result at float32.
        """
        mesh = self._solid.to_mesh64()
        return (
            np.array(mesh.vert_properties[:, :3], dtype=np.float64, copy=True),
            np.array(mesh.tri_verts, dtype=np.uint64, copy=True),
        )


@dataclass(frozen=True)
class Inspection:
    """Grid and base detection; an unrecognized base is non-fatal.

    origin_mm and rotation_z_deg map the normalized grid back to source
    coordinates. Rotation is modulo 90 degrees, in [-45, 45).
    """

    grid: tuple[int, int]
    origin_mm: tuple[float, float, float]
    triangles: int
    standard_bin: bool
    recommended_base_height_mm: float | None = None
    interior_start_mm: float | None = None
    nominal_base_height_mm: float | None = None
    base_detection_error: str | None = None
    base_detection_error_code: str | None = None
    rotation_z_deg: float = 0.0

    def describe(self) -> dict:
        """Return a JSON-ready report, compatible with CLI inspection fields."""
        report = {
            "grid": list(self.grid),
            "origin_mm": list(self.origin_mm),
            "rotation_z_deg": self.rotation_z_deg,
            "triangles": self.triangles,
            "standard_bin": self.standard_bin,
        }
        if self.standard_bin:
            report.update(
                recommended_base_height_mm=self.recommended_base_height_mm,
                interior_start_mm=self.interior_start_mm,
                nominal_base_height_mm=self.nominal_base_height_mm,
            )
        else:
            report["base_detection_error"] = self.base_detection_error
        return report


@dataclass(frozen=True)
class GeneratedBase:
    """Generate feet using resolved options and a curve segment count."""

    options: BaseOptions = field(default_factory=BaseOptions)
    segments: int = 64

    def __post_init__(self) -> None:
        if not isinstance(self.options, BaseOptions):
            raise RebaseError("options must be BaseOptions", code="invalid_options")
        if (
            not isinstance(self.segments, int)
            or isinstance(self.segments, bool)
            or not 32 <= self.segments <= 256
            or self.segments % 8
        ):
            raise RebaseError(
                "Segments must be a multiple of 8 between 32 and 256",
                code="invalid_segments",
                details={"segments": self.segments},
            )


@dataclass(frozen=True)
class DonorBase:
    """Copy an existing model's base, including its hardware geometry."""

    model: Model

    def __post_init__(self) -> None:
        if not isinstance(self.model, Model):
            raise RebaseError("Donor must be a Model", code="invalid_model")


ProgressStage = Literal[
    "detecting_grid",
    "detecting_base",
    "generating_base",
    "preparing_donor",
    "replacing_base",
    "complete",
]


@dataclass(frozen=True)
class ProgressEvent:
    """Stage notification, with no estimate of percentage or remaining time."""

    stage: ProgressStage


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True)
class RebaseReport:
    """Resolved settings and geometry statistics, independent of file output."""

    grid: tuple[int, int]
    origin_mm: tuple[float, float, float]
    base_height_mm: float
    base_height_mode: Literal["auto", "manual"]
    geometry: BaseOptions | None
    triangles: int
    elapsed_ms: float
    inspection: Inspection | None
    warnings: tuple[str, ...] = ()
    rotation_z_deg: float = 0.0

    def describe(self) -> dict:
        report = self.inspection.describe() if self.inspection is not None else {}
        report.update(
            grid=list(self.grid),
            origin_mm=list(self.origin_mm),
            rotation_z_deg=self.rotation_z_deg,
            base_height_mm=self.base_height_mm,
            base_height_mode=self.base_height_mode,
            geometry=self.geometry.describe() if self.geometry is not None else None,
            thumbscrew=self.geometry.thumbscrew if self.geometry is not None else None,
            triangles=self.triangles,
            elapsed_ms=self.elapsed_ms,
            warnings=list(self.warnings),
        )
        return report


@dataclass(frozen=True)
class RebaseResult:
    model: Model
    report: RebaseReport


@contextmanager
def _geometry_errors(code: str, **details) -> Iterator[None]:
    """Give legacy geometry errors a code without interpreting their messages."""
    try:
        yield
    except RebaseError as exc:
        if exc.code != "invalid_geometry":
            raise
        raise RebaseError(
            str(exc), code=code, details={**exc.details, **details}
        ) from exc


def _notify(callback: ProgressCallback | None, stage: ProgressStage) -> None:
    if callback is not None:
        callback(ProgressEvent(stage))


def _require_model(model: Model) -> None:
    if not isinstance(model, Model):
        raise RebaseError("Expected a Model from load_stl()", code="invalid_model")


def _normalize(model: Model) -> NormalizedModel:
    with _geometry_errors("invalid_grid"):
        return normalize_model(
            model._solid, str(model.source) if model.source else "Model"
        )


def _inspect(model: Model, normalized: NormalizedModel) -> Inspection:
    grid = normalized.grid
    fields = {
        "grid": (grid.nx, grid.ny),
        "origin_mm": normalized.frame.origin_mm,
        "rotation_z_deg": normalized.frame.rotation_z_deg,
        "triangles": model.triangles,
    }
    try:
        with _geometry_errors("unrecognized_base"):
            standard = detect_standard_base(
                normalized.solid, grid, str(model.source) if model.source else "Model"
            )
    except RebaseError as exc:
        if exc.code != "unrecognized_base":
            raise
        return Inspection(
            **fields,
            standard_bin=False,
            base_detection_error=str(exc),
            base_detection_error_code=exc.code,
        )
    return Inspection(**fields, **standard.describe())


def load_stl(path: str | Path) -> Model:
    """Read a closed, consistently oriented STL solid without detecting its grid."""
    path = Path(path)
    return Model._from_solid(read_stl(path), path)


def inspect_model(
    model: Model, *, on_progress: ProgressCallback | None = None
) -> Inspection:
    """Detect the grid and base; invalid grids raise, custom bases are reported."""
    _require_model(model)
    _notify(on_progress, "detecting_grid")
    normalized = _normalize(model)
    _notify(on_progress, "detecting_base")
    info = _inspect(model, normalized)
    _notify(on_progress, "complete")
    return info


def rebase(
    model: Model,
    *,
    base: GeneratedBase | DonorBase,
    base_height_mm: float | None = None,
    on_progress: ProgressCallback | None = None,
) -> RebaseResult:
    """Return a new model, preserving the input above the validated cut.

    None selects automatic standard-base detection, falling back to replacing
    only the 4.75 mm foot profile with a report warning for custom bases.
    An explicit height is measured from the bottom of the feet, not from
    absolute Z=0. Donor bases must match the grid, match after rotation, or
    be 1x1 for tiling.

    Target and donor are normalized independently before geometry operations.
    The returned model retains the target's original position and Z rotation.

    Callbacks run synchronously on the calling thread. Their exceptions
    propagate unchanged; callers are responsible for dispatching GUI updates.
    """
    start = perf_counter()
    _require_model(model)
    if not isinstance(base, (GeneratedBase, DonorBase)):
        raise RebaseError(
            "base must be GeneratedBase or DonorBase", code="invalid_base"
        )
    if base_height_mm is not None and (
        not isinstance(base_height_mm, Real) or isinstance(base_height_mm, bool)
    ):
        raise RebaseError("Base height must be numeric", code="invalid_height")
    _notify(on_progress, "detecting_grid")
    normalized = _normalize(model)
    grid = normalized.grid
    info = None
    warnings = ()
    if base_height_mm is None:
        _notify(on_progress, "detecting_base")
        info = _inspect(model, normalized)
        if info.standard_bin:
            height = info.recommended_base_height_mm
            assert height is not None
        else:
            height = PROFILE_HEIGHT
            warnings = (
                (
                    "Standard bin base not recognized; replacing only the bottom "
                    f"{PROFILE_HEIGHT:g} mm foot profile. Geometry above the cut, "
                    "including any old holes, is preserved; check the result in "
                    "a slicer. Use --base-height to choose a different cut height."
                ),
            )
    else:
        height = float(base_height_mm)
    with _geometry_errors("invalid_height", base_height_mm=height):
        validate_height(normalized.solid, grid, height)

    if isinstance(base, GeneratedBase):
        _notify(on_progress, "generating_base")
        with _geometry_errors("base_generation_failed"):
            replacement = generate_base(base.options, grid, height, base.segments)
        geometry = base.options
    else:
        _notify(on_progress, "preparing_donor")
        with _geometry_errors("incompatible_donor"):
            donor = normalize_model(
                base.model._solid,
                str(base.model.source) if base.model.source else "Donor",
            )
            if base_height_mm is None and height > PROFILE_HEIGHT:
                donor_standard = detect_standard_base(
                    donor.solid,
                    donor.grid,
                    str(base.model.source) if base.model.source else "Donor",
                )
                if donor_standard.height < height - 0.001:
                    raise RebaseError(
                        f"Donor base ends at {donor_standard.height:g} mm, before the input's {height:g} mm cut; use a compatible donor or set --base-height explicitly",
                        code="incompatible_donor",
                        details={
                            "donor_base_height_mm": donor_standard.height,
                            "base_height_mm": height,
                        },
                    )
            replacement = donor_base(donor.solid, donor.grid, grid, height)
        geometry = None

    _notify(on_progress, "replacing_base")
    with _geometry_errors("replacement_failed"):
        solid = normalized.frame.to_source(
            replace_base(normalized.solid, replacement, grid, height)
        )
    result = RebaseResult(
        model=Model._from_solid(solid),
        report=RebaseReport(
            grid=(grid.nx, grid.ny),
            origin_mm=normalized.frame.origin_mm,
            rotation_z_deg=normalized.frame.rotation_z_deg,
            base_height_mm=height,
            base_height_mode="auto" if base_height_mm is None else "manual",
            geometry=geometry,
            triangles=solid.num_tri(),
            elapsed_ms=round((perf_counter() - start) * 1000, 2),
            inspection=info,
            warnings=warnings,
        ),
    )
    _notify(on_progress, "complete")
    return result


def save_stl(model: Model, path: str | Path, *, overwrite: bool = False) -> int:
    """Atomically export binary STL; return the exported triangle count.

    Float32 export is validated separately and may change the triangle count
    compared to the in-memory model. Existing files are protected by default.
    """
    _require_model(model)
    return write_stl(model._solid, path, overwrite=overwrite)
