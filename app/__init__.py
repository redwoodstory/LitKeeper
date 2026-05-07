from __future__ import annotations
from flask import Flask
import os
import time
import atexit
from datetime import datetime
from dotenv import load_dotenv
from typing import Any
from app.utils.paths import get_data_directory, get_stories_directory

load_dotenv()

# Build version identifier - update this when making significant changes
APP_VERSION = "2026.01.06-automation-fix"

def _is_cli_context() -> bool:
    """Detect if we're running under Flask CLI or a one-off script.

    When SKIP_BACKGROUND_WORKERS is set, or when the process was launched
    via the ``flask`` CLI entry-point, startup banners and background
    workers should be suppressed.
    """
    import sys
    if os.getenv('SKIP_BACKGROUND_WORKERS', '').lower() == 'true':
        return True
    argv0 = sys.argv[0] if sys.argv else ''
    if argv0.endswith('flask') or '/flask' in argv0:
        return True
    return False


def _validate_deployment_config():
    """Validate deployment configuration safety"""
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

    _cli_mode = _is_cli_context()

    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    if not _cli_mode:
        print(f"=" * 80)
        print(f"LitKeeper Version: {APP_VERSION}")
        print(f"Build: Production-ready deployment")
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
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    app.config['SESSION_COOKIE_HTTPONLY'] = True

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
        'pool_recycle': 1800,
        'pool_timeout': 30,
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
        from app.models import AppConfig

        config_defaults = [
            ('db_mode_enabled', 'false', 'bool', 'Whether database mode is active'),
            ('migration_completed', 'false', 'bool', 'Whether initial migration has completed'),
            ('migration_version', '1', 'int', 'Database schema version'),
            ('auto_refresh_metadata', 'false', 'bool', 'Auto-refresh missing metadata on startup'),
            ('auto_lock_timeout', '0', 'int', 'Lock timeout minutes (0=never, >0=inactivity threshold)'),
            ('opds_enabled', 'false', 'bool', 'Whether the OPDS catalog is enabled'),
            ('opds_auth_enabled', 'false', 'bool', 'Whether OPDS requires HTTP Basic Auth'),
            ('opds_username', '', 'string', 'OPDS Basic Auth username'),
            ('opds_password_hash', '', 'string', 'OPDS Basic Auth password (bcrypt hash)'),
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

    @app.template_filter('humanize_date')
    def humanize_date_filter(dt) -> str:
        """Convert datetime to human-readable format"""
        if not dt:
            return ''
        from datetime import datetime, timezone
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except:
                return dt
        
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        diff = now - dt
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days} day{"s" if days != 1 else ""} ago'
        else:
            return dt.strftime('%b %d, %Y')

    # Register Blueprints
    from .blueprints import api, library, downloads, errors, settings, highlights
    from .blueprints.epub import epub
    from .blueprints.auth import auth
    from .blueprints.queue import queue
    from .blueprints.authors import authors_bp
    from .blueprints.opds import opds_bp
    from .blueprints.auto_update_stories import auto_update_stories

    app.register_blueprint(api)
    app.register_blueprint(library)
    app.register_blueprint(downloads)
    app.register_blueprint(errors)
    app.register_blueprint(settings)
    app.register_blueprint(epub)
    app.register_blueprint(auth)
    app.register_blueprint(queue)
    app.register_blueprint(highlights)
    app.register_blueprint(authors_bp)
    app.register_blueprint(opds_bp)
    app.register_blueprint(auto_update_stories)

    from .commands import register_commands
    register_commands(app)

    from flask import request, redirect, url_for, session, jsonify
    from app.models import AppConfig

    _api_token = os.getenv('LITKEEPER_API_TOKEN', '')

    @app.before_request
    def enforce_api_token():
        if not _api_token:
            return
        api_prefixes = ('/api/', '/epub/api/', '/epub/file/', '/queue/api/', '/download/')
        if not request.path.startswith(api_prefixes):
            return
        # Valid Bearer token → iOS app, allow through
        if request.headers.get('Authorization') == f'Bearer {_api_token}':
            return
        # No Authorization header → web browser, allow through (enforce_pin_lock handles auth)
        if not request.headers.get('Authorization'):
            return
        return jsonify({'error': 'Unauthorized'}), 401

    @app.before_request
    def enforce_pin_lock():
        from flask import make_response as _make_response
        from app.models.webauthn import WebAuthnCredential
        # Bearer-authenticated requests (iOS app) are already validated by enforce_api_token
        if _api_token and request.headers.get('Authorization') == f'Bearer {_api_token}':
            return
        exempt_prefixes = ('/auth/', '/static/', '/favicon', '/settings/theme-preference', '/opds')
        if request.path.startswith(exempt_prefixes):
            return
        cred_count = WebAuthnCredential.query.count()
        if cred_count == 0:
            return
        # Transition mode: PIN was set but no passkeys registered yet — stay open
        pin_cfg = AppConfig.query.filter_by(key='pin_enabled').first()
        if pin_cfg and pin_cfg.get_value() and cred_count == 0:
            return
        lock_url = url_for('auth.lock', next=request.full_path)
        def _lock_response():
            # HTMX injects responses into swap targets, so a plain 302 would cause
            # the lock page HTML to be injected into a partial div instead of
            # replacing the full page. HX-Redirect triggers a proper navigation.
            if request.headers.get('HX-Request'):
                resp = _make_response('', 200)
                resp.headers['HX-Redirect'] = lock_url
                return resp
            return redirect(lock_url)
        if not session.get('unlocked'):
            return _lock_response()
        timeout_cfg = AppConfig.query.filter_by(key='auto_lock_timeout').first()
        minutes = int(timeout_cfg.value) if timeout_cfg else 0
        if minutes > 0:
            if time.time() - session.get('last_activity', 0) > minutes * 60:
                session['unlocked'] = False
                return _lock_response()
        session['last_activity'] = time.time()

    @app.context_processor
    def inject_auth_state():
        try:
            from app.models.webauthn import WebAuthnCredential
            cred_count = WebAuthnCredential.query.count()
            pin_cfg = AppConfig.query.filter_by(key='pin_enabled').first()
            in_pin_transition = bool(pin_cfg and pin_cfg.get_value()) and cred_count == 0
            timeout_cfg = AppConfig.query.filter_by(key='auto_lock_timeout').first()
            return {
                'credentials_registered': cred_count > 0,
                'in_pin_transition': in_pin_transition,
                'auto_lock_timeout': int(timeout_cfg.value) if timeout_cfg else 0,
            }
        except Exception:
            return {'credentials_registered': False, 'in_pin_transition': False, 'auto_lock_timeout': 0}

    from app.scheduler import init_scheduler, shutdown_scheduler
    init_scheduler(app)
    atexit.register(shutdown_scheduler)

    if not _cli_mode:
        def _repair_epub_metadata_background():
            import threading
            def _run():
                with app.app_context():
                    try:
                        from app.services.bulk_format_generator import BulkFormatGeneratorService
                        from app.models import Story, StoryFormat, AppConfig
                        from app.models.base import db
                        from datetime import datetime

                        # One-time migration: bump updated_at on all epub stories so the
                        # iOS sync detects the XHTML repair and re-downloads them.
                        migration_key = 'epub_xhtml_repair_notified'
                        already_done = AppConfig.query.filter_by(key=migration_key).first()
                        if not already_done:
                            epub_story_ids = {
                                f.story_id for f in StoryFormat.query.filter_by(format_type='epub').all()
                            }
                            if epub_story_ids:
                                now = datetime.utcnow()
                                Story.query.filter(Story.id.in_(epub_story_ids)).update(
                                    {Story.updated_at: now}, synchronize_session=False
                                )
                                flag = AppConfig(
                                    key=migration_key, value='true',
                                    value_type='bool',
                                    description='EPUB XHTML repair updated_at bump has run'
                                )
                                db.session.add(flag)
                                db.session.commit()
                                print(f"[startup] Bumped updated_at on {len(epub_story_ids)} epub stories for iOS re-sync")

                        result = BulkFormatGeneratorService().repair_all_epub_metadata()
                        if result['repaired'] > 0:
                            print(f"[startup] EPUB metadata repair: {result['repaired']} fixed, {result['skipped']} already clean")
                    except Exception as e:
                        print(f"[startup] EPUB metadata repair error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _repair_epub_metadata_background()

        def _migrate_filenames_background():
            import threading
            def _run():
                with app.app_context():
                    try:
                        from app.models import AppConfig
                        from app.models.base import db
                        migration_key = 'filenames_id_prefix_migrated'
                        already_done = AppConfig.query.filter_by(key=migration_key).first()
                        if already_done:
                            return
                        from app.services.migration.migrate_filenames_to_id_prefix import migrate_filenames_to_id_prefix
                        result = migrate_filenames_to_id_prefix()
                        flag = AppConfig(
                            key=migration_key, value='true',
                            value_type='bool',
                            description='Story files renamed to {id}_{filename_base} format'
                        )
                        db.session.add(flag)
                        db.session.commit()
                        print(f"[startup] Filename migration: {result.get('message', result)}")
                    except Exception as e:
                        print(f"[startup] Filename migration error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _migrate_filenames_background()

        def _migrate_covers_background():
            import threading
            def _run():
                with app.app_context():
                    try:
                        from app.models import AppConfig
                        from app.models.base import db
                        migration_key = 'covers_id_prefix_migrated'
                        already_done = AppConfig.query.filter_by(key=migration_key).first()
                        if already_done:
                            return
                        from app.services.migration.migrate_covers_to_id_prefix import migrate_covers_to_id_prefix
                        result = migrate_covers_to_id_prefix()
                        flag = AppConfig(
                            key=migration_key, value='true',
                            value_type='bool',
                            description='Story cover images renamed to {id}_{filename_base}.jpg format'
                        )
                        db.session.add(flag)
                        db.session.commit()
                        print(f"[startup] Cover migration: {result.get('message', result)}")
                    except Exception as e:
                        print(f"[startup] Cover migration error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _migrate_covers_background()

        def _backfill_missing_covers_background():
            import threading
            def _run():
                import time
                time.sleep(10)  # Let filename migration and other startup tasks settle first
                with app.app_context():
                    try:
                        from app.models import Story
                        from app.utils import get_cover_directory
                        from app.services.cover_generator import generate_cover_image, extract_cover_from_epub

                        cover_dir = get_cover_directory()
                        os.makedirs(cover_dir, exist_ok=True)

                        stories = Story.query.all()
                        generated = 0

                        for story in stories:
                            cover_filename = f"{story.id}_{story.filename_base}.jpg"
                            cover_path = os.path.join(cover_dir, cover_filename)

                            if os.path.exists(cover_path):
                                continue

                            author_name = story.author.name if story.author else 'Unknown Author'

                            epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
                            if epub_fmt and os.path.exists(epub_fmt.file_path):
                                try:
                                    if extract_cover_from_epub(epub_fmt.file_path, cover_path):
                                        generated += 1
                                        continue
                                except Exception:
                                    pass

                            generate_cover_image(story.title, author_name, cover_path)
                            generated += 1

                        if generated > 0:
                            print(f"[startup] Cover backfill: generated {generated} missing covers")
                    except Exception as e:
                        print(f"[startup] Cover backfill error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _backfill_missing_covers_background()

        def _backfill_seen_urls_background():
            """
            One-time startup migration: populate seen_literotica_urls from every
            existing Story record so that author re-scans correctly skip already-
            downloaded content.  Standalone story literotica_urls are inserted
            directly; series entries also have their series URL recorded so that
            series-URL dedup still works for any legacy queue items.
            """
            import threading
            def _run():
                with app.app_context():
                    try:
                        from app.models import AppConfig, Story, SeenLiteroticaUrl
                        from app.models.base import db

                        migration_key = 'seen_urls_backfilled'
                        already_done = AppConfig.query.filter_by(key=migration_key).first()
                        if already_done:
                            return

                        stories = Story.query.all()
                        inserted = 0
                        for story in stories:
                            urls = []
                            if story.literotica_url:
                                urls.append(story.literotica_url)
                            if story.literotica_series_url:
                                urls.append(story.literotica_series_url)
                            for url in urls:
                                if not SeenLiteroticaUrl.query.filter_by(url=url).first():
                                    db.session.add(SeenLiteroticaUrl(url=url, story_id=story.id))
                                    inserted += 1

                        flag = AppConfig(
                            key=migration_key,
                            value='true',
                            value_type='bool',
                            description='seen_literotica_urls backfilled from existing stories',
                        )
                        db.session.add(flag)
                        db.session.commit()
                        print(f"[startup] seen_urls backfill: inserted {inserted} URL records from {len(stories)} stories")
                    except Exception as e:
                        print(f"[startup] seen_urls backfill error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _backfill_seen_urls_background()

        def _self_heal_formats_background():
            """
            Startup self-heal: repair stale StoryFormat paths and enqueue generation
            of any missing EPUB or JSON formats. Runs every startup, fast (local I/O only).
            """
            import threading
            def _run():
                with app.app_context():
                    try:
                        import os as _os
                        from app.models import Story, StoryFormat, FormatQueueItem
                        from app.models.format_queue import FormatQueueItem as _FQI
                        from app.models.base import db
                        from app.services.story_processor import link_story_formats
                        from app.services.logger import log_action

                        epub_queued = 0
                        json_queued = 0
                        for story in Story.query.all():
                            link_story_formats(story)

                            json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
                            epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
                            json_ok = json_fmt and _os.path.exists(json_fmt.file_path)
                            epub_ok = epub_fmt and _os.path.exists(epub_fmt.file_path)

                            if json_ok and not epub_ok:
                                if not _FQI.query.filter_by(story_id=story.id, job_type='generate_epub', status='pending').first():
                                    db.session.add(_FQI(story_id=story.id, job_type='generate_epub', method='auto'))
                                    epub_queued += 1

                            if epub_ok and not json_ok:
                                if not _FQI.query.filter_by(story_id=story.id, job_type='generate_json', status='pending').first():
                                    db.session.add(_FQI(story_id=story.id, job_type='generate_json', method='auto'))
                                    json_queued += 1

                        db.session.commit()
                        log_action(f"[STARTUP] Format self-heal: queued {epub_queued} EPUB and {json_queued} JSON generation jobs.")
                    except Exception as e:
                        print(f"[startup] Format self-heal error: {e}")
            threading.Thread(target=_run, daemon=True).start()

        _self_heal_formats_background()

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

        from app.services.format_queue_worker import FormatQueueWorker
        format_worker = FormatQueueWorker(app, poll_interval=5)
        format_worker.start()
        atexit.register(format_worker.stop)

    return app