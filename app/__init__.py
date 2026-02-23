from __future__ import annotations
from flask import Flask
import os
import atexit
from datetime import datetime
from dotenv import load_dotenv
from typing import Any
from app.utils.paths import get_data_directory, get_stories_directory

load_dotenv()

# Build version identifier - update this when making significant changes
APP_VERSION = "2026.01.06-automation-fix"

def _validate_deployment_config():
    """Validate deployment configuration safety"""
    import sys

    db_uri = os.getenv('SQLALCHEMY_DATABASE_URI', '')
    if 'sqlite' in db_uri.lower() or not db_uri:
        print("INFO: SQLite detected - single worker required")

    skip_workers = os.getenv('SKIP_BACKGROUND_WORKERS', 'false').lower() == 'true'
    if skip_workers:
        print("INFO: Background workers disabled")
    else:
        print("INFO: Embedded workers enabled (3 threads)")


def create_app() -> Flask:
    app = Flask(__name__)

    print(f"=" * 80)
    print(f"LitKeeper Version: {APP_VERSION}")
    print(f"Build: Production-ready multi-user deployment")
    print(f"[CONFIG] Data Directory: {get_data_directory()}")
    print(f"[CONFIG] Stories Directory: {get_stories_directory()}")
    print(f"=" * 80)

    _validate_deployment_config()

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        secret_key_file = os.path.join('app', 'data', 'secret.key')
        os.makedirs(os.path.dirname(secret_key_file), exist_ok=True)
        
        if os.path.exists(secret_key_file):
            try:
                with open(secret_key_file, 'r') as f:
                    secret_key = f.read().strip()
                print(f"Loaded SECRET_KEY from {secret_key_file}")
            except Exception as e:
                print(f"Error reading secret key file: {e}")
                secret_key = None
        
        if not secret_key:
            import secrets
            secret_key = secrets.token_hex(32)
            try:
                os.makedirs(os.path.dirname(secret_key_file), mode=0o750, exist_ok=True)

                fd = os.open(secret_key_file, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as f:
                    f.write(secret_key)

                print(f"Generated SECRET_KEY with mode 0600: {secret_key_file}")
            except FileExistsError:
                with open(secret_key_file, 'r') as f:
                    secret_key = f.read().strip()
            except Exception as e:
                print(f"Warning: Could not save secret key: {e}")
                print("Using temporary key - sessions won't persist")

    app.config['SECRET_KEY'] = secret_key

    app.config['UPLOAD_FOLDER'] = "app/epub_files"  # Directory to store EPUB files

    # Database configuration
    from flask_migrate import Migrate
    from app.models.base import db

    data_directory = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_directory, exist_ok=True)

    stories_directory = os.path.join(os.path.dirname(__file__), 'stories')
    os.makedirs(os.path.join(stories_directory, 'epubs'), exist_ok=True)
    os.makedirs(os.path.join(stories_directory, 'html'), exist_ok=True)
    os.makedirs(os.path.join(stories_directory, 'covers'), exist_ok=True)

    database_path = os.path.join(data_directory, 'litkeeper.db')

    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False,
        },
    }

    db.init_app(app)
    migrate = Migrate(app, db)

    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        if 'sqlite' in str(type(dbapi_conn)):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    with app.app_context():
        db.create_all()

        from app.models import AppConfig

        config_defaults = [
            ('db_mode_enabled', 'false', 'bool', 'Whether database mode is active'),
            ('migration_completed', 'false', 'bool', 'Whether initial migration has completed'),
            ('migration_version', '1', 'int', 'Database schema version'),
            ('auto_refresh_metadata', 'false', 'bool', 'Auto-refresh missing metadata on startup'),
        ]

        for key, value, value_type, description in config_defaults:
            existing = AppConfig.query.filter_by(key=key).first()
            if not existing:
                config = AppConfig(key=key, value=value, value_type=value_type, description=description)
                db.session.add(config)

        try:
            db.session.commit()
        except:
            db.session.rollback()

    # Register template filters
    @app.template_filter('format_date')
    def format_date(value: Any) -> str:
        if not value:
            return ''
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
            else:
                dt = value
            return dt.strftime('%b %d, %Y')
        except:
            return value

    @app.template_filter('format_size')
    def format_size(bytes: Any) -> str:
        if not bytes:
            return ''
        try:
            bytes = int(bytes)
            if bytes < 1024:
                return f'{bytes} B'
            elif bytes < 1024 * 1024:
                return f'{bytes / 1024:.1f} KB'
            else:
                return f'{bytes / (1024 * 1024):.1f} MB'
        except:
            return ''

    @app.template_filter('format_word_count')
    def format_word_count(count: Any) -> str:
        if not count:
            return ''
        try:
            count = int(count)
            if count < 1000:
                return f'{count} words'
            else:
                return f'{count / 1000:.1f}k words'
        except:
            return ''

    @app.template_filter('basename')
    def basename_filter(path: str) -> str:
        if not path:
            return ''
        return os.path.basename(path)

    # Register Blueprints
    from .blueprints import api, library, downloads, errors, settings
    from .blueprints.admin import admin
    from .blueprints.epub import epub

    app.register_blueprint(api)
    app.register_blueprint(library)
    app.register_blueprint(downloads)
    app.register_blueprint(errors)
    app.register_blueprint(admin)
    app.register_blueprint(settings)
    app.register_blueprint(epub)

    from app.scheduler import init_scheduler, shutdown_scheduler
    init_scheduler(app)
    atexit.register(shutdown_scheduler)

    if os.getenv('SKIP_BACKGROUND_WORKERS') != 'true':
        from app.services.download_queue_worker import DownloadQueueWorker
        worker = DownloadQueueWorker(app, poll_interval=5)
        worker.start()
        atexit.register(worker.stop)

        from app.services.metadata_refresh_worker import MetadataRefreshWorker
        metadata_worker = MetadataRefreshWorker(app, poll_interval=5)
        metadata_worker.start()
        atexit.register(metadata_worker.stop)

        from app.services.background_automation import BackgroundAutomation
        automation = BackgroundAutomation(app)
        app.automation = automation
        automation.start()
        atexit.register(automation.stop)

    return app