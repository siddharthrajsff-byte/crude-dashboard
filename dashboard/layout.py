"""Top-level page layout."""
from __future__ import annotations

import dash_mantine_components as dmc
from dash import dcc, html

from dashboard.theme import COLORS


def _card(children, **kwargs) -> dmc.Card:
    style = {
        "backgroundColor": COLORS["surface"],
        "borderColor": COLORS["border"],
        "height": "100%",
    }
    style.update(kwargs.pop("style", {}) or {})
    return dmc.Card(
        withBorder=True, radius="md", padding="sm",
        style=style, children=children, **kwargs,
    )


def _metric_card(card_id: str) -> dmc.Card:
    """Metric card placeholder; content populated by callback."""
    return dmc.Card(
        id=card_id,
        withBorder=True, radius="md", padding="md",
        style={
            "backgroundColor": COLORS["surface"],
            "borderColor": COLORS["border"],
            "minHeight": "100px",
        },
        children=[dmc.Text("...", c=COLORS["text_muted"], size="sm")],
    )


def _chart_card(graph_id: str, height: int = 320) -> dmc.Card:
    return _card(
        children=[
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": False},
                style={"height": f"{height}px"},
            )
        ]
    )


def build_layout() -> html.Div:
    return html.Div(
        style={
            "backgroundColor": COLORS["bg"],
            "color": COLORS["text"],
            "minHeight": "100vh",
            "padding": "0",
        },
        children=[
            dcc.Store(id="data-loaded", data=False),
            dcc.Interval(id="initial-load", interval=300, n_intervals=0, max_intervals=1),

            # Accent top strip
            html.Div(style={"height": "3px", "backgroundColor": COLORS["accent"]}),

            # Header
            dmc.Group(
                justify="space-between",
                align="center",
                px="lg",
                py="md",
                style={
                    "backgroundColor": COLORS["surface"],
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
                children=[
                    dmc.Stack(gap=2, children=[
                        dmc.Text(
                            "Crude Oil Trading Dashboard",
                            c=COLORS["text"], size="xl", fw=700,
                        ),
                        dmc.Text(
                            id="last-updated",
                            c=COLORS["text_muted"], size="xs",
                        ),
                    ]),
                    dmc.Group(gap="sm", children=[
                        dmc.Loader(id="refresh-loader", size="sm", color="orange",
                                   style={"display": "none"}),
                        dmc.Button(
                            "Refresh Data",
                            id="refresh-btn",
                            color="orange",
                            variant="filled",
                            radius="md",
                        ),
                    ]),
                ],
            ),

            html.Div(
                style={"padding": "16px"},
                children=[
                    # Signal Bar — 6 metric cards
                    dmc.Grid(gutter="md", children=[
                        dmc.GridCol(_metric_card("metric-cushing"), span=2),
                        dmc.GridCol(_metric_card("metric-production"), span=2),
                        dmc.GridCol(_metric_card("metric-refinery"), span=2),
                        dmc.GridCol(_metric_card("metric-exports"), span=2),
                        dmc.GridCol(_metric_card("metric-spread"), span=2),
                        dmc.GridCol(_metric_card("metric-zscore"), span=2),
                    ]),

                    dmc.Space(h="md"),

                    # Row 2: Inventory & Production — 3 cols
                    dmc.Grid(gutter="md", children=[
                        dmc.GridCol(_chart_card("chart-cushing-5yr"), span=4),
                        dmc.GridCol(_chart_card("chart-cushing-wow"), span=4),
                        dmc.GridCol(_chart_card("chart-production"), span=4),
                    ]),

                    dmc.Space(h="md"),

                    # Row 3: Refinery, Exports, Crack, Demand — 4 cols
                    dmc.Grid(gutter="md", children=[
                        dmc.GridCol(_chart_card("chart-refinery"), span=3),
                        dmc.GridCol(_chart_card("chart-exports"), span=3),
                        dmc.GridCol(_chart_card("chart-crack"), span=3),
                        dmc.GridCol(_chart_card("chart-demand"), span=3),
                    ]),

                    dmc.Space(h="md"),

                    # Row 4: CL-CO spread analysis — 2 cols
                    dmc.Grid(gutter="md", children=[
                        dmc.GridCol(_chart_card("chart-spread-seasonal", height=340), span=6),
                        dmc.GridCol(
                            html.Div(children=[
                                _chart_card("chart-zscore", height=260),
                                dmc.Space(h="xs"),
                                dmc.Card(
                                    withBorder=True, radius="md", padding="sm",
                                    style={
                                        "backgroundColor": COLORS["surface"],
                                        "borderColor": COLORS["border"],
                                    },
                                    children=[
                                        dmc.Text(
                                            "Current z-score position",
                                            c=COLORS["text_muted"], size="xs", mb=4,
                                        ),
                                        html.Div(id="zscore-gauge"),
                                    ],
                                ),
                            ]),
                            span=6,
                        ),
                    ]),

                    dmc.Space(h="md"),

                    # Row 5: Curve structure — 2 cols
                    dmc.Grid(gutter="md", children=[
                        dmc.GridCol(_chart_card("chart-calendar-spreads", height=260), span=6),
                        dmc.GridCol(_chart_card("chart-clco-expiry", height=260), span=6),
                    ]),

                    dmc.Space(h="md"),

                    # Row 6: Trade signal summary panel — full width
                    html.Div(id="signal-panel"),

                    dmc.Space(h="xl"),
                ],
            ),
        ],
    )
