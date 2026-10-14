"""Geometry settings independent of preset names and the geometry engine."""

from dataclasses import asdict, dataclass
from math import isfinite
from numbers import Real
from typing import Literal

from .errors import RebaseError

DEFAULT_SIDE_POCKET_HEIGHT_MM = 2.1


@dataclass(frozen=True)
class BaseOptions:
    magnets: Literal["none", "side", "bottom"] = "none"
    screws: bool = False
    crush_ribs: bool = False
    thumbscrew: bool = False
    only_corners: bool = False
    side_pocket_height_mm: float | None = None

    def __post_init__(self):
        if self.magnets not in ("none", "side", "bottom"):
            raise RebaseError(
                f"Unknown magnet style: {self.magnets}",
                code="invalid_options",
                details={"field": "magnets"},
            )
        for name in ("screws", "crush_ribs", "thumbscrew", "only_corners"):
            if not isinstance(getattr(self, name), bool):
                raise RebaseError(
                    f"{name} must be a boolean",
                    code="invalid_options",
                    details={"field": name},
                )
        if self.crush_ribs and self.magnets != "bottom":
            raise RebaseError(
                "--crush-ribs requires --magnets bottom",
                code="invalid_options",
                details={"field": "crush_ribs", "requires": {"magnets": "bottom"}},
            )
        if self.side_pocket_height_mm is not None:
            value = self.side_pocket_height_mm
            if (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not isfinite(value)
                or not 0 < value < 4.35
            ):
                raise RebaseError(
                    "Side pocket height must be finite, positive and below 4.35 mm",
                    code="invalid_options",
                    details={"field": "side_pocket_height_mm"},
                )
            if self.magnets != "side":
                raise RebaseError(
                    "--side-pocket-height requires --magnets side",
                    code="invalid_options",
                    details={"field": "side_pocket_height_mm"},
                )

    @property
    def effective_side_pocket_height_mm(self):
        """Actual void height, rather than nominal magnet thickness."""
        return (
            DEFAULT_SIDE_POCKET_HEIGHT_MM
            if self.side_pocket_height_mm is None
            else self.side_pocket_height_mm
        )

    def describe(self):
        result = asdict(self)
        result["side_pocket_height_mm"] = (
            self.effective_side_pocket_height_mm if self.magnets == "side" else None
        )
        return result

    def filename_suffix(self):
        parts = []
        if self.magnets != "none":
            parts.append(f"magnets-{self.magnets}")
        if (
            self.magnets == "side"
            and self.effective_side_pocket_height_mm != DEFAULT_SIDE_POCKET_HEIGHT_MM
        ):
            parts.append(f"pocket-height-{self.effective_side_pocket_height_mm:g}mm")
        if self.crush_ribs:
            parts.append("crush-ribs")
        if self.screws:
            parts.append("screws")
        if not parts:
            parts.append("plain")
        if self.thumbscrew:
            parts.append("thumbscrew")
        if self.only_corners:
            parts.append("only-corners")
        return "-".join(parts)
