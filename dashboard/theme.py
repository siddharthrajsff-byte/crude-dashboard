"""Shared color palette and Plotly layout defaults."""
from __future__ import annotations

import plotly.graph_objects as go

COLORS = {
    "bg": "#1a1a1a",
    "surface": "#242424",
    "border": "#2e2e2e",
    "accent": "#e07b39",
    "accent_muted": "#a85a22",
    "text": "#f0f0f0",
    "text_muted": "#9a9a9a",
    "bull": "#4caf7d",
    "bear": "#e05252",
    "neutral": "#6b7280",
}

CHART_MARGIN = dict(l=40, r=20, t=30, b=40)


def base_layout(**overrides) -> dict:
    """Common Plotly layout used by every chart."""
    layout = dict(
        template="plotly_dark",
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"], size=11),
        margin=CHART_MARGIN,
        xaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
        yaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
    )
    layout.update(overrides)
    return layout


def empty_figure(message: str = "No data — click Refresh") -> go.Figure:
    """Render an empty styled figure with a centered annotation."""
    fig = go.Figure()
    fig.update_layout(
        **base_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
    )
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=13),
    )
    return fig
