"""Forward curve analysis charts."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS, base_layout, empty_figure


def curve_line(df: pd.DataFrame, title: str) -> go.Figure:
    """Render a configured FCA curve in listed tenor order."""
    if df.empty:
        return empty_figure(f"Configure {title.lower()} instruments")

    available = df.dropna(subset=["price"])
    if available.empty:
        fig = empty_figure("Waiting for live L1 snapshots")
        fig.update_layout(title=dict(text=title, font=dict(size=13)))
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=available["tenor"],
            y=available["price"],
            mode="lines+markers",
            line=dict(color=COLORS["accent"], width=2.5),
            marker=dict(
                size=8,
                color=COLORS["accent"],
                line=dict(color=COLORS["text"], width=1),
            ),
            customdata=available[
                ["instrument_id", "bid", "ask", "trade", "price_source", "state"]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Price: %{y:.4f}<br>"
                "Instrument: %{customdata[0]}<br>"
                "Bid: %{customdata[1]}<br>"
                "Ask: %{customdata[2]}<br>"
                "Trade: %{customdata[3]}<br>"
                "Source: %{customdata[4]}<br>"
                "State: %{customdata[5]}<extra></extra>"
            ),
            name=title,
        )
    )

    missing = int(df["price"].isna().sum())
    if missing:
        fig.add_annotation(
            text=f"{missing} configured instruments missing prices",
            xref="paper",
            yref="paper",
            x=1,
            y=1.12,
            showarrow=False,
            font=dict(color=COLORS["text_muted"], size=11),
            xanchor="right",
        )

    fig.update_layout(
        **base_layout(
            title=dict(text=title, font=dict(size=13)),
            xaxis=dict(
                title="Delivery month",
                gridcolor=COLORS["border"],
                categoryorder="array",
                categoryarray=df["tenor"].tolist(),
            ),
            yaxis=dict(title="Price", gridcolor=COLORS["border"]),
            showlegend=False,
        )
    )
    return fig
