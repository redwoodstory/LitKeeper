from __future__ import annotations
import os
import json
import time
from flask import request, session, jsonify
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from app.models.base import db
from app.models.webauthn import WebAuthnCredential
from . import auth


_RP_NAME = "LitKeeper"
_USER_ID = b"litkeeper_owner"
_USER_NAME = "owner"


def _rp_id() -> str:
    # Env var wins; otherwise strip port from request host (e.g. "myapp.example.com")
    return os.getenv('WEBAUTHN_RP_ID') or request.host.split(':')[0]


def _origin() -> str:
    # Env var wins; otherwise reconstruct from request (e.g. "https://myapp.example.com")
    return os.getenv('WEBAUTHN_ORIGIN') or request.host_url.rstrip('/')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@auth.route('/webauthn/register/begin')
def webauthn_register_begin():
    if not session.get('unlocked') and WebAuthnCredential.query.count() > 0:
        return jsonify({'error': 'Must be unlocked to register a new passkey'}), 403

    existing = WebAuthnCredential.query.all()
    exclude = [c.credential_id for c in existing]

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_RP_NAME,
        user_id=_USER_ID,
        user_name=_USER_NAME,
        user_display_name="LitKeeper Owner",
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude,
    )

    session['webauthn_register_challenge'] = options.challenge
    return options_to_json(options), 200, {'Content-Type': 'application/json'}


@auth.route('/webauthn/register/complete', methods=['POST'])
def webauthn_register_complete():
    challenge = session.pop('webauthn_register_challenge', None)
    if not challenge:
        return jsonify({'error': 'No registration challenge in session'}), 400

    if not session.get('unlocked') and WebAuthnCredential.query.count() > 0:
        return jsonify({'error': 'Must be unlocked to register a new passkey'}), 403

    data = request.get_json(silent=True) or {}
    device_name = str(data.get('device_name', '')).strip()[:100] or None

    try:
        credential = verify_registration_response(
            credential=data,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
        )
    except Exception as exc:
        return jsonify({'error': f'Registration failed: {exc}'}), 400

    transports = json.dumps(credential.credential_device_type if hasattr(credential, 'credential_device_type') else [])

    row = WebAuthnCredential(
        credential_id=credential.credential_id,
        public_key=credential.credential_public_key,
        sign_count=credential.sign_count,
        transports=transports,
        device_name=device_name,
    )
    db.session.add(row)

    # Clean up legacy PIN config on first passkey registration
    from app.models import AppConfig
    for key in ('pin_enabled', 'pin_hash'):
        cfg = AppConfig.query.filter_by(key=key).first()
        if cfg:
            db.session.delete(cfg)

    db.session.commit()

    session['unlocked'] = True
    session['last_activity'] = time.time()
    session.modified = True

    return jsonify({'success': True, 'credential': {
        'id': row.id,
        'device_name': row.device_name,
        'created_at': row.created_at.strftime('%b %-d, %Y'),
    }})


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@auth.route('/webauthn/authenticate/begin')
def webauthn_authenticate_begin():
    credentials = WebAuthnCredential.query.all()
    if not credentials:
        return jsonify({'error': 'No passkeys registered'}), 404

    options = generate_authentication_options(
        rp_id=_rp_id(),
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    session['webauthn_auth_challenge'] = options.challenge
    return options_to_json(options), 200, {'Content-Type': 'application/json'}


@auth.route('/webauthn/authenticate/complete', methods=['POST'])
def webauthn_authenticate_complete():
    challenge = session.pop('webauthn_auth_challenge', None)
    if not challenge:
        return jsonify({'error': 'No authentication challenge in session'}), 400

    data = request.get_json(silent=True) or {}

    raw_id = data.get('rawId') or data.get('id', '')
    # credential_id is bytes; rawId arrives as base64url string
    import base64

    def _b64url_decode(s: str) -> bytes:
        s = s.replace('-', '+').replace('_', '/')
        pad = 4 - len(s) % 4
        if pad != 4:
            s += '=' * pad
        return base64.b64decode(s)

    try:
        cred_id_bytes = _b64url_decode(raw_id)
    except Exception:
        return jsonify({'error': 'Invalid credential id'}), 400

    row = WebAuthnCredential.query.filter_by(credential_id=cred_id_bytes).first()
    if not row:
        return jsonify({'error': 'Unknown credential'}), 401

    try:
        auth_result = verify_authentication_response(
            credential=data,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=row.public_key,
            credential_current_sign_count=row.sign_count,
        )
    except Exception as exc:
        return jsonify({'error': f'Authentication failed: {exc}'}), 401

    row.sign_count = auth_result.new_sign_count
    db.session.commit()

    session['unlocked'] = True
    session['last_activity'] = time.time()
    session.modified = True

    next_url = data.get('next', '/')
    if not (next_url and next_url.startswith('/') and not next_url.startswith('//')):
        next_url = '/'

    return jsonify({'success': True, 'redirect': next_url})


# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------

@auth.route('/webauthn/credentials')
def webauthn_credentials():
    if not session.get('unlocked'):
        return jsonify({'error': 'Must be unlocked'}), 403
    rows = WebAuthnCredential.query.order_by(WebAuthnCredential.created_at).all()
    return jsonify([
        {'id': r.id, 'device_name': r.device_name, 'created_at': r.created_at.isoformat()}
        for r in rows
    ])


@auth.route('/webauthn/credential/<int:cred_id>', methods=['DELETE'])
def webauthn_delete_credential(cred_id: int):
    if not session.get('unlocked'):
        return jsonify({'error': 'Must be unlocked'}), 403

    row = WebAuthnCredential.query.get(cred_id)
    if not row:
        return jsonify({'error': 'Credential not found'}), 404

    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Emergency reset via env-var code
# ---------------------------------------------------------------------------

@auth.route('/webauthn/reset', methods=['POST'])
def webauthn_reset():
    reset_code_env = os.getenv('WEBAUTHN_RESET_CODE', '').strip()
    if not reset_code_env:
        return jsonify({'error': 'Reset not configured'}), 403

    data = request.get_json(silent=True) or {}
    provided = str(data.get('reset_code', '')).strip()

    if not provided or provided != reset_code_env:
        return jsonify({'error': 'Invalid reset code'}), 401

    WebAuthnCredential.query.delete()
    db.session.commit()

    session.pop('unlocked', None)
    session.pop('last_activity', None)
    session.modified = True

    return jsonify({'success': True, 'message': 'All passkeys removed. Register a new one in Settings.'})
