"""Errors shared by the library and command-line adapter."""

from collections.abc import Mapping
from typing import Any


class RebaseError(ValueError):
    """An expected failure, with a stable code and machine-readable details."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_geometry",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})
