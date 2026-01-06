from flask import render_template, jsonify, request
from . import admin
from app.services.migration.migrator import DatabaseMigrator
from app.services.migration.file_scanner import FileScanner
from app.services.migration.sync_checker import SyncChecker
from app.services.mode_detector import ModeDetector
from app.models import AppConfig, Story, Author, Category, Tag, MigrationLog, StoryFormat
from app.models.base import db
import uuid
import threading

active_migrations = {}

@admin.route('/migration')
def migration_page():
    """Render migration dashboard page"""
    scanner = FileScanner()
    file_counts = scanner.get_file_count()

    db_mode = ModeDetector.is_database_mode()
    migration_completed = ModeDetector.is_migration_completed()

    story_count = Story.query.count() if db_mode else 0
    author_count = Author.query.count() if db_mode else 0
    category_count = Category.query.count() if db_mode else 0
    tag_count = Tag.query.count() if db_mode else 0

    recent_logs = MigrationLog.query.order_by(MigrationLog.processed_at.desc()).limit(50).all()

    return render_template('admin/migration.html',
                         file_counts=file_counts,
                         db_mode=db_mode,
                         migration_completed=migration_completed,
                         story_count=story_count,
                         author_count=author_count,
                         category_count=category_count,
                         tag_count=tag_count,
                         recent_logs=recent_logs)

@admin.route('/migration/preflight', methods=['GET'])
def migration_preflight():
    """Pre-flight check before migration"""
    scanner = FileScanner()
    file_counts = scanner.get_file_count()

    db_story_count = Story.query.count()

    warnings = []
    if db_story_count > 0:
        warnings.append(f"Database already contains {db_story_count} stories. Migration will skip duplicates.")

    if file_counts['total'] == 0:
        warnings.append("No files found to migrate.")

    return jsonify({
        'success': True,
        'file_counts': file_counts,
        'db_story_count': db_story_count,
        'warnings': warnings,
        'ready': file_counts['total'] > 0
    })

@admin.route('/migration/start', methods=['POST'])
def start_migration():
    """Start migration process"""
    data = request.get_json() or {}
    dry_run = data.get('dry_run', False)

    session_id = str(uuid.uuid4())

    migrator = DatabaseMigrator()
    result = migrator.run_migration(dry_run=dry_run)

    active_migrations[session_id] = result

    return jsonify({
        'success': True,
        'session_id': session_id,
        'result': result.to_dict()
    })

@admin.route('/migration/status/<session_id>', methods=['GET'])
def migration_status(session_id):
    """Get migration status"""
    if session_id in active_migrations:
        result = active_migrations[session_id]
        return jsonify({
            'success': True,
            'result': result.to_dict()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Migration session not found'
        }), 404

@admin.route('/migration/enable-db-mode', methods=['POST'])
def enable_db_mode():
    """Enable database mode"""
    config = AppConfig.query.filter_by(key='db_mode_enabled').first()
    if config:
        config.value = 'true'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Database mode enabled'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Config not found'
        }), 500

@admin.route('/migration/disable-db-mode', methods=['POST'])
def disable_db_mode():
    """Disable database mode (rollback to file-based)"""
    config = AppConfig.query.filter_by(key='db_mode_enabled').first()
    if config:
        config.value = 'false'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Rolled back to file-based mode. Database data preserved.'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Config not found'
        }), 500

@admin.route('/migration/clear-database', methods=['POST'])
def clear_database():
    """Clear all migrated data (destructive)"""
    try:
        db.session.execute(db.text('DELETE FROM story_tags'))
        db.session.execute(db.text('DELETE FROM story_formats'))

        try:
            db.session.execute(db.text('DELETE FROM reading_progress'))
        except:
            pass


        Story.query.delete()
        Author.query.delete()
        Category.query.delete()
        Tag.query.delete()
        MigrationLog.query.delete()

        try:
            db.session.execute(db.text("DELETE FROM sqlite_sequence WHERE name IN ('stories', 'authors', 'categories', 'tags', 'story_formats')"))
        except:
            pass

        migration_config = AppConfig.query.filter_by(key='migration_completed').first()
        if migration_config:
            migration_config.value = 'false'

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Database cleared successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/migration/logs', methods=['GET'])
def migration_logs():
    """Get migration logs"""
    session_id = request.args.get('session_id')

    query = MigrationLog.query
    if session_id:
        query = query.filter_by(migration_session_id=session_id)

    logs = query.order_by(MigrationLog.processed_at.desc()).limit(100).all()

    return jsonify({
        'success': True,
        'logs': [log.to_dict() for log in logs]
    })

@admin.route('/sync')
def sync_page():
    """Render database sync page"""
    sync_checker = SyncChecker()
    sync_status = sync_checker.check_sync()
    
    scanner = FileScanner()
    file_counts = scanner.get_file_count()
    
    story_count = Story.query.count()
    
    return render_template('admin/sync.html',
                         sync_status=sync_status,
                         file_counts=file_counts,
                         story_count=story_count)

@admin.route('/sync/check', methods=['GET'])
def check_sync():
    """Check sync status"""
    sync_checker = SyncChecker()
    sync_status = sync_checker.check_sync()
    
    return jsonify({
        'success': True,
        'in_sync': sync_status['in_sync'],
        'orphaned_db_count': sync_status['orphaned_db_count'],
        'orphaned_files_count': sync_status['orphaned_files_count']
    })

@admin.route('/sync/clean-orphaned', methods=['POST'])
def clean_orphaned_records():
    """Remove database records for files that no longer exist"""
    try:
        sync_checker = SyncChecker()
        count = sync_checker.clean_orphaned_records()
        
        return jsonify({
            'success': True,
            'message': f'Removed {count} orphaned database records',
            'records_cleaned': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/sync/add-orphaned', methods=['POST'])
def add_orphaned_files():
    """Add untracked files to database"""
    try:
        sync_checker = SyncChecker()
        count = sync_checker.add_orphaned_files()
        
        return jsonify({
            'success': True,
            'message': f'Added {count} files to database',
            'files_added': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/sync/full', methods=['POST'])
def full_sync():
    """Perform full sync: clean orphaned records and add orphaned files"""
    try:
        sync_checker = SyncChecker()
        result = sync_checker.full_sync()
        
        return jsonify({
            'success': True,
            'message': f"Cleaned {result['records_cleaned']} orphaned records, added {result['files_added']} files",
            'records_cleaned': result['records_cleaned'],
            'files_added': result['files_added']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/sync/fix-formats', methods=['POST'])
def fix_missing_formats():
    """Scan existing stories and add missing format records"""
    try:
        from app.utils import get_epub_directory, get_html_directory
        import os
        import json as json_module
        
        stories = Story.query.all()
        fixed_count = 0
        
        for story in stories:
            existing_formats = {fmt.format_type for fmt in story.formats}
            
            epub_path = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
            if os.path.exists(epub_path) and 'epub' not in existing_formats:
                story_format = StoryFormat(
                    story_id=story.id,
                    format_type='epub',
                    file_path=epub_path,
                    file_size=os.path.getsize(epub_path)
                )
                db.session.add(story_format)
                fixed_count += 1
            
            json_path = os.path.join(get_html_directory(), f"{story.filename_base}.json")
            if os.path.exists(json_path) and 'json' not in existing_formats:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json_module.load(f)
                
                story_format = StoryFormat(
                    story_id=story.id,
                    format_type='json',
                    file_path=json_path,
                    file_size=os.path.getsize(json_path),
                    json_data=json_module.dumps(json_data)
                )
                db.session.add(story_format)
                fixed_count += 1
        
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Added {fixed_count} missing format records',
            'fixed_count': fixed_count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/trigger-update-check', methods=['POST'])
def trigger_update_check():
    """Manually trigger story update check (for testing)."""
    try:
        from app.services.story_update_checker import check_all_stories_for_updates
        from flask import current_app

        thread = threading.Thread(
            target=check_all_stories_for_updates,
            args=(current_app._get_current_object(),)
        )
        thread.start()

        return jsonify({
            "success": True,
            "message": "Update check triggered in background"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@admin.route('/backfill-series-urls', methods=['POST'])
def backfill_series_urls():
    """Trigger series URL backfill for existing stories."""
    try:
        from app.services.series_backfill_service import SeriesBackfillService
        from flask import current_app
        from app.services.logger import log_action

        def run_backfill(app):
            with app.app_context():
                service = SeriesBackfillService()
                results = service.backfill_all_stories()
                log_action(f"Backfill results: {results}")

        app = current_app._get_current_object()
        thread = threading.Thread(target=run_backfill, args=(app,))
        thread.start()

        return jsonify({
            "success": True,
            "message": "Series backfill started in background"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
