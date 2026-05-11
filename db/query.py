"""DuckDB query helpers. Each function returns a DataFrame parsed with dates."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def _query_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = duckdb.query(f"SELECT * FROM '{path.as_posix()}'").df()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def get_cushing_stocks() -> pd.DataFrame:
    return _query_parquet(RAW_DIR / "cushing_stocks.parquet")


def get_production() -> pd.DataFrame:
    return _query_parquet(RAW_DIR / "us_production.parquet")


def get_refinery_util() -> pd.DataFrame:
    return _query_parquet(RAW_DIR / "refinery_util.parquet")


def get_exports() -> pd.DataFrame:
    return _query_parquet(RAW_DIR / "crude_exports.parquet")


def get_spread() -> pd.DataFrame:
    return _query_parquet(RAW_DIR / "cl_co_spread.parquet")


def get_zscore() -> pd.DataFrame:
    return _query_parquet(PROCESSED_DIR / "spread_zscore.parquet")


def get_seasonal_bands() -> pd.DataFrame:
    path = PROCESSED_DIR / "seasonal_bands.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM '{path.as_posix()}'").df()


def load_all() -> dict[str, pd.DataFrame]:
    """One-shot loader used by signal computation."""
    return {
        "cushing_stocks": get_cushing_stocks(),
        "us_production": get_production(),
        "refinery_util": get_refinery_util(),
        "crude_exports": get_exports(),
        "spread": get_spread(),
        "spread_zscore": get_zscore(),
        "seasonal_bands": get_seasonal_bands(),
    }


def data_exists() -> bool:
    return any(RAW_DIR.glob("*.parquet"))
