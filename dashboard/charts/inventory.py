"""Cushing inventory charts."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def cushing_vs_5yr(df: pd.DataFrame) -> go.Figure:
    """Area chart with 5-yr min/max band, 5-yr median dashed, current year accent."""
    if df.empty or "stocks_kbbl" not in df.columns:
        return empty_figure()

    work = df.copy()
    work["year"] = work["date"].dt.year
    work["week"] = work["date"].dt.isocalendar().week.astype(int)
    latest_year = int(work["year"].max())
    history = work[work["year"].between(latest_year - 5, latest_year - 1)]

    if history.empty:
        return empty_figure("Not enough history for 5-yr band")

    band = (
        history.groupby("week")["stocks_kbbl"]
        .agg(["min", "max", "median"])
        .reset_index()
        .sort_values("week")
    )
    current = (
        work[work["year"] == latest_year]
        .groupby("week")["stocks_kbbl"]
        .mean()
        .reset_index()
        .sort_values("week")
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=band["week"],
            y=band["max"],
            mode="lines",
            line=dict(color="rgba(224,123,57,0.0)"),
            name="5yr max",
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=band["week"],
            y=band["min"],
            mode="lines",
            line=dict(color="rgba(224,123,57,0.0)"),
            fill="tonexty",
            fillcolor="rgba(224,123,57,0.18)",
            name="5yr min-max",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=band["week"],
            y=band["median"],
            mode="lines",
            line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
            name="5yr median",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=current["week"],
            y=current["stocks_kbbl"],
            mode="lines",
            line=dict(color=COLORS["accent"], width=2.5),
            name=f"{latest_year}",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Cushing stocks vs 5yr range", font=dict(size=13)),
            xaxis=dict(title="Week of year", gridcolor=COLORS["border"]),
            yaxis=dict(title="kbbl", gridcolor=COLORS["border"]),
        )
    )
    return fig


def cushing_wow(df: pd.DataFrame, lookback_weeks: int = 26) -> go.Figure:
    """Bar chart of week-over-week changes, green for draws, red for builds."""
    if df.empty or "stocks_kbbl" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(lookback_weeks + 1).copy()
    work["wow"] = work["stocks_kbbl"].diff()
    work = work.dropna(subset=["wow"])
    if work.empty:
        return empty_figure()
    colors = [COLORS["bull"] if v < 0 else COLORS["bear"] for v in work["wow"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=work["date"],
                y=work["wow"],
                marker_color=colors,
                name="WoW change",
            )
        ]
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Cushing WoW change", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="Δ kbbl", gridcolor=COLORS["border"], zerolinecolor=COLORS["text_muted"]),
            showlegend=False,
        )
    )
    return fig


def spr_stocks(df: pd.DataFrame, weeks: int = 104) -> go.Figure:
    if df.empty or "spr_stocks_kbbl" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(weeks).copy()
    work["rolling4"] = work["spr_stocks_kbbl"].rolling(4, min_periods=2).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=work["date"],
            y=work["spr_stocks_kbbl"],
            mode="lines",
            line=dict(color=COLORS["accent"], width=2.5),
            name="Weekly",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"],
            y=work["rolling4"],
            mode="lines",
            line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
            name="4W avg",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="SPR stocks", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="kbbl", gridcolor=COLORS["border"]),
        )
    )
    return fig
