from __future__ import annotations
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask
import os
import random
import time
from typing import Optional

_scheduler: Optional[BackgroundScheduler] = None

def _get_or_generate_cron_schedule(app: Flask) -> Optional[str]:
    """
    Get cron schedule from database or generate new random schedule.
    Returns the schedule string to be used by APScheduler.
    """
    from app.models import AppConfig, db
    
    with app.app_context():
        config = AppConfig.query.filter_by(key='auto_update_cron_schedule').first()
        
        if config:
            saved_schedule = config.get_value()
            app.logger.info(f"Using saved auto-update schedule from database: {saved_schedule}")
            app.config['ACTIVE_CRON'] = saved_schedule
            return saved_schedule
        
        random_minute = random.randint(0, 59)
        random_hour = random.randint(0, 23)
        random_day = random.randint(0, 6)
        random_schedule = f"{random_minute} {random_hour} * * {random_day}"
        
        new_config = AppConfig(
            key='auto_update_cron_schedule',
            value=random_schedule,
            value_type='string',
            description='Auto-generated random cron schedule for story updates (weekly)'
        )
        db.session.add(new_config)
        db.session.commit()
        
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        app.logger.info(f"Generated random auto-update schedule: {random_schedule} (weekly on {day_names[random_day]})")
        app.logger.info("This schedule is saved to the database and will persist across container restarts.")
        app.logger.info("Auto-updates are DISABLED by default. Enable in Settings UI after reviewing the schedule.")
        app.config['ACTIVE_CRON'] = random_schedule
        
        return saved_schedule

def init_scheduler(app: Flask) -> None:
    """Initialize APScheduler with Flask app context."""
    global _scheduler

    if _scheduler is not None:
        return

    cron_schedule = _get_or_generate_cron_schedule(app)
    if not cron_schedule:
        app.logger.info("Auto-updates disabled (no AUTO_UPDATE_SCHEDULE set)")
        return

    _scheduler = BackgroundScheduler(daemon=True)

    from app.services.story_update_checker import check_all_stories_for_updates

    try:
        trigger = CronTrigger.from_crontab(cron_schedule)
        
        jitter_seconds = random.randint(0, 3600)
        jitter_minutes = jitter_seconds // 60
        
        def delayed_update_check():
            app.logger.info(f"Auto-update triggered, waiting {jitter_minutes} minutes (jitter) before starting...")
            time.sleep(jitter_seconds)
            check_all_stories_for_updates(app)
        
        _scheduler.add_job(
            func=delayed_update_check,
            trigger=trigger,
            id='story_update_checker',
            name='Check stories for updates',
            replace_existing=True
        )

        _scheduler.start()
        app.logger.info(f"Story update checker scheduled: {cron_schedule} (with 0-60 min random jitter)")
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
