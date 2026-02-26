from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.logger import log_error, log_action
from app.models import AppConfig, Story, db
import traceback


@settings.route('/')
def index() -> ResponseReturnValue:
    theme_config = AppConfig.query.filter_by(key='theme_preference').first()
    theme_preference = theme_config.get_value() if theme_config else 'system'
    return render_template('settings.html', theme_preference=theme_preference)


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
        enabled = auto_update_config.get_value() if auto_update_config else True
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        error_msg = f"Error getting auto-update setting: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error loading auto-update setting"}), 500


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
                value=enabled,
                value_type='boolean',
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


