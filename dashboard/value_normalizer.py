"""
Safe Value Normalizer for Numeric & String Fields.

Provides resilient numeric parsers that convert NaN, Infinity, and unparseable
values to None without corrupting class labels or raising uncaught exceptions.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple, Union

CLASS_LABELS = {
    "web",
    "video",
    "messaging",
    "voip",
    "file transfer",
    "other",
    "bulk_streaming",
    "interactive",
    "unknown",
    "—",
    "-",
    "n/a",
    "none",
    "null",
}


def is_class_label(value: Any) -> bool:
    """Checks whether the value represents a categorical traffic class label."""
    if value is None:
        return False
    return str(value).strip().lower() in CLASS_LABELS


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely converts a value to float.

    Rules:
    - Normal numeric float/int -> float
    - Numeric string (e.g. "123.45") -> float
    - float("nan"), float("inf"), float("-inf") -> default (None)
    - Categorical class strings (e.g. "Messaging", "Video") -> default (None)
    - None or empty string -> default (None)
    """
    if value is None or value == "":
        return default

    # If it is a string class label, never parse as numeric
    if isinstance(value, str):
        val_str = value.strip().lower()
        if val_str in CLASS_LABELS or val_str in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
            return default

    try:
        f_val = float(value)
        if math.isnan(f_val) or math.isinf(f_val):
            return default
        return f_val
    except (ValueError, TypeError, OverflowError):
        return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Safely converts a value to integer.

    Rules:
    - Normal numeric float/int -> int
    - Numeric string -> int
    - NaN / Inf / unparseable / class labels -> default (None)
    """
    if value is None or value == "":
        return default

    if isinstance(value, str):
        val_str = value.strip().lower()
        if val_str in CLASS_LABELS or val_str in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
            return default

    try:
        f_val = float(value)
        if math.isnan(f_val) or math.isinf(f_val):
            return default
        return int(f_val)
    except (ValueError, TypeError, OverflowError):
        return default
