"""US crude production chart."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def production_trend(df: pd.DataFrame, weeks: int = 52) -> go.Figure:
    """Line chart of last `weeks` of production, with prior-year overlay."""
    if df.empty or "production_kbbl_d" not in df.columns:
        return empty_figure()

    work = df.sort_values("date").copy()
    recent = work.tail(weeks)
    prior = work.iloc[-weeks * 2 : -weeks] if len(work) >= weeks * 2 else pd.DataFrame()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recent["date"],
            y=recent["production_kbbl_d"],
            mode="lines",
            line=dict(color=COLORS["accent"], width=2.5),
            name="Current",
        )
    )
    if not prior.empty:
        offset = (recent["date"].iloc[0] - prior["date"].iloc[0])
        prior_dates = prior["date"] + offset
        fig.add_trace(
            go.Scatter(
                x=prior_dates,
                y=prior["production_kbbl_d"].values,
                mode="lines",
                line=dict(color=COLORS["text_muted"], dash="dash", width=1.5),
                name="Year ago",
            )
        )

    fig.update_layout(
        **base_layout(
            title=dict(text="US crude production", font=dict(size=13)),
            xaxis=dict(title="", gridcolor=COLORS["border"]),
            yaxis=dict(title="kbbl/d", gridcolor=COLORS["border"]),
        )
    )
    return fig
