"""Dash app initialization and DMC theme."""
from __future__ import annotations

import dash
import dash_mantine_components as dmc

from dashboard.theme import COLORS

# DMC v0.14+ requires Mantine v7 stylesheets to be injected.
def _dmc_stylesheets() -> list:
    styles_mod = getattr(dmc, "styles", None)
    if styles_mod is None:
        return []
    sheets = getattr(styles_mod, "ALL", None)
    if sheets is not None:
        return list(sheets) if not isinstance(sheets, str) else [sheets]
    return [
        getattr(styles_mod, name)
        for name in dir(styles_mod)
        if not name.startswith("_") and isinstance(getattr(styles_mod, name), str)
    ]


_external_stylesheets = _dmc_stylesheets()

app = dash.Dash(
    __name__,
    title="Crude Oil Trading Dashboard",
    external_stylesheets=_external_stylesheets,
    suppress_callback_exceptions=True,
    update_title=None,
)
server = app.server

_theme = {
    "colorScheme": "dark",
    "primaryColor": "orange",
    "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "components": {
        "Card": {"defaultProps": {"radius": "md"}},
    },
}

from dashboard.layout import build_layout  # noqa: E402  (import after app)
import dashboard.callbacks  # noqa: F401, E402  (register callbacks)

app.layout = dmc.MantineProvider(
    theme=_theme,
    forceColorScheme="dark",
    children=build_layout(),
)
