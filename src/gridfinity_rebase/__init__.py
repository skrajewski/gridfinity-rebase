"""Public library API for replacing the base of a Gridfinity bin STL.

Geometry imports are lazy: presets and options do not load the native engine.
"""

from importlib import import_module
from importlib.metadata import version
from typing import TYPE_CHECKING

from .catalog import Preset, list_presets, resolve_options
from .errors import RebaseError
from .options import BaseOptions

__version__ = version("gridfinity-rebase")

_API_EXPORTS = (
    "Model",
    "Inspection",
    "GeneratedBase",
    "DonorBase",
    "ProgressEvent",
    "ProgressStage",
    "RebaseReport",
    "RebaseResult",
    "load_stl",
    "inspect_model",
    "rebase",
    "save_stl",
)

__all__ = [
    "BaseOptions",
    "DonorBase",
    "GeneratedBase",
    "Inspection",
    "Model",
    "Preset",
    "ProgressEvent",
    "ProgressStage",
    "RebaseError",
    "RebaseReport",
    "RebaseResult",
    "__version__",
    "inspect_model",
    "list_presets",
    "load_stl",
    "rebase",
    "resolve_options",
    "save_stl",
]

if TYPE_CHECKING:
    from .api import (
        DonorBase,
        GeneratedBase,
        Inspection,
        Model,
        ProgressEvent,
        ProgressStage,
        RebaseReport,
        RebaseResult,
        inspect_model,
        load_stl,
        rebase,
        save_stl,
    )


def __getattr__(name: str):
    if name in _API_EXPORTS:
        api = import_module(".api", __name__)
        globals().update({export: getattr(api, export) for export in _API_EXPORTS})
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
