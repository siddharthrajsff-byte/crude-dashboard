"""Background scheduler: refresh EIA data every Wednesday at 10:30 AM ET."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .fetch_all import fetch_all

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """Start (or return) the singleton background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    sched = BackgroundScheduler(daemon=True, timezone="America/New_York")
    sched.add_job(
        _run_fetch,
        CronTrigger(day_of_week="wed", hour=10, minute=30),
        id="eia_weekly_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started: EIA refresh every Wed 10:30 ET")
    return sched


def _run_fetch() -> None:
    try:
        counts = fetch_all()
        logger.info("Scheduled refresh complete: %s", counts)
    except Exception as e:
        logger.exception("Scheduled refresh failed: %s", e)
