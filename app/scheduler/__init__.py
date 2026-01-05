from __future__ import annotations
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask
import os
from typing import Optional

_scheduler: Optional[BackgroundScheduler] = None

def init_scheduler(app: Flask) -> None:
    """Initialize APScheduler with Flask app context."""
    global _scheduler

    if _scheduler is not None:
        return

    cron_schedule = os.getenv('AUTO_UPDATE_SCHEDULE')
    if not cron_schedule:
        app.logger.info("Auto-updates disabled (AUTO_UPDATE_SCHEDULE not set)")
        return

    _scheduler = BackgroundScheduler(daemon=True)

    from app.services.story_update_checker import check_all_stories_for_updates

    try:
        trigger = CronTrigger.from_crontab(cron_schedule)
        _scheduler.add_job(
            func=lambda: check_all_stories_for_updates(app),
            trigger=trigger,
            id='story_update_checker',
            name='Check stories for updates',
            replace_existing=True
        )

        _scheduler.start()
        app.logger.info(f"Story update checker scheduled: {cron_schedule}")
    except Exception as e:
        app.logger.error(f"Failed to initialize scheduler: {str(e)}")

def get_scheduler() -> Optional[BackgroundScheduler]:
    """Get the scheduler instance."""
    return _scheduler

def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        _scheduler = None
