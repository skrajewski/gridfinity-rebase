"""Replace Gridfinity feet without a CAD subprocess."""

__version__ = "0.1.0"


class RebaseError(ValueError):
    """Invalid geometry or an unsupported replacement."""
