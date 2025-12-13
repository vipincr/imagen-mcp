"""Thin wrapper to shared core implementation."""
from __future__ import annotations

from image_generator import core as _core

_state = _core._state  # pylint: disable=protected-access  # keep test access
__all__ = getattr(_core, "__all__", []) + ["_state"]


def __getattr__(name: str):
    return getattr(_core, name)
