#!/usr/bin/env python3
"""
CLI utility to reset the PIN lock.

Usage:
    python reset_pin.py

This script can be run directly on the server or inside the Docker container
to reset the PIN without needing the web interface.
"""

from app import create_app
from app.models import AppConfig
from app.models.base import db


def reset_pin():
    app = create_app()
    
    with app.app_context():
        try:
            enabled_cfg = AppConfig.query.filter_by(key='pin_enabled').first()
            hash_cfg = AppConfig.query.filter_by(key='pin_hash').first()
            
            if not enabled_cfg or not enabled_cfg.get_value():
                print("✓ PIN lock is not currently enabled.")
                return
            
            enabled_cfg.set_value(False)
            
            if hash_cfg:
                hash_cfg.value = ''
            
            db.session.commit()
            
            print("✓ PIN lock has been reset successfully!")
            print("  You can now access the app and set a new PIN in Settings.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error resetting PIN: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    exit(reset_pin())
