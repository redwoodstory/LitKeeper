#!/usr/bin/env python3
"""
CLI utility to clear all registered passkeys.

Usage:
    python reset_webauthn.py

Run directly on the server or inside the Docker container when you've lost
access to all registered passkeys and cannot unlock via the web interface.
After running this script, the app will be fully open — register a new passkey
in Settings → Security.
"""

from app import create_app
from app.models.webauthn import WebAuthnCredential
from app.models.base import db


def reset_webauthn():
    app = create_app()

    with app.app_context():
        try:
            count = WebAuthnCredential.query.count()

            if count == 0:
                print("✓ No passkeys are registered.")
                return 0

            WebAuthnCredential.query.delete()
            db.session.commit()

            print(f"✓ Removed {count} passkey(s) successfully.")
            print("  The app is now open. Register a new passkey in Settings → Security.")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error removing passkeys: {e}")
            return 1

    return 0


if __name__ == "__main__":
    exit(reset_webauthn())
