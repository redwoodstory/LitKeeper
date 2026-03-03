from __future__ import annotations
import time
import os
from flask import render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import AppConfig
from app.models.base import db
from . import auth


def _get_config(key: str) -> AppConfig | None:
    return AppConfig.query.filter_by(key=key).first()


def _pin_enabled() -> bool:
    cfg = _get_config('pin_enabled')
    return bool(cfg and cfg.get_value())


def _safe_next(next_url: str | None) -> str:
    """Return next_url if it's a relative path, otherwise home."""
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return '/'


@auth.route('/lock')
def lock():
    if not _pin_enabled():
        return redirect('/')
    # Always render the lock page (200) so the SW can reliably pre-cache it.
    # Client-side JS in lock.html redirects away if the session is already unlocked.
    next_url = request.args.get('next', '/')
    return render_template('lock.html', next_url=next_url)


@auth.route('/verify', methods=['POST'])
def verify():
    if not _pin_enabled():
        return jsonify({'success': False, 'message': 'PIN lock is not enabled'}), 400

    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin', ''))

    if not (4 <= len(pin) <= 8) or not pin.isdigit():
        return jsonify({'success': False, 'message': 'Invalid PIN format'}), 400

    pin_cfg = _get_config('pin_hash')
    stored_hash = pin_cfg.value if pin_cfg else ''

    if not stored_hash or not check_password_hash(stored_hash, pin):
        return jsonify({'success': False, 'message': 'Incorrect PIN'}), 401

    session['pin_unlocked'] = True
    session['last_activity'] = time.time()
    session.modified = True

    next_url = _safe_next(data.get('next'))
    return jsonify({'success': True, 'redirect': next_url})


@auth.route('/lock-now', methods=['POST'])
def lock_now():
    session['pin_unlocked'] = False
    session.modified = True
    return '', 204


@auth.route('/status')
def status():
    if not _pin_enabled():
        return jsonify({'unlocked': True, 'enabled': False})
    return jsonify({'unlocked': bool(session.get('pin_unlocked')), 'enabled': True})


@auth.route('/set-pin', methods=['POST'])
def set_pin():
    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin', ''))

    if not (4 <= len(pin) <= 8) or not pin.isdigit():
        return jsonify({'success': False, 'message': 'PIN must be 4–8 digits'}), 400

    pin_hash = generate_password_hash(pin)

    try:
        hash_cfg = _get_config('pin_hash')
        if hash_cfg:
            hash_cfg.value = pin_hash
        else:
            db.session.add(AppConfig(
                key='pin_hash', value=pin_hash,
                value_type='string', description='Hashed PIN for lock screen'
            ))

        enabled_cfg = _get_config('pin_enabled')
        if enabled_cfg:
            enabled_cfg.set_value(True)
        else:
            db.session.add(AppConfig(
                key='pin_enabled', value='true',
                value_type='bool', description='Whether PIN lock is enabled'
            ))

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to save PIN'}), 500

    session['pin_unlocked'] = True
    session['last_activity'] = time.time()
    session.modified = True

    return jsonify({'success': True, 'message': 'PIN lock enabled'})


@auth.route('/remove-pin', methods=['POST'])
def remove_pin():
    if not session.get('pin_unlocked'):
        return jsonify({'success': False, 'message': 'Must be unlocked to remove PIN'}), 403

    try:
        enabled_cfg = _get_config('pin_enabled')
        if enabled_cfg:
            enabled_cfg.set_value(False)

        hash_cfg = _get_config('pin_hash')
        if hash_cfg:
            hash_cfg.value = ''

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to remove PIN'}), 500

    session.pop('pin_unlocked', None)
    session.pop('last_activity', None)
    session.modified = True

    return jsonify({'success': True, 'message': 'PIN lock removed'})


@auth.route('/update-timeout', methods=['POST'])
def update_timeout():
    if not session.get('pin_unlocked'):
        return jsonify({'success': False, 'message': 'Must be unlocked'}), 403

    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get('minutes', 0))
        if minutes not in (0, 5, 15, 30):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid timeout value'}), 400

    try:
        cfg = _get_config('auto_lock_timeout')
        if cfg:
            cfg.set_value(minutes)
        else:
            db.session.add(AppConfig(
                key='auto_lock_timeout', value=str(minutes),
                value_type='int', description='Lock timeout minutes (0=on background)'
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to save timeout'}), 500

    return jsonify({'success': True})


@auth.route('/reset-pin', methods=['POST'])
def reset_pin():
    if not _pin_enabled():
        return jsonify({'success': False, 'message': 'PIN lock is not enabled'}), 400

    reset_code_env = os.getenv('PIN_RESET_CODE', '').strip()
    if not reset_code_env:
        return jsonify({'success': False, 'message': 'PIN reset is not configured'}), 403

    data = request.get_json(silent=True) or {}
    provided_code = str(data.get('reset_code', '')).strip()

    if not provided_code or provided_code != reset_code_env:
        return jsonify({'success': False, 'message': 'Invalid reset code'}), 401

    try:
        enabled_cfg = _get_config('pin_enabled')
        if enabled_cfg:
            enabled_cfg.set_value(False)

        hash_cfg = _get_config('pin_hash')
        if hash_cfg:
            hash_cfg.value = ''

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to reset PIN'}), 500

    session.pop('pin_unlocked', None)
    session.pop('last_activity', None)
    session.modified = True

    return jsonify({'success': True, 'message': 'PIN has been reset. You can now set a new PIN in Settings.'})
