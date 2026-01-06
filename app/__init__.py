from __future__ import annotations
from flask import Flask
import os
import atexit
from datetime import datetime
from dotenv import load_dotenv
from typing import Any

load_dotenv()

def create_app() -> Flask:
    app = Flask(__name__)

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
                with open(secret_key_file, 'w') as f:
                    f.write(secret_key)
                print(f"Generated and saved new SECRET_KEY to {secret_key_file}")
            except Exception as e:
                print(f"Warning: Could not save secret key to file: {e}")
                print("Using temporary key. Sessions will not persist across restarts.")

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
    }

    db.init_app(app)
    migrate = Migrate(app, db)

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

    from app.services.download_queue_worker import DownloadQueueWorker
    worker = DownloadQueueWorker(app, poll_interval=5)
    worker.start()
    atexit.register(worker.stop)

    from app.services.background_automation import BackgroundAutomation
    automation = BackgroundAutomation(app)
    automation.start()
    atexit.register(automation.stop)

    return app