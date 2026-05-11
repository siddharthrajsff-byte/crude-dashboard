"""EIA API v2 client. Fetches series data and persists as Parquet."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv

load_dotenv()

EIA_BASE_URL = "https://api.eia.gov/v2"
PAGE_SIZE = 5000
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)


def _api_key() -> str:
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "EIA_API_KEY is not set. Add it to .env in the project root."
        )
    return key


def _build_params(
    facets: dict[str, list[str]] | None,
    frequency: str,
    start_date: str | None,
    offset: int,
    data_cols: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Build query parameter list. Multi-value facets must repeat the key."""
    params: list[tuple[str, str]] = [
        ("api_key", _api_key()),
        ("frequency", frequency),
        ("offset", str(offset)),
        ("length", str(PAGE_SIZE)),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    for col in (data_cols or ["value"]):
        params.append(("data[]", col))
    if start_date:
        params.append(("start", start_date))
    if facets:
        for facet_name, values in facets.items():
            for v in values:
                params.append((f"facets[{facet_name}][]", v))
    return params


def _request_page(endpoint: str, params: list[tuple[str, str]]) -> dict[str, Any]:
    url = f"{EIA_BASE_URL}/{endpoint.strip('/')}"
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            last_err = e
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    raise RuntimeError(f"EIA request failed for {endpoint}: {last_err}")


def fetch_series(
    endpoint: str,
    facets: dict[str, list[str]] | None = None,
    frequency: str = "weekly",
    start_date: str | None = "2010-01-01",
    data_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch a series from EIA, handling pagination. Returns a DataFrame."""
    rows: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None

    while True:
        params = _build_params(facets, frequency, start_date, offset, data_cols)
        payload = _request_page(endpoint, params)
        response = payload.get("response", {})
        page = response.get("data", []) or []
        if total is None:
            try:
                total = int(response.get("total", 0))
            except (TypeError, ValueError):
                total = None
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if total is not None and offset >= total:
            break
        if len(page) < PAGE_SIZE:
            break

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "period" in df.columns:
        df["date"] = pd.to_datetime(df["period"], errors="coerce")
    for col in df.columns:
        if col in ("value",) or col.endswith("_value"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def save_parquet(df: pd.DataFrame, filename: str) -> Path:
    """Persist DataFrame to data/raw/<filename> as Parquet via PyArrow."""
    path = DATA_RAW_DIR / filename
    if df.empty:
        if path.exists():
            path.unlink()
        return path
    safe = df.copy()
    for col in safe.columns:
        if safe[col].dtype == "object":
            safe[col] = safe[col].astype("string")
    table = pa.Table.from_pandas(safe, preserve_index=False)
    pq.write_table(table, path)
    return path
