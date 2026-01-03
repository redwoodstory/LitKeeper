from __future__ import annotations
from app.models import AppConfig

class ModeDetector:
    """Detects whether the app is running in database or file-based mode"""

    @staticmethod
    def is_database_mode() -> bool:
        """Check if database mode is enabled"""
        try:
            config = AppConfig.query.filter_by(key='db_mode_enabled').first()
            return config and config.get_value() is True
        except:
            return False

    @staticmethod
    def is_migration_completed() -> bool:
        """Check if initial migration has completed"""
        try:
            config = AppConfig.query.filter_by(key='migration_completed').first()
            return config and config.get_value() is True
        except:
            return False

    @staticmethod
    def enable_database_mode():
        """Enable database mode"""
        try:
            from app.models.base import db
            config = AppConfig.query.filter_by(key='db_mode_enabled').first()
            if config:
                config.set_value(True)
                db.session.commit()
        except:
            pass

    @staticmethod
    def disable_database_mode():
        """Disable database mode (rollback to file-based)"""
        try:
            from app.models.base import db
            config = AppConfig.query.filter_by(key='db_mode_enabled').first()
            if config:
                config.set_value(False)
                db.session.commit()
        except:
            pass
