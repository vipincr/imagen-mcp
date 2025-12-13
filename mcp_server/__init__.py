"""Public API re-exporting the shared implementation."""
from __future__ import annotations

import image_generator as _common

__all__ = getattr(_common, "__all__", [])


def __getattr__(name: str):
    return getattr(_common, name)
