"""Instrument taxonomy for forward curve analysis."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "fca_instruments.json"

GROUP_LABELS = {
    "outrights": "Outrights",
    "spreads": "Spreads",
    "butterflies": "Butterflies",
}

TYPE_GROUPS = {
    "OUTRIGHT": "outrights",
    "1MS": "spreads",
    "2MS": "spreads",
    "3MS": "spreads",
    "1MF": "butterflies",
    "2MF": "butterflies",
    "3MF": "butterflies",
}


@dataclass(frozen=True)
class FcaInstrument:
    group: str
    product_name: str
    instrument_type: str
    tenor: str
    instrument_id: str
    label: str
    enabled: bool = True


def _normalise_entry(
    product_name: str,
    entry: dict[str, Any],
    fallback_group: str | None = None,
) -> FcaInstrument | None:
    instrument_id = str(entry.get("instrument_id") or entry.get("instrumentId") or "").strip()
    instrument_id = instrument_id.split("-")[0]
    tenor = str(entry.get("tenor") or entry.get("label") or "").strip()
    instrument_type = str(entry.get("instrument_type") or entry.get("instrumentType") or "").strip().upper()
    group = TYPE_GROUPS.get(instrument_type, fallback_group or "")
    if not instrument_id or not tenor:
        return None

    return FcaInstrument(
        group=group,
        product_name=product_name,
        instrument_type=instrument_type,
        tenor=tenor,
        instrument_id=instrument_id,
        label=str(entry.get("label") or tenor),
        enabled=bool(entry.get("enabled", True)),
    )


def load_fca_instruments(path: Path = CONFIG_PATH) -> dict[str, list[FcaInstrument]]:
    """Load enabled FCA instruments, preserving file order for curve plotting."""
    groups = {group: [] for group in GROUP_LABELS}
    for instrument in load_product_instruments(path):
        if instrument.group in groups and instrument.enabled:
            groups[instrument.group].append(instrument)
    return groups


def load_product_instruments(path: Path = CONFIG_PATH) -> list[FcaInstrument]:
    """Load enabled instruments in product order."""
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    instruments: list[FcaInstrument] = []
    if "products" in payload:
        for product in payload.get("products", []) or []:
            product_name = str(product.get("product_name") or product.get("productName") or "").strip()
            if not product_name:
                continue
            for entry in product.get("instruments", []) or []:
                if not isinstance(entry, dict):
                    continue
                instrument = _normalise_entry(product_name, entry)
                if instrument is not None and instrument.enabled:
                    instruments.append(instrument)
        return instruments

    raw_groups = payload.get("groups", payload)
    for group in GROUP_LABELS:
        for entry in raw_groups.get(group, []) or []:
            if not isinstance(entry, dict):
                continue
            product_name = str(entry.get("product_name") or entry.get("productName") or "Default").strip()
            instrument = _normalise_entry(product_name, entry, fallback_group=group)
            if instrument is not None and instrument.enabled:
                instruments.append(instrument)
    return instruments


def configured_count(groups: dict[str, list[FcaInstrument]]) -> int:
    return sum(len(items) for items in groups.values())


def table_types(instruments: list[FcaInstrument]) -> tuple[str, ...]:
    configured = {
        instrument.instrument_type
        for instrument in instruments
        if instrument.instrument_type and instrument.instrument_type != "OUTRIGHT"
    }
    if not configured:
        return ("1MS", "2MS", "1MF", "2MF")

    def sort_key(value: str) -> tuple[str, int, str]:
        digits = "".join(ch for ch in value if ch.isdigit())
        suffix = "".join(ch for ch in value if not ch.isdigit())
        group = "0" if suffix == "MS" else "1" if suffix == "MF" else "2"
        return group, int(digits or 0), value

    return tuple(sorted(configured, key=sort_key))
