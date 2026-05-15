"""Read latest L1 market data snapshots for FCA charts.

This module intentionally does not import or start the Lightstreamer service.
The dashboard reads a small snapshot file if another process writes one.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import pandas as pd

from dashboard.fca.config import FcaInstrument

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_PATH = ROOT / "data" / "live" / "l1_latest.json"

PRICE_FIELDS = (
    "VWAP",
)

_LAST_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def _to_float(value: Any) -> float | None:
    if value in (None, "", "NaN"):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    instrument_id = str(record.get("instrumentId") or record.get("instrument_id") or record.get("key") or "")
    instrument_id = instrument_id.split("-")[0]

    bid = _to_float(record.get("bidPrice"))
    ask = _to_float(record.get("askPrice"))
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None

    normalised = dict(record)
    normalised["instrument_id"] = instrument_id
    normalised["midPrice"] = mid
    normalised["bidPrice"] = bid
    normalised["askPrice"] = ask
    normalised["tradePrice"] = _to_float(record.get("tradePrice"))
    normalised["settlementPrice"] = _to_float(record.get("settlementPrice"))
    normalised["VWAP"] = _to_float(record.get("VWAP"))
    return normalised


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return [item for item in payload["records"] if isinstance(item, dict)]
        if isinstance(payload.get("latest"), dict):
            return [
                {"instrumentId": instrument_id, **record}
                for instrument_id, record in payload["latest"].items()
                if isinstance(record, dict)
            ]
        return [
            {"instrumentId": instrument_id, **record}
            for instrument_id, record in payload.items()
            if isinstance(record, dict)
        ]
    return []


def load_latest_snapshots(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, dict[str, Any]]:
    """Return latest L1 records keyed by bare instrument id."""
    if not path.exists():
        return _LAST_SNAPSHOTS.copy()

    payload = None
    for attempt in range(5):
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            break
        except (PermissionError, json.JSONDecodeError):
            if attempt == 4:
                return _LAST_SNAPSHOTS.copy()
            time.sleep(0.05)

    snapshots: dict[str, dict[str, Any]] = {}
    for record in _records_from_payload(payload):
        normalised = _normalise_record(record)
        instrument_id = normalised.get("instrument_id")
        if instrument_id:
            snapshots[instrument_id] = normalised
    if snapshots:
        _LAST_SNAPSHOTS.clear()
        _LAST_SNAPSHOTS.update(snapshots)
    return snapshots


def price_from_snapshot(snapshot: dict[str, Any]) -> tuple[float | None, str | None]:
    for field in PRICE_FIELDS:
        value = _to_float(snapshot.get(field))
        if value is not None:
            return value, field
    return None, None


def build_curve_frame(
    instruments: list[FcaInstrument],
    snapshots: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for position, instrument in enumerate(instruments):
        snapshot = snapshots.get(instrument.instrument_id, {})
        price, source = price_from_snapshot(snapshot)
        rows.append(
            {
                "position": position,
                "tenor": instrument.tenor,
                "label": instrument.label,
                "instrument_id": instrument.instrument_id,
                "price": price,
                "price_source": source,
                "bid": snapshot.get("bidPrice"),
                "ask": snapshot.get("askPrice"),
                "trade": snapshot.get("tradePrice"),
                "exchange_time_ns": snapshot.get("exchangeTimeNs"),
                "state": snapshot.get("state"),
            }
        )
    return pd.DataFrame(rows)


def build_product_table_frame(
    instruments: list[FcaInstrument],
    snapshots: dict[str, dict[str, Any]],
    instrument_types: tuple[str, ...],
) -> pd.DataFrame:
    table_instruments = [
        instrument
        for instrument in instruments
        if instrument.instrument_type != "OUTRIGHT"
    ]
    products = list(dict.fromkeys(instrument.product_name for instrument in table_instruments))
    rows = []

    for product_name in products:
        product_instruments = [
            instrument
            for instrument in table_instruments
            if instrument.product_name == product_name
        ]
        labels = list(dict.fromkeys(instrument.label for instrument in product_instruments))

        for label in labels:
            row = {"product_name": product_name, "label": label}
            for instrument_type in instrument_types:
                match = next(
                    (
                        instrument
                        for instrument in product_instruments
                        if instrument.label == label
                        and instrument.instrument_type == instrument_type
                    ),
                    None,
                )
                price = None
                if match is not None:
                    price, _source = price_from_snapshot(snapshots.get(match.instrument_id, {}))
                if price is not None:
                    row[instrument_type] = f"{price:.3f}"
                else:
                    row[instrument_type] = ""
            rows.append(row)

    return pd.DataFrame(rows)
