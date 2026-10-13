"""Replace the base of a Gridfinity bin STL."""

from importlib.metadata import version

__version__ = version("gridfinity-rebase")


class RebaseError(ValueError):
    """Invalid geometry or an unsupported replacement."""
