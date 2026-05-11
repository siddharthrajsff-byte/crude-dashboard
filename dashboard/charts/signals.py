"""Trade signal summary panel — rendered as DMC components (not Plotly)."""
from __future__ import annotations

import dash_mantine_components as dmc
from dash import html

from compute.signals import signal_label
from dashboard.theme import COLORS

FACTORS = [
    ("cushing_signal",        "Cushing inventories", "Bullish WTI", "Bearish WTI"),
    ("production_signal",     "US production",       "Bullish WTI", "Bearish WTI"),
    ("refinery_signal",       "Refinery utilization","Strong demand","Weak demand"),
    ("export_signal",         "Crude exports",       "Bullish WTI", "Bearish WTI"),
    ("spread_zscore_signal",  "CL-CO spread (z)",    "WTI cheap",   "WTI rich"),
    ("curve_signal",          "Curve structure",     "Backwardation","Contango"),
]


def _bar(score: float) -> html.Div:
    """A horizontal bar centered at 0, filling left (red) or right (green)."""
    pct = max(min(score, 1.0), -1.0) * 50  # half-width
    color = COLORS["bull"] if score > 0 else COLORS["bear"] if score < 0 else COLORS["neutral"]
    if pct >= 0:
        left = 50
        width = pct
    else:
        left = 50 + pct
        width = -pct
    return html.Div(
        style={
            "position": "relative",
            "height": "10px",
            "backgroundColor": COLORS["bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "5px",
            "overflow": "hidden",
        },
        children=[
            html.Div(
                style={
                    "position": "absolute",
                    "left": "50%",
                    "top": 0,
                    "bottom": 0,
                    "width": "1px",
                    "backgroundColor": COLORS["text_muted"],
                }
            ),
            html.Div(
                style={
                    "position": "absolute",
                    "left": f"{left}%",
                    "width": f"{width}%",
                    "top": 0,
                    "bottom": 0,
                    "backgroundColor": color,
                    "opacity": 0.85,
                }
            ),
        ],
    )


def signal_panel(signals: dict[str, float]) -> dmc.Card:
    rows = []
    for key, label, bull, bear in FACTORS:
        score = float(signals.get(key, 0.0) or 0.0)
        text = signal_label(score, bull, bear)
        text_color = (
            COLORS["bull"] if score > 0.25
            else COLORS["bear"] if score < -0.25
            else COLORS["text_muted"]
        )
        rows.append(
            dmc.Grid(
                gutter="sm",
                align="center",
                children=[
                    dmc.GridCol(
                        dmc.Text(label, c=COLORS["text"], size="sm"),
                        span=3,
                    ),
                    dmc.GridCol(_bar(score), span=6),
                    dmc.GridCol(
                        dmc.Text(text, c=text_color, size="sm", fw=600, ta="right"),
                        span=3,
                    ),
                ],
            )
        )
    return dmc.Card(
        withBorder=True,
        radius="md",
        style={
            "backgroundColor": COLORS["surface"],
            "borderColor": COLORS["border"],
        },
        children=[
            dmc.Text(
                "Trade signal summary",
                c=COLORS["text"], size="md", fw=600, mb="sm",
            ),
            dmc.Stack(rows, gap="xs"),
        ],
    )
