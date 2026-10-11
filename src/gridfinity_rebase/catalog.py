"""Preset descriptions, kept importable without loading the geometry engine."""

PRESETS = {
    "plain": "Plain mating foot, no magnet or screw holes",
    "rebuilt": "Rebuilt/Refined side-loading 5.86 x 1.9 mm magnet pockets and removal slots",
    "rebuilt-screws": "Rebuilt side-loading magnet pockets + 3 mm screw bores (depth limited to replacement height)",
    "press-fit": "Rebuilt bottom magnet pockets with 8 crush ribs (5.9–6.5 mm diameter)",
    "refined": "Alias of rebuilt: side-loading magnet pockets",
    "standard": "Alias of plain: no magnet or screw holes",
}

ALIASES = {"refined": "rebuilt", "standard": "plain"}
