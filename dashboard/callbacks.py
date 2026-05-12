"""Dash callbacks: load data, render charts and metric cards."""
from __future__ import annotations

import logging
from datetime import datetime

import dash_mantine_components as dmc
import pandas as pd
from dash import Input, Output, State, callback, ctx, html, no_update

from compute.curve import compute_calendar_spreads, compute_clco_by_expiry
from compute.signals import compute_trade_signals
from dashboard.charts import exports as exports_chart
from dashboard.charts import inventory, production, refinery, spread
from dashboard.charts.signals import signal_panel
from dashboard.theme import COLORS
from db.query import data_exists, load_all
from ingestion.fetch_all import fetch_all_now, last_updated
from ingestion.scheduler_status import get_status

logger = logging.getLogger(__name__)


# ---- helpers --------------------------------------------------------------


def _badge(text: str, kind: str) -> dmc.Badge:
    palette = {
        "bull": (COLORS["bull"], "#0f2a1d"),
        "bear": (COLORS["bear"], "#2a0f0f"),
        "neutral": (COLORS["text_muted"], "#222"),
    }
    fg, bg = palette.get(kind, palette["neutral"])
    return dmc.Badge(
        text, variant="filled", radius="sm",
        styles={"root": {"backgroundColor": bg, "color": fg, "border": f"1px solid {fg}"}},
    )


def _metric_card_content(
    label: str, value: str, sublabel: str, badge: dmc.Badge | None = None
) -> list:
    return [
        dmc.Text(label, c=COLORS["text_muted"], size="xs", tt="uppercase"),
        dmc.Space(h=4),
        dmc.Text(value, c=COLORS["text"], size="xl", fw=700),
        dmc.Space(h=4),
        dmc.Group(gap="xs", children=[
            dmc.Text(sublabel, c=COLORS["text_muted"], size="xs"),
            badge if badge is not None else html.Span(),
        ]),
    ]


def _fmt_num(x: float | None, fmt: str = "{:.0f}") -> str:
    if x is None or pd.isna(x):
        return "—"
    return fmt.format(x)


def _wow(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return None
    return float(s.iloc[-1] - s.iloc[-2])


def _gauge(zscore_value: float | None) -> html.Div:
    """Visual position on a -2..+2 scale."""
    if zscore_value is None or pd.isna(zscore_value):
        return html.Div(
            "No data",
            style={"color": COLORS["text_muted"], "fontSize": "12px"},
        )
    pos = max(min(zscore_value, 2.0), -2.0)
    left_pct = (pos + 2.0) / 4.0 * 100
    color = COLORS["bull"] if pos > 0 else COLORS["bear"] if pos < 0 else COLORS["text_muted"]
    return html.Div(
        style={"position": "relative", "height": "28px"},
        children=[
            html.Div(style={
                "position": "absolute",
                "left": 0, "right": 0, "top": "12px",
                "height": "4px",
                "background": f"linear-gradient(90deg, {COLORS['bear']} 0%, {COLORS['neutral']} 50%, {COLORS['bull']} 100%)",
                "borderRadius": "2px",
                "opacity": 0.6,
            }),
            html.Div(style={
                "position": "absolute",
                "left": f"calc({left_pct}% - 6px)",
                "top": "6px",
                "width": "12px", "height": "16px",
                "backgroundColor": color,
                "borderRadius": "3px",
                "border": f"2px solid {COLORS['text']}",
            }),
            html.Div("-2σ", style={
                "position": "absolute", "left": 0, "bottom": 0,
                "color": COLORS["text_muted"], "fontSize": "10px",
            }),
            html.Div("0", style={
                "position": "absolute", "left": "50%", "transform": "translateX(-50%)",
                "bottom": 0, "color": COLORS["text_muted"], "fontSize": "10px",
            }),
            html.Div("+2σ", style={
                "position": "absolute", "right": 0, "bottom": 0,
                "color": COLORS["text_muted"], "fontSize": "10px",
            }),
        ],
    )


def _format_status_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%a %H:%M ET")
    except ValueError:
        return value


def _status_badge(state: str) -> dmc.Badge:
    palette = {
        "running": (COLORS["accent"], "#332214", "Running"),
        "success": (COLORS["bull"], "#0f2a1d", "Complete"),
        "error": (COLORS["bear"], "#2a0f0f", "Failed"),
        "idle": (COLORS["text_muted"], "#222", "Idle"),
    }
    fg, bg, label = palette.get(state, palette["idle"])
    return dmc.Badge(
        label,
        variant="filled",
        radius="sm",
        styles={"root": {"backgroundColor": bg, "color": fg, "border": f"1px solid {fg}"}},
    )


def _job_status_chip(job: dict) -> dmc.Card:
    state = job.get("state", "idle")
    border = COLORS["accent"] if state == "running" else COLORS["bear"] if state == "error" else COLORS["border"]
    caption = job.get("message") or "Waiting for next run."
    if state in {"idle", "success"}:
        caption = f"Next: {_format_status_time(job.get('next_run_at'))}"
    if state == "success" and job.get("finished_at"):
        caption = f"Last complete: {_format_status_time(job.get('finished_at'))}"

    return dmc.Card(
        withBorder=True,
        radius="md",
        padding="xs",
        style={
            "backgroundColor": COLORS["bg"],
            "borderColor": border,
            "minWidth": "260px",
        },
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                gap="xs",
                children=[
                    dmc.Text(job.get("label", "Scheduled job"), c=COLORS["text"], size="xs", fw=700),
                    _status_badge(state),
                ],
            ),
            dmc.Text(caption, c=COLORS["text_muted"], size="xs", mt=4),
        ],
    )


def _scheduler_status_bar(status: dict) -> html.Div:
    jobs = status.get("jobs", {})
    running_jobs = [job for job in jobs.values() if job.get("state") == "running"]
    error_jobs = [job for job in jobs.values() if job.get("state") == "error"]

    if running_jobs:
        headline = running_jobs[0].get("message", "Scheduled data refresh in progress.")
        color = COLORS["accent"]
        bg = "#2d2118"
        loader = dmc.Loader(size="xs", color="orange")
    elif error_jobs:
        headline = error_jobs[0].get("message", "Scheduled data refresh failed.")
        color = COLORS["bear"]
        bg = "#2a1515"
        loader = html.Span()
    elif status.get("scheduler_running"):
        headline = "Scheduled data refresh is armed. WPSR runs at 10:30 ET; EIA API backfill runs at 11:30 ET."
        color = COLORS["bull"]
        bg = "#14241c"
        loader = html.Span()
    else:
        headline = "Scheduler status unavailable until the dashboard process starts APScheduler."
        color = COLORS["neutral"]
        bg = "#20232a"
        loader = html.Span()

    ordered_jobs = [
        jobs[key]
        for key in ("wpsr_realtime_refresh", "eia_api_historical_refresh")
        if key in jobs
    ]

    return html.Div(
        style={
            "backgroundColor": bg,
            "borderBottom": f"1px solid {COLORS['border']}",
            "boxShadow": "0 8px 24px rgba(0,0,0,0.18)",
            "padding": "10px 16px",
        },
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                gap="sm",
                children=[
                    dmc.Group(gap="xs", align="center", children=[
                        loader,
                        html.Div(
                            style={
                                "width": "8px",
                                "height": "8px",
                                "borderRadius": "50%",
                                "backgroundColor": color,
                                "boxShadow": f"0 0 12px {color}",
                            }
                        ),
                        dmc.Text(headline, c=COLORS["text"], size="sm", fw=600),
                    ]),
                    dmc.Text(
                        f"Status checked: {_format_status_time(status.get('updated_at'))}",
                        c=COLORS["text_muted"],
                        size="xs",
                    ),
                ],
            ),
            dmc.Space(h="xs"),
            dmc.Group(gap="sm", children=[_job_status_chip(job) for job in ordered_jobs]),
        ],
    )


# ---- callbacks ------------------------------------------------------------


@callback(
    Output("scheduler-status-bar", "children"),
    Input("scheduler-status-interval", "n_intervals"),
    prevent_initial_call=False,
)
def render_scheduler_status(_n_intervals):
    return _scheduler_status_bar(get_status())


@callback(
    Output("data-loaded", "data"),
    Output("last-updated", "children"),
    Input("initial-load", "n_intervals"),
    Input("refresh-btn", "n_clicks"),
    State("data-loaded", "data"),
    prevent_initial_call=False,
)
def load_or_refresh(_n_intervals, n_clicks, loaded):
    """Trigger fetch when no data exists, or when user clicks Refresh."""
    trigger = ctx.triggered_id
    if trigger == "refresh-btn" and n_clicks:
        try:
            fetch_all_now()
        except Exception as e:
            logger.exception("Refresh failed: %s", e)
    elif not data_exists():
        try:
            fetch_all_now()
        except Exception as e:
            logger.exception("Initial fetch failed: %s", e)

    ts = last_updated()
    ts_str = ts.strftime("Last updated: %Y-%m-%d %H:%M") if ts else "No data yet"
    return True, ts_str


@callback(
    Output("metric-cushing", "children"),
    Output("metric-production", "children"),
    Output("metric-refinery", "children"),
    Output("metric-exports", "children"),
    Output("metric-spread", "children"),
    Output("metric-zscore", "children"),
    Output("chart-cushing-5yr", "figure"),
    Output("chart-cushing-wow", "figure"),
    Output("chart-production", "figure"),
    Output("chart-refinery", "figure"),
    Output("chart-exports", "figure"),
    Output("chart-crack", "figure"),
    Output("chart-demand", "figure"),
    Output("chart-spread-seasonal", "figure"),
    Output("chart-zscore", "figure"),
    Output("chart-calendar-spreads", "figure"),
    Output("chart-clco-expiry", "figure"),
    Output("zscore-gauge", "children"),
    Output("signal-panel", "children"),
    Input("data-loaded", "data"),
)
def render_all(loaded):
    data = load_all()

    cushing = data["cushing_stocks"]
    prod = data["us_production"]
    ref = data["refinery_util"]
    exp = data["crude_exports"]
    spr = data["spread"]
    zsc = data["spread_zscore"]
    bands = data["seasonal_bands"]

    # ---- metric cards -----
    cushing_card = _metric_cushing(cushing)
    production_card = _metric_production(prod)
    refinery_card = _metric_refinery(ref)
    exports_card = _metric_exports(exp)
    spread_card = _metric_spread(spr)
    zscore_card = _metric_zscore(zsc)

    # ---- charts -----
    fig_cushing_5yr = inventory.cushing_vs_5yr(cushing)
    fig_cushing_wow = inventory.cushing_wow(cushing)
    fig_production = production.production_trend(prod)
    fig_refinery = refinery.utilization(ref)
    fig_exports = exports_chart.exports(exp)
    fig_crack = refinery.crack_spread_placeholder()
    fig_demand = refinery.implied_demand(ref)
    fig_spread_seasonal = spread.spread_vs_seasonal(spr, bands)
    fig_zscore = spread.zscore(zsc)
    fig_calendar = spread.calendar_spreads_bar(compute_calendar_spreads(None))
    fig_clco_expiry = spread.clco_by_expiry_bar(compute_clco_by_expiry(None, None))

    # ---- z-score gauge -----
    latest_z = None
    if not zsc.empty and "zscore" in zsc.columns:
        zs = pd.to_numeric(zsc["zscore"], errors="coerce").dropna()
        latest_z = float(zs.iloc[-1]) if not zs.empty else None
    gauge = _gauge(latest_z)

    # ---- signal panel -----
    signals = compute_trade_signals(data)
    panel = signal_panel(signals)

    return (
        cushing_card, production_card, refinery_card,
        exports_card, spread_card, zscore_card,
        fig_cushing_5yr, fig_cushing_wow, fig_production,
        fig_refinery, fig_exports, fig_crack, fig_demand,
        fig_spread_seasonal, fig_zscore,
        fig_calendar, fig_clco_expiry,
        gauge, panel,
    )


# ---- per-card content helpers --------------------------------------------


def _metric_cushing(df: pd.DataFrame) -> list:
    if df.empty:
        return _metric_card_content("Cushing stocks", "—", "No data")
    latest = float(df["stocks_kbbl"].iloc[-1])
    wow = _wow(df["stocks_kbbl"]) or 0.0
    kind = "bull" if wow < 0 else "bear" if wow > 0 else "neutral"
    label = f"{'Draw' if wow < 0 else 'Build' if wow > 0 else 'Flat'} {abs(wow):,.0f} kbbl"
    return _metric_card_content(
        "Cushing stocks", f"{latest:,.0f} kbbl",
        "WoW", _badge(label, kind),
    )


def _metric_production(df: pd.DataFrame) -> list:
    if df.empty:
        return _metric_card_content("US production", "—", "No data")
    latest = float(df["production_kbbl_d"].iloc[-1])
    wow = _wow(df["production_kbbl_d"]) or 0.0
    kind = "bull" if wow > 0 else "bear" if wow < 0 else "neutral"
    label = f"{wow:+,.0f} kbbl/d"
    return _metric_card_content(
        "US production", f"{latest:,.0f} kbbl/d",
        "WoW", _badge(label, kind),
    )


def _metric_refinery(df: pd.DataFrame) -> list:
    if df.empty:
        return _metric_card_content("Refinery util", "—", "No data")
    s = pd.to_numeric(df["utilization_pct"], errors="coerce").dropna()
    if s.empty:
        return _metric_card_content("Refinery util", "—", "No data")
    latest = float(s.iloc[-1])
    avg5 = float(s.iloc[-min(len(s), 5 * 52):].mean())
    delta = latest - avg5
    kind = "bull" if delta > 0 else "bear" if delta < 0 else "neutral"
    return _metric_card_content(
        "Refinery util", f"{latest:.1f}%",
        "vs 5yr avg", _badge(f"{delta:+.1f} pp", kind),
    )


def _metric_exports(df: pd.DataFrame) -> list:
    if df.empty:
        return _metric_card_content("Crude exports", "—", "No data")
    s = pd.to_numeric(df["exports_kbbl_d"], errors="coerce").dropna()
    if len(s) < 4:
        return _metric_card_content("Crude exports", "—", "No data")
    avg4 = float(s.iloc[-4:].mean())
    prior4 = float(s.iloc[-8:-4].mean()) if len(s) >= 8 else avg4
    delta = avg4 - prior4
    kind = "bull" if delta > 0 else "bear" if delta < 0 else "neutral"
    return _metric_card_content(
        "Crude exports", f"{avg4:,.0f} kbbl/d",
        "4W avg vs prior", _badge(f"{delta:+,.0f}", kind),
    )


def _metric_spread(df: pd.DataFrame) -> list:
    if df.empty or "spread" not in df.columns:
        return _metric_card_content("CL-CO spread", "—", "No data")
    s = pd.to_numeric(df["spread"], errors="coerce").dropna()
    if s.empty:
        return _metric_card_content("CL-CO spread", "—", "No data")
    latest = float(s.iloc[-1])
    kind = "bear" if latest < 0 else "bull"  # WTI discount = bearish for WTI
    return _metric_card_content(
        "CL-CO spread", f"${latest:+.2f}",
        "Per bbl", _badge("WTI discount" if latest < 0 else "WTI premium", kind),
    )


def _metric_zscore(df: pd.DataFrame) -> list:
    if df.empty or "zscore" not in df.columns:
        return _metric_card_content("Spread z-score", "—", "No data")
    s = pd.to_numeric(df["zscore"], errors="coerce").dropna()
    if s.empty:
        return _metric_card_content("Spread z-score", "—", "No data")
    z = float(s.iloc[-1])
    if z > 1:
        kind, label = "bear", "WTI rich"
    elif z < -1:
        kind, label = "bull", "WTI cheap"
    else:
        kind, label = "neutral", "In range"
    return _metric_card_content(
        "Spread z-score", f"{z:+.2f}σ",
        "vs seasonal", _badge(label, kind),
    )
