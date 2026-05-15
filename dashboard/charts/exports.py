"""Crude exports chart."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def exports(df: pd.DataFrame, weeks: int = 104) -> go.Figure:
    if df.empty or "exports_kbbl_d" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(weeks).copy()
    work["rolling4"] = work["exports_kbbl_d"].rolling(4, min_periods=2).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["exports_kbbl_d"], mode="lines",
            line=dict(color=COLORS["accent"], width=2), name="Weekly",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["rolling4"], mode="lines",
            line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
            name="4W avg",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Crude exports", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="kbbl/d", gridcolor=COLORS["border"]),
        )
    )
    return fig


def imports(df: pd.DataFrame, weeks: int = 104) -> go.Figure:
    if df.empty or "imports_kbbl_d" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").tail(weeks).copy()
    work["rolling4"] = work["imports_kbbl_d"].rolling(4, min_periods=2).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["imports_kbbl_d"], mode="lines",
            line=dict(color=COLORS["accent"], width=2), name="Weekly",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=work["date"], y=work["rolling4"], mode="lines",
            line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
            name="4W avg",
        )
    )
    fig.update_layout(
        **base_layout(
            title=dict(text="Crude imports", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="kbbl/d", gridcolor=COLORS["border"]),
        )
    )
    return fig
