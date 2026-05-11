"""Futures curve computations: calendar spreads and CL-CO by expiry.

NOTE: EIA does not publish futures curve settlements by expiry. These functions
return empty placeholders so the dashboard can render a "Future expansion"
state. Hook in a CME / ICE settlement source to populate.
"""
from __future__ import annotations

import pandas as pd

CALENDAR_TENORS = ["M1-M2", "M1-M3", "M1-M6", "M1-M12"]
CLCO_TENORS = ["M1", "M2", "M3", "M4", "M5", "M6"]


def compute_calendar_spreads(prices_df: pd.DataFrame | None) -> pd.DataFrame:
    """Return DataFrame with columns [tenor, value].

    FUTURE EXPANSION: requires WTI futures settlement curve from CME (e.g. via
    NYMEX CL contracts). EIA spot price alone cannot derive M1-M2/M3/M6/M12.
    Returns empty values so the chart renders as a placeholder.
    """
    return pd.DataFrame({"tenor": CALENDAR_TENORS, "value": [None] * len(CALENDAR_TENORS)})


def compute_clco_by_expiry(
    wti_df: pd.DataFrame | None, brent_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Return DataFrame with columns [tenor, value] for M1..M6 CL-CO spread.

    FUTURE EXPANSION: requires ICE Brent + NYMEX WTI settlement curves by expiry.
    Returns empty placeholder.
    """
    return pd.DataFrame({"tenor": CLCO_TENORS, "value": [None] * len(CLCO_TENORS)})
