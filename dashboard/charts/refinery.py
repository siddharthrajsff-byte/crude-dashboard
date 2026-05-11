"""Refinery utilization, crack spread, implied demand charts."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def utilization(df: pd.DataFrame) -> go.Figure:
    """Refinery utilization with 5yr min/max band."""
    if df.empty or "utilization_pct" not in df.columns:
        return empty_figure()

    work = df.copy()
    work["year"] = work["date"].dt.year
    work["week"] = work["date"].dt.isocalendar().week.astype(int)
    latest_year = int(work["year"].max())
    history = work[work["year"].between(latest_year - 5, latest_year - 1)]

    fig = go.Figure()
    if not history.empty:
        band = (
            history.groupby("week")["utilization_pct"]
            .agg(["min", "max"])
            .reset_index()
            .sort_values("week")
        )
        fig.add_trace(
            go.Scatter(
                x=band["week"], y=band["max"], mode="lines",
                line=dict(color="rgba(224,123,57,0)"), showlegend=False, hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=band["week"], y=band["min"], mode="lines",
                line=dict(color="rgba(224,123,57,0)"),
                fill="tonexty", fillcolor="rgba(224,123,57,0.18)",
                name="5yr min-max", hoverinfo="skip",
            )
        )
    current = work[work["year"] == latest_year].sort_values("week")
    fig.add_trace(
        go.Scatter(
            x=current["week"], y=current["utilization_pct"], mode="lines",
            line=dict(color=COLORS["accent"], width=2.5), name=f"{latest_year}",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Refinery utilization", font=dict(size=13)),
            xaxis=dict(title="Week of year", gridcolor=COLORS["border"]),
            yaxis=dict(title="% capacity", gridcolor=COLORS["border"]),
        )
    )
    return fig


def crack_spread_placeholder() -> go.Figure:
    """3-2-1 crack spread placeholder.

    FUTURE EXPANSION: requires product (gasoline + distillate) and WTI prices
    aligned at daily/weekly frequency from EIA petroleum/pri/spt for product
    codes EPMRR / EPD2DXL0 alongside WTI. Not yet wired.
    """
    fig = go.Figure()
    fig.update_layout(
        **base_layout(
            title=dict(text="3-2-1 crack spread", font=dict(size=13)),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
    )
    fig.add_annotation(
        text="Future expansion — requires CME RBOB / HO settlements",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(color=COLORS["text_muted"], size=12),
    )
    return fig


def implied_demand(df: pd.DataFrame) -> go.Figure:
    """Approximate implied crude demand using refinery utilization 4W avg."""
    if df.empty or "utilization_pct" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(104).copy()
    work["rolling4"] = work["utilization_pct"].rolling(4, min_periods=2).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["utilization_pct"], mode="lines",
            line=dict(color=COLORS["accent_muted"], width=1.5), name="Weekly",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["rolling4"], mode="lines",
            line=dict(color=COLORS["accent"], width=2.5), name="4W avg",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Implied crude demand (util proxy)", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="% capacity", gridcolor=COLORS["border"]),
        )
    )
    return fig
