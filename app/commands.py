import click
from flask import current_app
from flask.cli import AppGroup

sync_cli = AppGroup('sync', help='Database/file sync operations.')
migration_cli = AppGroup('migration', help='Database migration operations.')
backfill_cli = AppGroup('backfill', help='Data backfill operations.')


def _get_sync_checker():
    from app.services.migration.sync_checker import SyncChecker
    return SyncChecker()


@sync_cli.command('check')
def sync_check():
    """Check sync status between database and story files."""
    checker = _get_sync_checker()
    status = checker.check_sync()
    if status['in_sync']:
        click.echo('Database and files are in sync.')
    else:
        click.echo(f"Out of sync: {status['orphaned_db_count']} orphaned DB records, "
                   f"{status['orphaned_files_count']} untracked files.")


@sync_cli.command('clean')
def sync_clean():
    """Remove database records for story files that no longer exist."""
    checker = _get_sync_checker()
    count = checker.clean_orphaned_records()
    click.echo(f'Removed {count} orphaned database records.')


@sync_cli.command('add')
def sync_add():
    """Add untracked story files to the database."""
    checker = _get_sync_checker()
    count = checker.add_orphaned_files()
    click.echo(f'Added {count} files to the database.')


@sync_cli.command('full')
def sync_full():
    """Full sync: remove orphaned records and add untracked files."""
    checker = _get_sync_checker()
    result = checker.full_sync()
    click.echo(f"Cleaned {result['records_cleaned']} orphaned records, "
               f"added {result['files_added']} files.")


@sync_cli.command('fix-formats')
def sync_fix_formats():
    """Scan stories and add missing StoryFormat records for existing EPUB/JSON files."""
    import os
    import json as json_module
    from app.utils import get_epub_directory, get_html_directory
    from app.models import Story, StoryFormat
    from app.models.base import db

    stories = Story.query.all()
    fixed_count = 0

    for story in stories:
        existing_formats = {fmt.format_type for fmt in story.formats}

        epub_path = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
        if os.path.exists(epub_path) and 'epub' not in existing_formats:
            db.session.add(StoryFormat(
                story_id=story.id,
                format_type='epub',
                file_path=epub_path,
                file_size=os.path.getsize(epub_path)
            ))
            fixed_count += 1

        json_path = os.path.join(get_html_directory(), f"{story.filename_base}.json")
        if os.path.exists(json_path) and 'json' not in existing_formats:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json_module.load(f)
            db.session.add(StoryFormat(
                story_id=story.id,
                format_type='json',
                file_path=json_path,
                file_size=os.path.getsize(json_path),
                json_data=json_module.dumps(json_data)
            ))
            fixed_count += 1

    db.session.commit()
    click.echo(f'Added {fixed_count} missing format records.')


@sync_cli.command('inject-descriptions')
def sync_inject_descriptions():
    """Patch descriptions from DB into existing JSON and EPUB files without re-scraping."""
    import os
    import json as _json
    import zipfile
    import shutil
    import tempfile
    import html as _html
    from app.utils import get_epub_directory, get_html_directory
    from app.services.epub_generator import format_metadata_content
    from app.models import Story, StoryFormat
    from app.models.base import db

    stories = Story.query.filter(Story.description.isnot(None), Story.description != '').all()
    json_updated = 0
    epub_updated = 0
    skipped = 0

    with click.progressbar(stories, label='Injecting descriptions') as bar:
        for story in bar:
            category = story.category.name if story.category else None
            tags = [t.name for t in story.tags]
            description = story.description

            json_path = os.path.join(get_html_directory(), f"{story.filename_base}.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                    if data.get('description') != description:
                        data['description'] = description
                        with open(json_path, 'w', encoding='utf-8') as f:
                            _json.dump(data, f, ensure_ascii=False, indent=2)
                        json_updated += 1
                except Exception as e:
                    click.echo(f'\nFailed to patch JSON for {story.filename_base}: {e}', err=True)
                    skipped += 1

            json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
            if json_fmt and json_fmt.json_data:
                try:
                    data = _json.loads(json_fmt.json_data)
                    if data.get('description') != description:
                        data['description'] = description
                        json_fmt.json_data = _json.dumps(data, ensure_ascii=False)
                except Exception:
                    pass

            epub_path = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
            if os.path.exists(epub_path):
                try:
                    with zipfile.ZipFile(epub_path, 'r') as zin:
                        names = zin.namelist()
                        metadata_xhtml = next((n for n in names if n.endswith('metadata.xhtml')), None)
                        if metadata_xhtml:
                            new_content = format_metadata_content(
                                category=category,
                                tags=tags,
                                description=_html.escape(description)
                            )
                            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.epub')
                            os.close(tmp_fd)
                            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                                for item in zin.infolist():
                                    if item.filename == metadata_xhtml:
                                        zout.writestr(item, new_content)
                                    else:
                                        zout.writestr(item, zin.read(item.filename))
                            shutil.move(tmp_path, epub_path)

                            epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
                            if epub_fmt:
                                epub_fmt.file_size = os.path.getsize(epub_path)
                            epub_updated += 1
                        else:
                            skipped += 1
                except Exception as e:
                    click.echo(f'\nFailed to patch EPUB for {story.filename_base}: {e}', err=True)
                    skipped += 1

    db.session.commit()
    click.echo(f'Updated {json_updated} JSON files, {epub_updated} EPUB files ({skipped} skipped).')


@sync_cli.command('rebuild-epub-info')
def sync_rebuild_epub_info():
    """Force-rewrite Story Information pages in all EPUBs, inserting the page where missing."""
    import os
    import re
    import zipfile
    import shutil
    import tempfile
    import html as _html
    from app.utils import get_epub_directory
    from app.services.epub_generator import format_metadata_content
    from app.models import Story, StoryFormat
    from app.models.base import db

    stories = Story.query.all()
    updated = 0
    added = 0
    skipped = 0

    with click.progressbar(stories, label='Rebuilding Story Information pages') as bar:
        for story in bar:
            epub_path = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
            if not os.path.exists(epub_path):
                continue

            category = story.category.name if story.category else None
            tags = [t.name for t in story.tags]
            description = story.description

            if not (description or category or tags):
                continue

            new_content = format_metadata_content(
                category=category,
                tags=tags,
                description=_html.escape(description) if description else None
            )

            tmp_path = None
            try:
                with zipfile.ZipFile(epub_path, 'r') as zin:
                    names = zin.namelist()
                    metadata_xhtml = next((n for n in names if n.endswith('metadata.xhtml')), None)

                    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.epub')
                    os.close(tmp_fd)

                    if metadata_xhtml:
                        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                            for item in zin.infolist():
                                data = new_content.encode('utf-8') if item.filename == metadata_xhtml else zin.read(item.filename)
                                zout.writestr(item, data)
                        updated += 1
                    else:
                        # Find OPF via META-INF/container.xml
                        container_xml = zin.read('META-INF/container.xml').decode('utf-8')
                        opf_match = re.search(r'full-path="([^"]+\.opf)"', container_xml)
                        if not opf_match:
                            skipped += 1
                            os.unlink(tmp_path)
                            tmp_path = None
                            continue

                        opf_zip_path = opf_match.group(1)
                        opf_dir = opf_zip_path.rsplit('/', 1)[0] + '/' if '/' in opf_zip_path else ''
                        metadata_zip_path = opf_dir + 'metadata.xhtml'

                        opf = zin.read(opf_zip_path).decode('utf-8')

                        # Add item to manifest
                        opf = opf.replace(
                            '</manifest>',
                            '  <item id="metadata" href="metadata.xhtml" media-type="application/xhtml+xml"/>\n  </manifest>'
                        )

                        # Insert itemref after nav in spine
                        nav_inserted = re.sub(
                            r'(<itemref\s[^>]*idref=["\']nav["\'][^>]*/?>)',
                            r'\1\n    <itemref idref="metadata"/>',
                            opf, count=1
                        )
                        # Fallback: insert before first non-nav itemref if nav pattern didn't match
                        if nav_inserted == opf:
                            opf = re.sub(
                                r'(<itemref\b)',
                                '<itemref idref="metadata"/>\n    \\1',
                                opf, count=1
                            )
                        else:
                            opf = nav_inserted

                        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                            for item in zin.infolist():
                                data = opf.encode('utf-8') if item.filename == opf_zip_path else zin.read(item.filename)
                                zout.writestr(item, data)
                            zout.writestr(metadata_zip_path, new_content.encode('utf-8'))
                        added += 1

                shutil.move(tmp_path, epub_path)
                tmp_path = None

                epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
                if epub_fmt:
                    epub_fmt.file_size = os.path.getsize(epub_path)

            except Exception as e:
                click.echo(f'\nFailed for {story.filename_base}: {e}', err=True)
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                skipped += 1

    db.session.commit()
    click.echo(f'Done. Rewritten: {updated}, Added new page: {added}, Skipped: {skipped}.')


@migration_cli.command('run')
@click.option('--dry-run', is_flag=True, default=False, help='Preview changes without writing to DB.')
def migration_run(dry_run: bool):
    """Run the file-to-database migration."""
    from app.services.migration.migrator import DatabaseMigrator
    migrator = DatabaseMigrator()
    result = migrator.run_migration(dry_run=dry_run)
    d = result.to_dict()
    if dry_run:
        click.echo('[DRY RUN] No changes written.')
    click.echo(f"Migrated: {d.get('migrated', 0)}, Skipped: {d.get('skipped', 0)}, "
               f"Errors: {d.get('errors', 0)}")


@migration_cli.command('enable-db-mode')
def migration_enable_db_mode():
    """Enable database mode."""
    from app.models import AppConfig
    from app.models.base import db
    config = AppConfig.query.filter_by(key='db_mode_enabled').first()
    if not config:
        click.echo('Config key not found.', err=True)
        raise SystemExit(1)
    config.value = 'true'
    db.session.commit()
    click.echo('Database mode enabled.')


@migration_cli.command('disable-db-mode')
def migration_disable_db_mode():
    """Disable database mode (rollback to file-based). DB data is preserved."""
    from app.models import AppConfig
    from app.models.base import db
    config = AppConfig.query.filter_by(key='db_mode_enabled').first()
    if not config:
        click.echo('Config key not found.', err=True)
        raise SystemExit(1)
    config.value = 'false'
    db.session.commit()
    click.echo('Rolled back to file-based mode. Database data preserved.')


@migration_cli.command('clear')
@click.confirmation_option(prompt='This will delete all migrated story data. Are you sure?')
def migration_clear():
    """Clear all migrated data from the database (destructive)."""
    from app.models import Story, Author, Category, Tag, MigrationLog, AppConfig
    from app.models.base import db

    db.session.execute(db.text('DELETE FROM story_tags'))
    db.session.execute(db.text('DELETE FROM story_formats'))
    try:
        db.session.execute(db.text('DELETE FROM reading_progress'))
    except Exception:
        pass

    Story.query.delete()
    Author.query.delete()
    Category.query.delete()
    Tag.query.delete()
    MigrationLog.query.delete()

    try:
        db.session.execute(db.text(
            "DELETE FROM sqlite_sequence WHERE name IN "
            "('stories', 'authors', 'categories', 'tags', 'story_formats')"
        ))
    except Exception:
        pass

    migration_config = AppConfig.query.filter_by(key='migration_completed').first()
    if migration_config:
        migration_config.value = 'false'

    db.session.commit()
    click.echo('Database cleared.')


@migration_cli.command('logs')
@click.option('--limit', default=50, show_default=True, help='Number of log entries to show.')
def migration_logs(limit: int):
    """Show recent migration log entries."""
    from app.models import MigrationLog
    logs = MigrationLog.query.order_by(MigrationLog.processed_at.desc()).limit(limit).all()
    if not logs:
        click.echo('No migration logs found.')
        return
    for log in reversed(logs):
        d = log.to_dict()
        click.echo(f"[{d.get('processed_at', '')}] {d.get('status', '').upper():8s} {d.get('filename', '')} — {d.get('message', '')}")


@backfill_cli.command('descriptions')
@click.option('--rate', default=5, show_default=True, help='Max requests per minute.')
def backfill_descriptions(rate: int):
    """Backfill missing descriptions by re-fetching metadata from Literotica."""
    from app.models import Story
    from app.models.base import db
    from app.services.metadata_refresh.rate_limiter import RateLimiter
    from app.services.story_downloader import fetch_story_metadata
    from app.services.logger import log_action

    Story.query.filter(Story.literotica_url.isnot(None)).update(
        {Story.description: None}, synchronize_session=False
    )
    db.session.commit()

    stories = Story.query.filter(Story.literotica_url.isnot(None)).all()
    if not stories:
        click.echo('No stories with a Literotica URL found.')
        return

    rate_limiter = RateLimiter(max_requests=rate, time_window=60)
    updated = 0
    failed = 0

    with click.progressbar(stories, label='Backfilling descriptions') as bar:
        for story in bar:
            rate_limiter.wait_if_needed()
            try:
                metadata = fetch_story_metadata(story.literotica_url)
                description = metadata.get('description')
                log_action(f"[BACKFILL] '{story.title}' → {repr(description)}")
                if description:
                    story.description = description
                    db.session.commit()
                    updated += 1
                else:
                    failed += 1
            except Exception as e:
                log_action(f"[BACKFILL] '{story.title}' → ERROR: {e}")
                db.session.rollback()
                failed += 1

    click.echo(f'Done. Updated: {updated}, Failed: {failed}.')


@backfill_cli.command('series-urls')
def backfill_series_urls():
    """Backfill series URLs for existing stories."""
    from app.services.series_backfill_service import SeriesBackfillService
    from app.services.logger import log_action

    service = SeriesBackfillService()
    results = service.backfill_all_stories()
    log_action(f'Series backfill results: {results}')
    click.echo(f'Done. Results: {results}')


def register_commands(app):
    app.cli.add_command(sync_cli)
    app.cli.add_command(migration_cli)
    app.cli.add_command(backfill_cli)

    @app.cli.command('update-check')
    def update_check():
        """Trigger a story update check (runs synchronously)."""
        from app.services.story_update_checker import check_all_stories_for_updates
        click.echo('Running update check...')
        check_all_stories_for_updates(app)
        click.echo('Done.')
