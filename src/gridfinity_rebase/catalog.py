"""Preset descriptions, kept importable without loading the geometry engine."""

from dataclasses import dataclass, replace
from typing import Literal

from .errors import RebaseError
from .options import BaseOptions

PRESETS = {
    "plain": "Plain mating foot, no magnet or screw holes",
    "rebuilt": "Rebuilt/Refined fan pattern of side-loading 5.86 x 1.9 mm magnet pockets and removal slots",
    "rebuilt-screws": "Rebuilt fan pattern of side-loading magnet pockets + 3 mm screw bores (depth limited to replacement height)",
    "press-fit": "Rebuilt bottom magnet pockets with 8 crush ribs (5.9–6.5 mm diameter)",
    "refined": "Alias of rebuilt: side-loading magnet pockets",
    "standard": "Alias of plain: no magnet or screw holes",
}

ALIASES = {"refined": "rebuilt", "standard": "plain"}

PRESET_OPTIONS = {
    "plain": BaseOptions(),
    "rebuilt": BaseOptions(magnets="side"),
    "rebuilt-screws": BaseOptions(magnets="side", screws=True),
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
        }.items()
        if value is not None
    }
    # Ribs inherited from a preset belong to its bottom-loading pockets.
    # An explicit --crush-ribs still fails validation for other magnet styles.
    if magnets is not None and magnets != "bottom" and crush_ribs is None:
        overrides["crush_ribs"] = False
    return replace(options, **overrides)
