from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.logger import log_error, log_action
from app.models import AppConfig, Story, db
import traceback
import os


@settings.route('/')
def index() -> ResponseReturnValue:
    theme_config = AppConfig.query.filter_by(key='theme_preference').first()
    theme_preference = theme_config.get_value() if theme_config else 'system'
    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
    return render_template('settings.html', theme_preference=theme_preference, enable_library=enable_library)


@settings.route('/theme-preference', methods=['GET'])
def get_theme_preference() -> ResponseReturnValue:
    try:
        theme_config = AppConfig.query.filter_by(key='theme_preference').first()
        theme = theme_config.get_value() if theme_config else 'system'
        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        error_msg = f"Error getting theme preference: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error loading theme preference"}), 500


@settings.route('/theme-preference', methods=['POST'])
def save_theme_preference() -> ResponseReturnValue:
    try:
        data = request.get_json()
        theme = data.get('theme', 'system')

        if theme not in ['light', 'dark', 'system']:
            return jsonify({"success": False, "message": "Invalid theme value"}), 400

        theme_config = AppConfig.query.filter_by(key='theme_preference').first()
        if theme_config:
            theme_config.set_value(theme)
        else:
            theme_config = AppConfig(
                key='theme_preference',
                value=theme,
                value_type='string',
                description='User theme preference (light, dark, or system)'
            )
            db.session.add(theme_config)

        db.session.commit()
        log_action(f"Theme preference updated to: {theme}")

        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error saving theme preference: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error saving theme preference"}), 500


@settings.route('/auto-update-enabled', methods=['GET'])
def get_auto_update_enabled() -> ResponseReturnValue:
    try:
        auto_update_config = AppConfig.query.filter_by(key='auto_update_enabled').first()
        enabled = auto_update_config.get_value() if auto_update_config else False
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        error_msg = f"Error getting auto-update setting: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error loading auto-update setting"}), 500


def _cron_to_readable(cron_schedule: str) -> str:
    """Convert cron schedule to human-readable format (UTC time)."""
    try:
        parts = cron_schedule.strip().split()
        if len(parts) != 5:
            return cron_schedule
        
        minute = parts[0]
        hour = parts[1]
        day_of_week = parts[4]
        
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        day_name = day_names[int(day_of_week)] if day_of_week.isdigit() and 0 <= int(day_of_week) <= 6 else f"day {day_of_week}"
        
        hour_int = int(hour) if hour.isdigit() else 0
        minute_int = int(minute) if minute.isdigit() else 0
        
        time_str = f"{hour_int:02d}:{minute_int:02d} UTC"
        
        return f"Weekly on {day_name} at {time_str}"
    except Exception:
        return cron_schedule


@settings.route('/auto-update-schedule', methods=['GET'])
def get_auto_update_schedule() -> ResponseReturnValue:
    try:
        from flask import current_app
        
        schedule_config = AppConfig.query.filter_by(key='auto_update_cron_schedule').first()
        if schedule_config:
            schedule = schedule_config.get_value()
            return jsonify({
                "success": True,
                "schedule": schedule,
                "schedule_readable": _cron_to_readable(schedule),
                "source": "database"
            })
        
        active_cron = current_app.config.get('ACTIVE_CRON')
        if active_cron:
            return jsonify({
                "success": True,
                "schedule": active_cron,
                "schedule_readable": _cron_to_readable(active_cron),
                "source": "app_config"
            })
        
        return jsonify({
            "success": True,
            "schedule": None,
            "schedule_readable": None,
            "source": None,
            "message": "No schedule configured yet. Will be generated on first startup."
        })
    except Exception as e:
        error_msg = f"Error getting auto-update schedule: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error loading schedule"}), 500


@settings.route('/regenerate-covers-new', methods=['POST'])
def regenerate_covers() -> ResponseReturnValue:
    try:
        from app.services.bulk_format_generator import BulkFormatGeneratorService
        service = BulkFormatGeneratorService()
        result = service.regenerate_all_covers()
        if result['failed'] > 0:
            return f'<p class="text-sm text-yellow-600 mt-2">Done: {result["successful"]} succeeded, {result["failed"]} failed.</p>'
        return f'<p class="text-sm text-green-600 mt-2">Done: regenerated {result["successful"]} covers.</p>'
    except Exception as e:
        log_error(f"Error in regenerate_covers: {str(e)}\n{traceback.format_exc()}")
        return '<p class="text-sm text-red-600 mt-2">An error occurred. Check the logs.</p>', 500


@settings.route('/toggle-auto-update', methods=['POST'])
def toggle_auto_update() -> ResponseReturnValue:
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)

        auto_update_config = AppConfig.query.filter_by(key='auto_update_enabled').first()
        if auto_update_config:
            auto_update_config.set_value(enabled)
        else:
            auto_update_config = AppConfig(
                key='auto_update_enabled',
                value='true' if enabled else 'false',
                value_type='bool',
                description='Global setting to enable/disable automatic story updates'
            )
            db.session.add(auto_update_config)

        db.session.commit()
        log_action(f"Auto-update setting changed to: {enabled}")

        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error toggling auto-update: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error updating auto-update setting"}), 500


