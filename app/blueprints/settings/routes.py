from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.logger import log_error, log_action
from app.models import AppConfig, Story, db
from app.models.webauthn import WebAuthnCredential
import traceback
import os


@settings.route('/')
def index() -> ResponseReturnValue:
    from flask import url_for
    theme_config = AppConfig.query.filter_by(key='theme_preference').first()
    theme_preference = theme_config.get_value() if theme_config else 'system'
    enable_library = os.getenv('ENABLE_LIBRARY', 'true').lower() == 'true'
    passkeys = WebAuthnCredential.query.order_by(WebAuthnCredential.created_at).all()
    auto_lock_config = AppConfig.query.filter_by(key='auto_lock_timeout').first()
    auto_lock_timeout = int(auto_lock_config.get_value()) if auto_lock_config else 0
    auto_watch_config = AppConfig.query.filter_by(key='auto_watch_authors_enabled').first()
    auto_watch_enabled = auto_watch_config.get_value() if auto_watch_config else False
    auto_update_config = AppConfig.query.filter_by(key='auto_update_enabled').first()
    auto_update_enabled = auto_update_config.get_value() if auto_update_config else False

    opds_keys = ['opds_enabled', 'opds_auth_enabled', 'opds_username']
    opds_cfgs = {c.key: c for c in AppConfig.query.filter(AppConfig.key.in_(opds_keys)).all()}
    opds_enabled = opds_cfgs['opds_enabled'].get_value() if 'opds_enabled' in opds_cfgs else False
    opds_auth_enabled = opds_cfgs['opds_auth_enabled'].get_value() if 'opds_auth_enabled' in opds_cfgs else False
    opds_username = opds_cfgs['opds_username'].value if 'opds_username' in opds_cfgs else ''
    opds_url = url_for('opds.root', _external=True)

    return render_template(
        'settings.html',
        theme_preference=theme_preference,
        enable_library=enable_library,
        passkeys=passkeys,
        auto_lock_timeout=auto_lock_timeout,
        auto_watch_enabled=auto_watch_enabled,
        auto_update_enabled=auto_update_enabled,
        opds_enabled=opds_enabled,
        opds_auth_enabled=opds_auth_enabled,
        opds_username=opds_username,
        opds_url=opds_url,
    )


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


@settings.route('/repair-epub-metadata', methods=['POST'])
def repair_epub_metadata() -> ResponseReturnValue:
    try:
        from app.services.bulk_format_generator import BulkFormatGeneratorService
        service = BulkFormatGeneratorService()
        result = service.repair_all_epub_metadata()
        if result['errors']:
            return f'<p class="text-sm text-yellow-600 mt-2">Done: {result["repaired"]} repaired, {result["skipped"]} already clean, {len(result["errors"])} errors.</p>'
        return f'<p class="text-sm text-green-600 mt-2">Done: {result["repaired"]} repaired, {result["skipped"]} already clean.</p>'
    except Exception as e:
        log_error(f"Error in repair_epub_metadata: {str(e)}\n{traceback.format_exc()}")
        return '<p class="text-sm text-red-600 mt-2">An error occurred. Check the logs.</p>', 500


@settings.route('/auto-watch-enabled', methods=['GET'])
def get_auto_watch_enabled() -> ResponseReturnValue:
    try:
        cfg = AppConfig.query.filter_by(key='auto_watch_authors_enabled').first()
        enabled = cfg.get_value() if cfg else False
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        log_error(f"Error getting auto-watch setting: {str(e)}")
        return jsonify({"success": False, "message": "Error loading setting"}), 500


@settings.route('/toggle-auto-watch', methods=['POST'])
def toggle_auto_watch() -> ResponseReturnValue:
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        cfg = AppConfig.query.filter_by(key='auto_watch_authors_enabled').first()
        if cfg:
            cfg.set_value(enabled)
        else:
            cfg = AppConfig(
                key='auto_watch_authors_enabled',
                value='true' if enabled else 'false',
                value_type='bool',
                description='Auto-download new stories from watched authors on schedule'
            )
            db.session.add(cfg)
        db.session.commit()
        log_action(f"Auto-watch-authors setting changed to: {enabled}")
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error toggling auto-watch: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Error updating setting"}), 500


@settings.route('/opds', methods=['GET'])
def get_opds_settings() -> ResponseReturnValue:
    try:
        from flask import url_for
        keys = ['opds_enabled', 'opds_auth_enabled', 'opds_username']
        cfgs = {c.key: c for c in AppConfig.query.filter(AppConfig.key.in_(keys)).all()}
        return jsonify({
            'success': True,
            'opds_enabled': cfgs['opds_enabled'].get_value() if 'opds_enabled' in cfgs else False,
            'opds_auth_enabled': cfgs['opds_auth_enabled'].get_value() if 'opds_auth_enabled' in cfgs else False,
            'opds_username': cfgs['opds_username'].value if 'opds_username' in cfgs else '',
            'opds_url': url_for('opds.root', _external=True),
        })
    except Exception as e:
        log_error(f"Error getting OPDS settings: {str(e)}")
        return jsonify({'success': False, 'message': 'Error loading OPDS settings'}), 500


@settings.route('/opds', methods=['POST'])
def save_opds_settings() -> ResponseReturnValue:
    from werkzeug.security import generate_password_hash
    try:
        data = request.get_json()
        _missing = object()
        all_updates = {
            'opds_enabled': ('bool', data.get('opds_enabled', _missing)),
            'opds_auth_enabled': ('bool', data.get('opds_auth_enabled', _missing)),
            'opds_username': ('string', data.get('opds_username', _missing)),
        }
        updates = {k: (vt, v) for k, (vt, v) in all_updates.items() if v is not _missing}
        if 'opds_username' in updates:
            updates['opds_username'] = ('string', (updates['opds_username'][1] or '').strip())
        new_password = (data.get('opds_password') or '').strip()

        for key, (value_type, value) in updates.items():
            cfg = AppConfig.query.filter_by(key=key).first()
            if cfg:
                cfg.set_value(value)
            else:
                cfg = AppConfig(key=key, value_type=value_type, description='')
                cfg.set_value(value)
                db.session.add(cfg)

        if new_password:
            pw_cfg = AppConfig.query.filter_by(key='opds_password_hash').first()
            if pw_cfg:
                pw_cfg.value = generate_password_hash(new_password)
            else:
                pw_cfg = AppConfig(key='opds_password_hash', value_type='string',
                                   description='OPDS Basic Auth password (bcrypt hash)')
                pw_cfg.value = generate_password_hash(new_password)
                db.session.add(pw_cfg)

        db.session.commit()
        log_action("OPDS settings updated")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error saving OPDS settings: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Error saving OPDS settings'}), 500


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


