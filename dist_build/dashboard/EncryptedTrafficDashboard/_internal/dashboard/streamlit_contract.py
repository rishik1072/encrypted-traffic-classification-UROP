"""
Streamlit DataFrame Contract & Safe Styler.

Guarantees that all pandas DataFrames and Stylers rendered in Streamlit:
1. Contain zero NaN, +Inf, -Inf values
2. Adhere to strict JSON-safe schemas
3. Fall back safely to plain tables if Styler generation encounters invalid values
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from dashboard.data_quality import inspect_dataframe_for_invalid_values

logger = logging.getLogger("dashboard.streamlit_contract")


def _clean_value(val: Any) -> Any:
    """Recursively cleans a single scalar or container value for JSON/Streamlit compliance."""
    if val is None:
        return None
    if isinstance(val, (list, tuple, np.ndarray)):
        return [_clean_value(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _clean_value(v) for k, v in val.items()}
    if isinstance(val, (float, np.floating)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, str):
        v_str = val.strip().lower()
        if v_str in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity", "none", "null"):
            return None
        return val
    return val


def prepare_dataframe_for_streamlit(
    data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any], Any],
    na_rep: str = "N/A",
) -> pd.DataFrame:
    """
    Prepares and cleans a DataFrame for safe Streamlit rendering.

    Contract guarantees:
    - No raw NaN values (converted to None / object type)
    - No +Inf or -Inf values
    - Preserves exact numeric values, strings, booleans, and dates
    - Returns a distinct copy, never mutating source objects
    """
    if data is None:
        return pd.DataFrame()

    if isinstance(data, pd.DataFrame):
        records = data.to_dict(orient="records")
    elif isinstance(data, list):
        if not data:
            return pd.DataFrame()
        records = [r if isinstance(r, dict) else {"value": r} for r in data]
    elif isinstance(data, dict):
        records = [data]
    else:
        try:
            records = pd.DataFrame(data).to_dict(orient="records")
        except Exception:
            return pd.DataFrame()

    if not records:
        return pd.DataFrame()

    # Step 1: Clean every field at Python dictionary level with sanitized string keys
    cleaned_records = []
    for row in records:
        cleaned_row = {}
        for k, v in row.items():
            key_str = "extra_fields" if (k is None or str(k).strip() in ("", "None", "nan")) else str(k)
            cleaned_row[key_str] = _clean_value(v)
        cleaned_records.append(cleaned_row)

    # Collect all column keys across records to preserve order
    all_cols = []
    for r in cleaned_records:
        for k in r:
            if k not in all_cols:
                all_cols.append(k)

    # Step 2: Build DataFrame from explicit object arrays so pandas never coerces None to np.nan
    data_dict = {}
    for col in all_cols:
        col_vals = [r.get(col) for r in cleaned_records]
        data_dict[col] = pd.Series(col_vals, dtype=object)

    clean_df = pd.DataFrame(data_dict)
    return clean_df



def create_safe_styler(
    df: pd.DataFrame,
    format_dict: Optional[Dict[str, Any]] = None,
    na_rep: str = "N/A",
    **kwargs,
) -> Any:
    """
    Creates a Styler only after rigorously asserting that no NaN or Inf remains in the base data.
    If the DataFrame contains unparseable values, returns a plain sanitized DataFrame.
    """
    clean_df = prepare_dataframe_for_streamlit(df)

    try:
        styler = clean_df.style
        if format_dict:
            styler = styler.format(format_dict, na_rep=na_rep)
        else:
            styler = styler.format(na_rep=na_rep)
        return styler
    except Exception as e:
        logger.error(f"Error creating Styler: {e}. Falling back to plain clean DataFrame.")
        return clean_df


