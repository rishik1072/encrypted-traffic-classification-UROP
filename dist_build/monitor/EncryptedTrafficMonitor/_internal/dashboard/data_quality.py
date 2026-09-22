"""
Data Quality Diagnostics for Dashboard & DataFrames.

Inspects dataframes and data objects for NaN, Infinity, and malformed values.
"""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import pandas as pd


def inspect_dataframe_for_invalid_values(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Inspects a DataFrame for NaN, +Inf, and -Inf values across columns.

    Returns:
        {
            "total_invalid_count": int,
            "columns": {
                "<col_name>": {
                    "nan_count": int,
                    "inf_count": int,
                    "neg_inf_count": int,
                    "dtype": str,
                }
            }
        }
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"total_invalid_count": 0, "columns": {}}

    total_invalid = 0
    column_reports = {}

    for col in df.columns:
        series = df[col]
        nan_cnt = int(series.isna().sum())
        
        inf_cnt = 0
        neg_inf_cnt = 0
        # If numeric dtype or object containing numeric types
        try:
            numeric_vals = pd.to_numeric(series, errors="coerce")
            inf_cnt = int((numeric_vals == np.inf).sum())
            neg_inf_cnt = int((numeric_vals == -np.inf).sum())
        except Exception:
            pass

        col_invalid = nan_cnt + inf_cnt + neg_inf_cnt
        total_invalid += col_invalid

        column_reports[col] = {
            "nan_count": nan_cnt,
            "inf_count": inf_cnt,
            "neg_inf_count": neg_inf_cnt,
            "total_invalid": col_invalid,
            "dtype": str(series.dtype),
        }

    return {
        "total_invalid_count": total_invalid,
        "columns": column_reports,
    }


def format_invalid_values_diagnostic(report: Dict[str, Any]) -> str:
    """Formats the inspection report as human-readable diagnostic text."""
    lines = [
        "INVALID VALUES DIAGNOSTIC",
        "-------------------------",
        f"Total Invalid Values: {report.get('total_invalid_count', 0)}",
    ]
    cols = report.get("columns", {})
    for col, stats in cols.items():
        if stats.get("total_invalid", 0) > 0:
            lines.append(f"\n<{col}> (dtype={stats.get('dtype')}):")
            lines.append(f"  NaN  = {stats.get('nan_count', 0)}")
            lines.append(f"  +Inf = {stats.get('inf_count', 0)}")
            lines.append(f"  -Inf = {stats.get('neg_inf_count', 0)}")

    return "\n".join(lines)
