"""Orchestrate all EIA series fetches and persist to Parquet."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from .eia_client import DATA_RAW_DIR, fetch_series, save_parquet
from .wpsr_client import fetch_all_wpsr

logger = logging.getLogger(__name__)

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"


def _value_col(df: pd.DataFrame) -> str | None:
    """Some EIA endpoints return 'value' as a string column. Normalize to numeric."""
    for col in ("value", "VALUE", "data"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            return col
    return None


def fetch_cushing_stocks() -> pd.DataFrame:
    """Weekly Cushing, OK ending stocks of crude oil (thousand barrels)."""
    df = fetch_series(
        endpoint="petroleum/stoc/wstk/data/",
        facets={"series": ["W_EPC0_SAX_YCUOK_MBBL"]},
        frequency="weekly",
        start_date=START_DATE,
    )
    if not df.empty:
        col = _value_col(df) or "value"
        df = df.rename(columns={col: "stocks_kbbl"})
        df = df[["date", "stocks_kbbl"]].dropna().drop_duplicates("date")
    save_parquet(df, "cushing_stocks.parquet")
    return df


def fetch_us_production() -> pd.DataFrame:
    """Weekly U.S. field production of crude oil (thousand barrels per day)."""
    df = fetch_series(
        endpoint="petroleum/sum/sndw/data/",
        facets={"series": ["WCRFPUS2"]},
        frequency="weekly",
        start_date=START_DATE,
    )
    if not df.empty:
        col = _value_col(df) or "value"
        df = df.rename(columns={col: "production_kbbl_d"})
        df = df[["date", "production_kbbl_d"]].dropna().drop_duplicates("date")
    save_parquet(df, "us_production.parquet")
    return df


def fetch_refinery_util() -> pd.DataFrame:
    """Weekly U.S. percent utilization of refinery operable capacity."""
    df = fetch_series(
        endpoint="petroleum/pnp/wiup/data/",
        facets={"series": ["WPULEUS3"]},
        frequency="weekly",
        start_date=START_DATE,
    )
    if not df.empty:
        col = _value_col(df) or "value"
        df = df.rename(columns={col: "utilization_pct"})
        df = df[["date", "utilization_pct"]].dropna().drop_duplicates("date")
    save_parquet(df, "refinery_util.parquet")
    return df


def fetch_crude_exports() -> pd.DataFrame:
    """Weekly U.S. exports of crude oil (thousand barrels per day)."""
    df = fetch_series(
        endpoint="petroleum/move/wkly/data/",
        facets={"series": ["WCREXUS2"]},
        frequency="weekly",
        start_date=START_DATE,
    )
    if not df.empty:
        col = _value_col(df) or "value"
        df = df.rename(columns={col: "exports_kbbl_d"})
        df = df[["date", "exports_kbbl_d"]].dropna().drop_duplicates("date")
    save_parquet(df, "crude_exports.parquet")
    return df


def fetch_cl_co_spread() -> pd.DataFrame:
    """Daily WTI (Cushing) and Brent (Europe) spot; computed CL-CO spread."""
    spot = fetch_series(
        endpoint="petroleum/pri/spt/data/",
        facets={"series": ["RWTC", "RBRTE"]},
        frequency="daily",
        start_date=START_DATE,
    )
    if spot.empty or "series" not in spot.columns:
        save_parquet(pd.DataFrame(), "cl_co_spread.parquet")
        return pd.DataFrame()

    col = _value_col(spot) or "value"
    wti = (
        spot[spot["series"] == "RWTC"][["date", col]]
        .rename(columns={col: "wti_price"})
        .drop_duplicates("date")
    )
    brent = (
        spot[spot["series"] == "RBRTE"][["date", col]]
        .rename(columns={col: "brent_price"})
        .drop_duplicates("date")
    )
    df = pd.merge(wti, brent, on="date", how="outer").sort_values("date")
    df["spread"] = df["wti_price"] - df["brent_price"]
    df = df.dropna(subset=["wti_price", "brent_price"]).reset_index(drop=True)
    save_parquet(df, "cl_co_spread.parquet")
    return df


def fetch_all() -> dict[str, int]:
    """Fetch every series. Returns row counts per series."""
    fetchers = {
        "cushing_stocks": fetch_cushing_stocks,
        "us_production": fetch_us_production,
        "refinery_util": fetch_refinery_util,
        "crude_exports": fetch_crude_exports,
        "cl_co_spread": fetch_cl_co_spread,
    }
    counts: dict[str, int] = {}
    for name, fn in fetchers.items():
        try:
            df = fn()
            counts[name] = len(df)
            logger.info("Fetched %s: %d rows", name, len(df))
        except Exception as e:
            logger.exception("Failed to fetch %s: %s", name, e)
            counts[name] = -1

    _write_processed(counts)
    return counts


def fetch_all_now() -> dict:
    """
    Manual refresh: run WPSR first (latest week), then API v2 (historical).
    Called by the dashboard Refresh button.
    Returns combined result dict.
    """
    wpsr_results = fetch_all_wpsr()
    api_results = fetch_all()
    return {"wpsr": wpsr_results, "api_v2": api_results}


def _write_processed(counts: dict[str, int]) -> None:
    """Compute and persist derived series (z-scores, seasonal bands) for the spread."""
    from compute.signals import compute_seasonal_bands, compute_zscore

    spread_path = DATA_RAW_DIR / "cl_co_spread.parquet"
    if not spread_path.exists():
        return
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    df = duckdb.query(f"SELECT * FROM '{spread_path.as_posix()}'").df()
    if df.empty or "spread" not in df.columns:
        return
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    z = compute_zscore(df["spread"], window=252)
    z_df = pd.DataFrame({"date": df["date"], "spread": df["spread"], "zscore": z})
    z_df = z_df.dropna(subset=["zscore"]).reset_index(drop=True)
    if not z_df.empty:
        pq.write_table(
            pa.Table.from_pandas(z_df, preserve_index=False),
            DATA_PROCESSED_DIR / "spread_zscore.parquet",
        )

    bands = compute_seasonal_bands(df, value_col="spread")
    if not bands.empty:
        pq.write_table(
            pa.Table.from_pandas(bands, preserve_index=False),
            DATA_PROCESSED_DIR / "seasonal_bands.parquet",
        )


def last_updated() -> datetime | None:
    """Return the most recent file mtime across raw Parquet files."""
    parquet_files = list(DATA_RAW_DIR.glob("*.parquet"))
    if not parquet_files:
        return None
    return datetime.fromtimestamp(max(p.stat().st_mtime for p in parquet_files))
