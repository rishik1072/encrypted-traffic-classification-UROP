"""
Training package initialization.

Keep lightweight to avoid circular import side effects and RuntimeWarnings when invoking
submodules directly via `python -m training.<submodule>`.
"""

from __future__ import annotations

__all__ = []
