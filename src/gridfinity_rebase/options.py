"""Geometry settings independent of preset names and the geometry engine."""

from dataclasses import asdict, dataclass
from typing import Literal

from . import RebaseError


@dataclass(frozen=True)
class BaseOptions:
    magnets: Literal["none", "side", "bottom"] = "none"
    screws: bool = False
    crush_ribs: bool = False
    thumbscrew: bool = False

    def __post_init__(self):
        if self.magnets not in ("none", "side", "bottom"):
            raise RebaseError(f"Unknown magnet style: {self.magnets}")
        if self.crush_ribs and self.magnets != "bottom":
            raise RebaseError("--crush-ribs requires --magnets bottom")

    def describe(self):
        return asdict(self)

    def filename_suffix(self):
        parts = []
        if self.magnets != "none":
            parts.append(f"magnets-{self.magnets}")
        if self.crush_ribs:
            parts.append("crush-ribs")
        if self.screws:
            parts.append("screws")
        if not parts:
            parts.append("plain")
        if self.thumbscrew:
            parts.append("thumbscrew")
        return "-".join(parts)
