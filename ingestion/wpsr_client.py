"""Real-time WPSR CSV ingestion for latest weekly petroleum data."""
from __future__ import annotations

import csv
import logging
import re
import time
from io import StringIO
from pathlib import Path
from typing import Callable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from .eia_client import DATA_RAW_DIR

logger = logging.getLogger(__name__)

WPSR_BASE = "https://ir.eia.gov/wpsr/"
USER_AGENT = "CrudeDashboard/1.0 (contact@example.com)"
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 30


def fetch_wpsr_table(table_num: str) -> pd.DataFrame:
    """
    Download ir.eia.gov/wpsr/table{table_num}.csv and return as raw DataFrame.
    Use requests with a descriptive User-Agent header as EIA recommends:
      User-Agent: CrudeDashboard/1.0 (contact@example.com)
    Follow 302 redirects (requests does this by default).
    Retry up to 3 times with 2s backoff. Timeout 30s.
    Return empty DataFrame on failure, log the error.
    """
    url = f"{WPSR_BASE}table{table_num}.csv"
    headers = {"User-Agent": USER_AGENT}
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return _read_wpsr_csv(resp.text)
        except (requests.RequestException, csv.Error, ValueError) as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF)

    logger.error("Failed to fetch WPSR table %s: %s", table_num, last_err)
    return pd.DataFrame()


def parse_latest_week(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """
    From a raw WPSR table DataFrame, extract:
    - latest_date: the first date column header parsed as a date string (YYYY-MM-DD)
    - values: DataFrame with STUB_1 (and STUB_2 if present) as index, latest week value
      as float column named 'value'
    Strip commas from value strings before converting to float.
    Return (latest_date, values_df).
    """
    if df.empty:
        return "", pd.DataFrame(columns=["value"])

    latest_col = _latest_date_column(df)
    if latest_col is None:
        logger.warning("WPSR table has no date-like value columns")
        return "", pd.DataFrame(columns=["value"])

    latest_date = _parse_date_header(latest_col)
    index_cols = ["STUB_1"]
    if "STUB_2" in df.columns:
        index_cols.append("STUB_2")

    missing_cols = [col for col in index_cols if col not in df.columns]
    if missing_cols:
        logger.warning("WPSR table missing expected label columns: %s", missing_cols)
        return latest_date, pd.DataFrame(columns=["value"])

    values = df[index_cols].copy()
    values["value"] = _numeric_series(df[latest_col])
    values = values.dropna(subset=["STUB_1"])
    values = values[values["STUB_1"].astype(str).str.strip().ne("STUB_1")]
    for col in index_cols:
        values[col] = values[col].fillna("").astype(str).str.strip()
    values = values.set_index(index_cols)[["value"]]
    return latest_date, values


def fetch_cushing_wpsr() -> dict:
    """
    From table4.csv, extract Cushing stocks (million barrels).
    Look for row where STUB_1 == 'Cushing' or contains 'Cushing'.
    Convert million barrels to thousand barrels (* 1000) to match existing parquet schema.
    Return {"date": "YYYY-MM-DD", "stocks_kbbl": float}
    """
    try:
        date, values = parse_latest_week(fetch_wpsr_table("4"))
        if not date or values.empty:
            return {}
        labels = _index_text(values.index, 0)
        match = values[labels.str.contains("cushing", na=False)]
        value = _first_value(match, "Cushing stocks")
        return {"date": date, "stocks_kbbl": value * 1000} if value is not None else {}
    except Exception as e:
        logger.exception("Failed to parse WPSR Cushing stocks: %s", e)
        return {}


def fetch_refinery_util_wpsr() -> dict:
    """
    From table2.csv, extract refinery utilization %.
    Look for row where STUB_1 contains 'Refiner Inputs and Utilization'
    and STUB_2 contains 'Utilization Rate' or similar.
    Return {"date": "YYYY-MM-DD", "utilization_pct": float}
    """
    try:
        date, values = parse_latest_week(fetch_wpsr_table("2"))
        if not date or values.empty:
            return {}
        stub_1 = _index_text(values.index, 0)
        stub_2 = _index_text(values.index, 1)
        match = values[
            stub_1.str.contains("refiner inputs and utilization", na=False)
            & stub_2.str.contains("utilization", na=False)
        ]
        value = _first_value(match, "refinery utilization")
        return {"date": date, "utilization_pct": value} if value is not None else {}
    except Exception as e:
        logger.exception("Failed to parse WPSR refinery utilization: %s", e)
        return {}


def fetch_crude_exports_wpsr() -> dict:
    """
    From table7.csv, extract crude oil exports (thousand barrels/day).
    Look for row where STUB_1 contains 'Exports' and refers to crude oil.
    Note: table7 values may be in Mbbl/d already -- confirm units from header context.
    Return {"date": "YYYY-MM-DD", "exports_kbbl_d": float}
    """
    try:
        date, values = parse_latest_week(fetch_wpsr_table("7"))
        if not date or values.empty:
            return {}
        section = _crude_net_imports_section(values)
        labels = _index_text(section.index, 0)
        match = section[labels.eq("exports") | labels.str.contains("crude.*exports|exports.*crude", regex=True, na=False)]
        value = _first_value(match, "crude exports")
        if value is None:
            exports_rows = values[_index_text(values.index, 0).eq("exports")]
            value = _nth_value(exports_rows, 1, "crude exports")
        return {"date": date, "exports_kbbl_d": value} if value is not None else {}
    except Exception as e:
        logger.exception("Failed to parse WPSR crude exports: %s", e)
        return {}


def fetch_crude_imports_wpsr() -> dict:
    """
    From table7.csv, extract crude oil commercial imports (thousand barrels/day).
    Look for row where STUB_1 == 'Commercial' under 'Crude Oil Net Imports'.
    Return {"date": "YYYY-MM-DD", "imports_kbbl_d": float}
    """
    try:
        date, values = parse_latest_week(fetch_wpsr_table("7"))
        if not date or values.empty:
            return {}
        section = _crude_net_imports_section(values)
        labels = _index_text(section.index, 0)
        match = section[labels.eq("commercial") | labels.str.contains("commercial crude oil", na=False)]
        value = _first_value(match, "crude commercial imports")
        return {"date": date, "imports_kbbl_d": value} if value is not None else {}
    except Exception as e:
        logger.exception("Failed to parse WPSR crude imports: %s", e)
        return {}


def fetch_spr_stocks_wpsr() -> dict:
    """
    From table4.csv, extract SPR stocks (million barrels -> thousand barrels).
    Look for row where STUB_1 == 'SPR' or 'Strategic Petroleum Reserve (SPR)'.
    Return {"date": "YYYY-MM-DD", "spr_stocks_kbbl": float}
    """
    try:
        date, values = parse_latest_week(fetch_wpsr_table("4"))
        if not date or values.empty:
            return {}
        labels = _index_text(values.index, 0)
        match = values[
            labels.eq("spr")
            | labels.str.contains("strategic petroleum reserve", na=False)
        ]
        value = _first_value(match, "SPR stocks")
        return {"date": date, "spr_stocks_kbbl": value * 1000} if value is not None else {}
    except Exception as e:
        logger.exception("Failed to parse WPSR SPR stocks: %s", e)
        return {}


def fetch_us_production_wpsr() -> dict:
    """
    From table2.csv, extract US field production of crude oil (thousand barrels/day).
    Look for row in STUB_1 containing 'Field Production' or 'Crude Oil' production row.
    Return {"date": "YYYY-MM-DD", "production_kbbl_d": float}
    """
    try:
        result = _fetch_us_production_from_table("2")
        if result:
            return result
        logger.warning("US crude production not found in WPSR table2; trying table1 fallback")
        return _fetch_us_production_from_table("1")
    except Exception as e:
        logger.exception("Failed to parse WPSR US production: %s", e)
        return {}


def upsert_wpsr_row(parquet_filename: str, row: dict, date_col: str = "date") -> None:
    """
    Upsert a single row (dict) into an existing Parquet file in data/raw/.
    - If the file does not exist: create it with just this row.
    - If the date already exists in the file: overwrite that row.
    - If the date does not exist: append the row.
    Use DuckDB to read existing data, pandas to upsert, pyarrow to write back.
    """
    if not row:
        logger.warning("Skipping empty WPSR upsert for %s", parquet_filename)
        return
    if date_col not in row:
        logger.warning("Skipping WPSR upsert for %s without %s", parquet_filename, date_col)
        return

    path = DATA_RAW_DIR / parquet_filename
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    new_row = pd.DataFrame([row])
    new_row[date_col] = pd.to_datetime(new_row[date_col], errors="coerce").dt.normalize()
    new_row = new_row.dropna(subset=[date_col])
    if new_row.empty:
        logger.warning("Skipping WPSR upsert for %s with invalid date", parquet_filename)
        return

    if path.exists():
        import duckdb

        existing = duckdb.query(f"SELECT * FROM '{path.as_posix()}'").df()
    else:
        existing = pd.DataFrame()

    combined = pd.concat([existing, new_row], ignore_index=True, sort=False)
    combined[date_col] = pd.to_datetime(combined[date_col], errors="coerce").dt.normalize()
    combined = combined.dropna(subset=[date_col])
    combined = (
        combined.drop_duplicates(subset=[date_col], keep="last")
        .sort_values(date_col)
        .reset_index(drop=True)
    )

    for col in combined.columns:
        if col != date_col:
            converted = pd.to_numeric(combined[col], errors="coerce")
            if converted[combined[col].notna()].notna().all():
                combined[col] = converted

    tmp_path = _tmp_parquet_path(path)
    table = pa.Table.from_pandas(combined, preserve_index=False)
    pq.write_table(table, tmp_path)
    tmp_path.replace(path)


def fetch_all_wpsr() -> dict[str, bool]:
    """
    Orchestrate all WPSR fetches and upserts.
    Returns dict of {series_name: success_bool}.
    Runs:
      fetch_cushing_wpsr()       -> upsert into cushing_stocks.parquet
      fetch_refinery_util_wpsr() -> upsert into refinery_util.parquet
      fetch_crude_exports_wpsr() -> upsert into crude_exports.parquet
      fetch_crude_imports_wpsr() -> upsert into crude_imports.parquet
      fetch_spr_stocks_wpsr()    -> upsert into spr_stocks.parquet
      fetch_us_production_wpsr() -> upsert into us_production.parquet
    Log success/failure per series. Never raise -- catch all exceptions per series.
    """
    jobs: dict[str, tuple[Callable[[], dict], str]] = {
        "cushing_stocks": (fetch_cushing_wpsr, "cushing_stocks.parquet"),
        "refinery_util": (fetch_refinery_util_wpsr, "refinery_util.parquet"),
        "crude_exports": (fetch_crude_exports_wpsr, "crude_exports.parquet"),
        "crude_imports": (fetch_crude_imports_wpsr, "crude_imports.parquet"),
        "spr_stocks": (fetch_spr_stocks_wpsr, "spr_stocks.parquet"),
        "us_production": (fetch_us_production_wpsr, "us_production.parquet"),
    }
    results: dict[str, bool] = {}

    for series_name, (fetcher, filename) in jobs.items():
        try:
            row = fetcher()
            if not row:
                logger.warning("WPSR %s not updated: no row extracted", series_name)
                results[series_name] = False
                continue
            upsert_wpsr_row(filename, row)
            logger.info("WPSR %s updated for %s", series_name, row.get("date"))
            results[series_name] = True
        except Exception as e:
            logger.exception("WPSR %s failed: %s", series_name, e)
            results[series_name] = False

    return results


def _read_wpsr_csv(text: str) -> pd.DataFrame:
    """Read WPSR CSV text, including files with repeated section headers."""
    cleaned = text.replace("\x1a", "")
    rows = [row for row in csv.reader(StringIO(cleaned)) if row]
    if not rows:
        return pd.DataFrame()

    current_header = _make_unique_headers(rows[0])
    parsed_rows: list[dict[str, str | None]] = []

    for row in rows[1:]:
        if row and row[0].strip().upper() == "STUB_1":
            current_header = _make_unique_headers(row)
            continue

        row_values = row + [None] * max(0, len(current_header) - len(row))
        item = {col: row_values[idx] for idx, col in enumerate(current_header)}
        if len(row) > len(current_header):
            for idx, value in enumerate(row[len(current_header):], start=1):
                item[f"EXTRA_{idx}"] = value
        parsed_rows.append(item)

    return pd.DataFrame(parsed_rows)


def _make_unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for header in headers:
        name = str(header).strip()
        count = seen.get(name, 0)
        unique.append(name if count == 0 else f"{name}.{count}")
        seen[name] = count + 1
    return unique


def _latest_date_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col in {"STUB_1", "STUB_2"}:
            continue
        if _is_date_header(col):
            return str(col)
    return None


def _is_date_header(header: object) -> bool:
    cleaned = _clean_date_header(header)
    return bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", cleaned))


def _clean_date_header(header: object) -> str:
    return re.sub(r"\.\d+$", "", str(header).strip())


def _parse_date_header(header: object) -> str:
    parsed = pd.to_datetime(_clean_date_header(header), format="%m/%d/%y", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(_clean_date_header(header), errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _index_text(index: pd.Index, level: int) -> pd.Series:
    if isinstance(index, pd.MultiIndex):
        if level >= index.nlevels:
            return pd.Series([""] * len(index), index=index)
        values = index.get_level_values(level)
    elif level == 0:
        values = index
    else:
        return pd.Series([""] * len(index), index=index)
    return pd.Series(values, index=index).fillna("").astype(str).str.strip().str.lower()


def _first_value(rows: pd.DataFrame, label: str) -> float | None:
    if rows.empty:
        logger.warning("WPSR row not found for %s", label)
        return None
    values = pd.to_numeric(rows["value"], errors="coerce").dropna()
    if values.empty:
        logger.warning("WPSR row has no numeric value for %s", label)
        return None
    return float(values.iloc[0])


def _nth_value(rows: pd.DataFrame, n: int, label: str) -> float | None:
    values = pd.to_numeric(rows["value"], errors="coerce").dropna()
    if len(values) <= n:
        logger.warning("WPSR row not found for %s", label)
        return None
    return float(values.iloc[n])


def _crude_net_imports_section(values: pd.DataFrame) -> pd.DataFrame:
    labels = _index_text(values.index, 0)
    start_positions = labels[labels.str.contains("crude oil net imports", na=False)].index
    if len(start_positions) == 0:
        logger.warning("WPSR crude oil net imports section not found")
        return pd.DataFrame(columns=values.columns)

    labels_list = list(labels)
    start_label = start_positions[0]
    start_pos = values.index.get_loc(start_label)
    end_pos = len(values)
    for pos in range(start_pos + 1, len(labels_list)):
        if "total products net imports" in labels_list[pos]:
            end_pos = pos
            break
    return values.iloc[start_pos + 1:end_pos]


def _fetch_us_production_from_table(table_num: str) -> dict:
    date, values = parse_latest_week(fetch_wpsr_table(table_num))
    if not date or values.empty:
        return {}

    stub_1 = _index_text(values.index, 0)
    stub_2 = _index_text(values.index, 1)
    match = values[
        stub_1.str.contains("field production", na=False)
        | (stub_1.str.contains("crude oil", na=False) & stub_1.str.contains("production", na=False))
        | (stub_1.str.contains("crude oil supply", na=False) & stub_2.str.contains("domestic production|field production", regex=True, na=False))
    ]
    value = _first_value(match, f"US crude production table{table_num}")
    return {"date": date, "production_kbbl_d": value} if value is not None else {}


def _tmp_parquet_path(path: Path) -> Path:
    return path.with_name(f".{path.stem}.tmp{path.suffix}")
