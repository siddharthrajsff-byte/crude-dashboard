"""Background scheduler: refresh WPSR and EIA API data weekly."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .fetch_all import fetch_all
from .scheduler_status import mark_finished, mark_scheduler_running, mark_started, set_next_run

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
WPSR_JOB_ID = "wpsr_realtime_refresh"
EIA_API_JOB_ID = "eia_api_historical_refresh"


def start_scheduler() -> BackgroundScheduler:
    """Start (or return) the singleton background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    sched = BackgroundScheduler(daemon=True, timezone="America/New_York")
    sched.add_job(
        _run_wpsr_fetch,
        CronTrigger(day_of_week="wed", hour=10, minute=30, timezone="America/New_York"),
        id=WPSR_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _run_fetch,
        CronTrigger(day_of_week="wed", hour=11, minute=30, timezone="America/New_York"),
        id=EIA_API_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    mark_scheduler_running(True)
    _sync_next_runs()
    logger.info("Scheduler started: WPSR Wed 10:30 ET, EIA API Wed 11:30 ET")
    return sched


def _run_wpsr_fetch() -> None:
    mark_started(WPSR_JOB_ID, "Fetching WPSR real-time summary CSVs.")
    try:
        from .wpsr_client import fetch_all_wpsr

        results = fetch_all_wpsr()
        success = all(results.values()) if results else False
        mark_finished(
            WPSR_JOB_ID,
            success,
            "WPSR real-time refresh complete." if success else "WPSR refresh completed with missing series.",
            results,
        )
        logger.info("WPSR real-time refresh complete: %s", results)
    except Exception as e:
        mark_finished(WPSR_JOB_ID, False, f"WPSR refresh failed: {e}")
        logger.exception("WPSR refresh failed: %s", e)
    finally:
        _sync_next_runs()


def _run_fetch() -> None:
    mark_started(EIA_API_JOB_ID, "Fetching EIA API v2 historical summary data.")
    try:
        counts = fetch_all()
        success = all(count >= 0 for count in counts.values()) if counts else False
        mark_finished(
            EIA_API_JOB_ID,
            success,
            "EIA API v2 historical refresh complete." if success else "EIA API refresh completed with failed series.",
            counts,
        )
        logger.info("Scheduled refresh complete: %s", counts)
    except Exception as e:
        mark_finished(EIA_API_JOB_ID, False, f"EIA API refresh failed: {e}")
        logger.exception("Scheduled refresh failed: %s", e)
    finally:
        _sync_next_runs()


def _sync_next_runs() -> None:
    if _scheduler is None:
        return
    for job_id in (WPSR_JOB_ID, EIA_API_JOB_ID):
        job = _scheduler.get_job(job_id)
        set_next_run(job_id, job.next_run_time if job is not None else None)
