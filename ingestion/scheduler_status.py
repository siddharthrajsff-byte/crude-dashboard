"""In-process status state for scheduled data refresh jobs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_LOCK = RLock()


def _now_iso() -> str:
    return datetime.now(ET).isoformat(timespec="seconds")


def _dt_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ET)
    return value.astimezone(ET).isoformat(timespec="seconds")

_DEFAULT_JOBS = {
    "wpsr_realtime_refresh": {
        "label": "WPSR real-time release",
        "schedule": "Wed 10:30 ET",
        "state": "idle",
        "message": "Waiting for next WPSR release window.",
        "started_at": None,
        "finished_at": None,
        "last_success_at": None,
        "last_error": None,
        "result": None,
        "next_run_at": None,
    },
    "eia_api_historical_refresh": {
        "label": "EIA API v2 historical refresh",
        "schedule": "Wed 11:30 ET",
        "state": "idle",
        "message": "Waiting for next EIA API backfill window.",
        "started_at": None,
        "finished_at": None,
        "last_success_at": None,
        "last_error": None,
        "result": None,
        "next_run_at": None,
    },
}

_STATUS = {
    "scheduler_running": False,
    "updated_at": _now_iso(),
    "jobs": deepcopy(_DEFAULT_JOBS),
}


def mark_scheduler_running(running: bool) -> None:
    """Record whether the in-process APScheduler has been started."""
    with _LOCK:
        _STATUS["scheduler_running"] = running
        _STATUS["updated_at"] = _now_iso()


def set_next_run(job_id: str, next_run_at: datetime | None) -> None:
    """Record the next scheduled run time for a known job."""
    with _LOCK:
        job = _job(job_id)
        job["next_run_at"] = _dt_iso(next_run_at) if next_run_at else None
        _STATUS["updated_at"] = _now_iso()


def mark_started(job_id: str, message: str) -> None:
    """Mark a scheduled job as running."""
    with _LOCK:
        now = _now_iso()
        job = _job(job_id)
        job.update({
            "state": "running",
            "message": message,
            "started_at": now,
            "finished_at": None,
            "last_error": None,
            "result": None,
        })
        _STATUS["updated_at"] = now


def mark_finished(job_id: str, success: bool, message: str, result: object = None) -> None:
    """Mark a scheduled job as finished, preserving its latest result."""
    with _LOCK:
        now = _now_iso()
        job = _job(job_id)
        job.update({
            "state": "success" if success else "error",
            "message": message,
            "finished_at": now,
            "last_error": None if success else message,
            "result": result,
        })
        if success:
            job["last_success_at"] = now
        _STATUS["updated_at"] = now


def get_status() -> dict:
    """Return a copy of the current scheduler status for dashboard callbacks."""
    with _LOCK:
        return deepcopy(_STATUS)


def _job(job_id: str) -> dict:
    if job_id not in _STATUS["jobs"]:
        _STATUS["jobs"][job_id] = {
            "label": job_id,
            "schedule": "",
            "state": "idle",
            "message": "Waiting for next run.",
            "started_at": None,
            "finished_at": None,
            "last_success_at": None,
            "last_error": None,
            "result": None,
            "next_run_at": None,
        }
    return _STATUS["jobs"][job_id]
