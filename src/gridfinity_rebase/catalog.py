"""Preset descriptions, kept importable without loading the geometry engine."""

from dataclasses import dataclass, replace
from typing import Literal

from .errors import RebaseError
from .options import BaseOptions

PRESETS = {
    "plain": "Plain mating foot, no magnet or screw holes",
    "magnet-holes": "Smooth bottom-loading 6.5 x 2.4 mm magnet pockets, no crush ribs",
    "rebuilt": "Rebuilt/Refined fan pattern of side-loading 5.86 x 2.1 mm magnet pockets and removal slots",
    "press-fit": "Rebuilt bottom magnet pockets with 8 crush ribs (5.9–6.5 mm diameter)",
    "refined": "Alias of rebuilt: side-loading magnet pockets",
}

ALIASES = {"refined": "rebuilt"}

PRESET_OPTIONS = {
    "plain": BaseOptions(),
    "magnet-holes": BaseOptions(magnets="bottom"),
    "rebuilt": BaseOptions(magnets="side"),
    "press-fit": BaseOptions(magnets="bottom", crush_ribs=True),
}


@dataclass(frozen=True)
class Preset:
    """Preset metadata; aliases have the same options as their canonical preset."""

    id: str
    description: str
    options: BaseOptions
    alias_of: str | None = None


def list_presets() -> tuple[Preset, ...]:
    """Return presets and compatibility aliases without loading geometry."""
    return tuple(
        Preset(
            name,
            description,
            PRESET_OPTIONS[ALIASES.get(name, name)],
            ALIASES.get(name),
        )
        for name, description in PRESETS.items()
    )


def resolve_options(
    preset: str = "plain",
    *,
    magnets: Literal["none", "side", "bottom"] | None = None,
    screws: bool | None = None,
    crush_ribs: bool | None = None,
    thumbscrew: bool | None = None,
    only_corners: bool | None = None,
    side_pocket_height_mm: float | None = None,
) -> BaseOptions:
    """Apply explicit overrides to a preset; None means keep its setting."""
    if preset not in PRESETS:
        raise RebaseError(
            f"Unknown preset: {preset}",
            code="unknown_preset",
            details={"preset": preset},
        )
    options = PRESET_OPTIONS[ALIASES.get(preset, preset)]
    overrides = {
        name: value
        for name, value in {
            "magnets": magnets,
            "screws": screws,
            "crush_ribs": crush_ribs,
            "thumbscrew": thumbscrew,
            "only_corners": only_corners,
            "side_pocket_height_mm": side_pocket_height_mm,
        }.items()
        if value is not None
    }
    # Ribs inherited from a preset belong to its bottom-loading pockets.
    # An explicit --crush-ribs still fails validation for other magnet styles.
    if magnets is not None and magnets != "bottom" and crush_ribs is None:
        overrides["crush_ribs"] = False
    if magnets is not None and magnets != "side" and side_pocket_height_mm is None:
        overrides["side_pocket_height_mm"] = None
    return replace(options, **overrides)
