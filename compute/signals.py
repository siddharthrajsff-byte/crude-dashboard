"""Signal computations: z-scores, seasonal envelopes, trade signal scoring."""
from __future__ import annotations

import numpy as np
import pandas as pd

PERCENTILES = [0.10, 0.25, 0.50, 0.75, 0.90]


def compute_zscore(series: pd.Series, window: int = 52) -> pd.Series:
    """Rolling z-score with look-ahead bias removed.

    Uses shift(1) on both mean and std so the value at t is compared against
    statistics computed from observations strictly prior to t.
    """
    s = pd.to_numeric(series, errors="coerce")
    rolling = s.rolling(window=window, min_periods=max(5, window // 4))
    mean = rolling.mean().shift(1)
    std = rolling.std().shift(1)
    z = (s - mean) / std.replace(0, np.nan)
    return z


def compute_seasonal_bands(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Percentile envelope by week-of-year using the most recent 5 complete years.

    Returns columns: week, p10, p25, p50, p75, p90, current.
    `current` is the value from the latest available calendar year, aligned by week.
    """
    if df.empty or value_col not in df.columns:
        return pd.DataFrame(
            columns=["week", "p10", "p25", "p50", "p75", "p90", "current"]
        )

    work = df[["date", value_col]].copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.dropna(subset=[value_col]).sort_values("date")
    work["year"] = work["date"].dt.isocalendar().year.astype(int)
    work["week"] = work["date"].dt.isocalendar().week.astype(int)

    latest_year = int(work["year"].max())
    history_years = list(range(latest_year - 5, latest_year))
    hist = work[work["year"].isin(history_years)]
    if hist.empty:
        hist = work[work["year"] < latest_year]

    grouped = (
        hist.groupby("week")[value_col]
        .quantile(PERCENTILES)
        .unstack(level=-1)
        .rename(columns={p: f"p{int(p * 100)}" for p in PERCENTILES})
        .reset_index()
    )

    current = (
        work[work["year"] == latest_year]
        .groupby("week")[value_col]
        .mean()
        .rename("current")
        .reset_index()
    )

    out = grouped.merge(current, on="week", how="left").sort_values("week")
    return out.reset_index(drop=True)


def _last_change(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return None
    return float(s.iloc[-1] - s.iloc[-2])


def _normalize(value: float | None, scale: float) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return float(np.clip(value / scale, -1.0, 1.0))


def compute_trade_signals(all_data: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Aggregate signal score per factor in [-1, +1]; +1 bullish, -1 bearish.

    Mapping (sign convention from a WTI long perspective):
      cushing_signal     : negative WoW (draw) -> bullish (+)
      production_signal  : negative WoW        -> bullish (+)
      refinery_signal    : utilization above 5yr avg -> bullish (+)
      export_signal      : exports above 4W avg trend -> bullish (+)
      spread_zscore_signal : spread z-score; positive z (WTI rich) -> bearish WTI (-)
      curve_signal       : positive (backwardation) -> bullish (+)
    """
    signals: dict[str, float] = {
        "cushing_signal": 0.0,
        "production_signal": 0.0,
        "refinery_signal": 0.0,
        "export_signal": 0.0,
        "spread_zscore_signal": 0.0,
        "curve_signal": 0.0,
    }

    cushing = all_data.get("cushing_stocks")
    if cushing is not None and not cushing.empty:
        wow = _last_change(cushing["stocks_kbbl"])
        signals["cushing_signal"] = _normalize(-(wow or 0.0), scale=2000.0)

    prod = all_data.get("us_production")
    if prod is not None and not prod.empty:
        wow = _last_change(prod["production_kbbl_d"])
        signals["production_signal"] = _normalize(-(wow or 0.0), scale=200.0)

    refinery = all_data.get("refinery_util")
    if refinery is not None and not refinery.empty:
        s = pd.to_numeric(refinery["utilization_pct"], errors="coerce").dropna()
        if len(s) >= 52:
            recent = s.iloc[-1]
            avg5y = s.iloc[-min(len(s), 5 * 52):].mean()
            signals["refinery_signal"] = _normalize(recent - avg5y, scale=5.0)

    exp = all_data.get("crude_exports")
    if exp is not None and not exp.empty:
        s = pd.to_numeric(exp["exports_kbbl_d"], errors="coerce").dropna()
        if len(s) >= 8:
            recent4 = s.iloc[-4:].mean()
            prior4 = s.iloc[-8:-4].mean()
            signals["export_signal"] = _normalize(recent4 - prior4, scale=300.0)

    spread_z = all_data.get("spread_zscore")
    if spread_z is not None and not spread_z.empty and "zscore" in spread_z.columns:
        latest_z = pd.to_numeric(spread_z["zscore"], errors="coerce").dropna()
        if not latest_z.empty:
            signals["spread_zscore_signal"] = _normalize(-latest_z.iloc[-1], scale=2.0)

    # curve_signal left at 0.0: requires futures curve data not in EIA.
    # FUTURE EXPANSION: compute from CME WTI settlements (M1-M2).

    return signals


def signal_label(score: float, bullish_text: str, bearish_text: str) -> str:
    """Convert a [-1, 1] score to a human label."""
    if score > 0.25:
        return bullish_text
    if score < -0.25:
        return bearish_text
    return "Neutral"
