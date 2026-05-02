from __future__ import annotations
import time
from flask import render_template, request, redirect, url_for, session, jsonify
from app.models import AppConfig
from app.models.base import db
from app.models.webauthn import WebAuthnCredential
from . import auth


def _get_config(key: str) -> AppConfig | None:
    return AppConfig.query.filter_by(key=key).first()


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return '/'


@auth.route('/lock')
def lock():
    if WebAuthnCredential.query.count() == 0:
        return redirect('/')
    next_url = request.args.get('next', '/')
    return render_template('lock.html', next_url=next_url)


@auth.route('/lock-now', methods=['POST'])
def lock_now():
    session['unlocked'] = False
    session.modified = True
    return '', 204


@auth.route('/status')
def status():
    cred_count = WebAuthnCredential.query.count()
    if cred_count == 0:
        return jsonify({'unlocked': True, 'enabled': False, 'credentials_count': 0})
    return jsonify({
        'unlocked': bool(session.get('unlocked')),
        'enabled': True,
        'credentials_count': cred_count,
    })


@auth.route('/update-timeout', methods=['POST'])
def update_timeout():
    if not session.get('unlocked'):
        return jsonify({'success': False, 'message': 'Must be unlocked'}), 403

    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get('minutes', 0))
        if minutes not in (0, 30, 60, 120, 240):
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
                value_type='int', description='Lock timeout minutes (0=never, >0=inactivity threshold)'
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to save timeout'}), 500

    return jsonify({'success': True})
