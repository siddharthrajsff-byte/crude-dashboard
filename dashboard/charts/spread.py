"""WTI-Brent (CL-CO) spread analysis charts."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def spread_vs_seasonal(
    spread_df: pd.DataFrame, bands_df: pd.DataFrame
) -> go.Figure:
    """Overlay current year spread on 10-90 percentile seasonal envelope."""
    if spread_df.empty or bands_df.empty:
        return empty_figure()

    bands = bands_df.sort_values("week")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=bands["week"], y=bands["p90"], mode="lines",
            line=dict(color="rgba(224,123,57,0)"), showlegend=False, hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=bands["week"], y=bands["p10"], mode="lines",
            line=dict(color="rgba(224,123,57,0)"),
            fill="tonexty", fillcolor="rgba(224,123,57,0.15)",
            name="10-90 pctile", hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=bands["week"], y=bands["p50"], mode="lines",
            line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
            name="5yr median",
        )
    )

    work = spread_df.copy()
    work["year"] = work["date"].dt.year
    work["week"] = work["date"].dt.isocalendar().week.astype(int)
    latest_year = int(work["year"].max())
    current = (
        work[work["year"] == latest_year]
        .groupby("week")["spread"].mean().reset_index().sort_values("week")
    )
    fig.add_trace(
        go.Scatter(
            x=current["week"], y=current["spread"], mode="lines",
            line=dict(color=COLORS["accent"], width=2.5), name=f"{latest_year}",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="CL-CO spread vs seasonal", font=dict(size=13)),
            xaxis=dict(title="Week of year", gridcolor=COLORS["border"]),
            yaxis=dict(title="$/bbl", gridcolor=COLORS["border"]),
        )
    )
    return fig


def zscore(df: pd.DataFrame) -> go.Figure:
    """Z-score line with ±1σ / ±2σ reference lines and signed area fill."""
    if df.empty or "zscore" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(500).copy()
    pos = work["zscore"].clip(lower=0)
    neg = work["zscore"].clip(upper=0)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=pos, mode="lines",
            line=dict(color="rgba(76,175,125,0.0)"),
            fill="tozeroy", fillcolor="rgba(76,175,125,0.25)",
            name="Above 0", hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=neg, mode="lines",
            line=dict(color="rgba(224,82,82,0.0)"),
            fill="tozeroy", fillcolor="rgba(224,82,82,0.25)",
            name="Below 0", hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["zscore"], mode="lines",
            line=dict(color=COLORS["accent"], width=2),
            name="Z-score",
        )
    )
    for level, dash in [(2, "dot"), (1, "dash"), (-1, "dash"), (-2, "dot")]:
        fig.add_hline(
            y=level,
            line=dict(color=COLORS["text_muted"], dash=dash, width=1),
            opacity=0.6,
        )
    fig.update_layout(
        **base_layout(
            title=dict(text="Spread rolling z-score", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="σ", gridcolor=COLORS["border"], zerolinecolor=COLORS["text_muted"]),
        )
    )
    return fig


def calendar_spreads_bar(curve_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar — WTI calendar spreads centered at 0.

    Renders empty placeholder when values are None (no futures data available).
    """
    if curve_df is None or curve_df.empty or curve_df["value"].isna().all():
        fig = go.Figure()
        fig.update_layout(
            **base_layout(
                title=dict(text="WTI calendar spreads", font=dict(size=13)),
                xaxis=dict(visible=False), yaxis=dict(visible=False),
            )
        )
        fig.add_annotation(
            text="Future expansion — requires CME WTI settlement curve",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(color=COLORS["text_muted"], size=12),
        )
        return fig

    colors = [COLORS["bull"] if (v or 0) > 0 else COLORS["bear"] for v in curve_df["value"]]
    fig = go.Figure(
        data=[
            go.Bar(
                x=curve_df["value"], y=curve_df["tenor"], orientation="h",
                marker_color=colors,
            )
        ]
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="WTI calendar spreads", font=dict(size=13)),
            xaxis=dict(title="$/bbl", gridcolor=COLORS["border"], zerolinecolor=COLORS["text_muted"]),
            yaxis=dict(gridcolor=COLORS["border"], autorange="reversed"),
            showlegend=False,
        )
    )
    return fig


def clco_by_expiry_bar(curve_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar — CL-CO spread M1..M6."""
    if curve_df is None or curve_df.empty or curve_df["value"].isna().all():
        fig = go.Figure()
        fig.update_layout(
            **base_layout(
                title=dict(text="CL-CO spread by expiry", font=dict(size=13)),
                xaxis=dict(visible=False), yaxis=dict(visible=False),
            )
        )
        fig.add_annotation(
            text="Future expansion — requires ICE Brent + NYMEX WTI curves",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(color=COLORS["text_muted"], size=12),
        )
        return fig

    colors = [COLORS["bull"] if (v or 0) > 0 else COLORS["bear"] for v in curve_df["value"]]
    fig = go.Figure(
        data=[
            go.Bar(
                x=curve_df["value"], y=curve_df["tenor"], orientation="h",
                marker_color=colors,
            )
        ]
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="CL-CO spread by expiry", font=dict(size=13)),
            xaxis=dict(title="$/bbl", gridcolor=COLORS["border"], zerolinecolor=COLORS["text_muted"]),
            yaxis=dict(gridcolor=COLORS["border"], autorange="reversed"),
            showlegend=False,
        )
    )
    return fig
