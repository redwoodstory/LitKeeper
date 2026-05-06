import click
from flask import current_app
from flask.cli import AppGroup

sync_cli = AppGroup('sync', help='Database/file sync operations.')
migration_cli = AppGroup('migration', help='Database migration operations.')
backfill_cli = AppGroup('backfill', help='Data backfill operations.')
redownload_cli = AppGroup('redownload', help='Re-download story content from source.')


def _get_sync_checker():
    from app.services.migration.sync_checker import SyncChecker
    return SyncChecker()


@sync_cli.command('check')
def sync_check():
    """Check sync status between database and story files."""
    checker = _get_sync_checker()
    status = checker.check_sync()
    if status['in_sync'] and status.get('broken_format_paths_count', 0) == 0:
        click.echo('Database and files are in sync.')
    else:
        if not status['in_sync']:
            click.echo(f"Out of sync: {status['orphaned_db_count']} orphaned DB records, "
                       f"{status['orphaned_files_count']} untracked files.")
        broken = status.get('broken_format_paths_count', 0)
        if broken:
            click.echo(f"  {broken} format record(s) have stale paths "
                       f"(run 'flask sync fix-paths' to repair).")


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
    """Add missing StoryFormat records for existing EPUB/JSON files (canonical path first, legacy fallback)."""
    import os
    import json as json_module
    from app.utils import get_epub_directory, get_html_directory, story_epub_path, story_json_path
    from app.models import Story, StoryFormat
    from app.models.base import db

    stories = Story.query.all()
    fixed_count = 0

    for story in stories:
        existing_formats = {fmt.format_type for fmt in story.formats}

        # EPUB
        canonical_epub = story_epub_path(story.id, story.filename_base)
        legacy_epub = os.path.join(get_epub_directory(), f"{story.filename_base}.epub")
        if 'epub' not in existing_formats:
            if os.path.exists(canonical_epub):
                use_epub = canonical_epub
            elif os.path.exists(legacy_epub):
                os.rename(legacy_epub, canonical_epub)
                use_epub = canonical_epub
            else:
                use_epub = None
            if use_epub:
                db.session.add(StoryFormat(
                    story_id=story.id,
                    format_type='epub',
                    file_path=use_epub,
                    file_size=os.path.getsize(use_epub)
                ))
                fixed_count += 1

        # JSON
        canonical_json = story_json_path(story.id, story.filename_base)
        legacy_json = os.path.join(get_html_directory(), f"{story.filename_base}.json")
        if 'json' not in existing_formats:
            if os.path.exists(canonical_json):
                use_json = canonical_json
            elif os.path.exists(legacy_json):
                os.rename(legacy_json, canonical_json)
                use_json = canonical_json
            else:
                use_json = None
            if use_json:
                with open(use_json, 'r', encoding='utf-8') as f:
                    json_data = json_module.load(f)
                db.session.add(StoryFormat(
                    story_id=story.id,
                    format_type='json',
                    file_path=use_json,
                    file_size=os.path.getsize(use_json),
                    json_data=json_module.dumps(json_data)
                ))
                fixed_count += 1

    db.session.commit()
    click.echo(f'Added {fixed_count} missing format records.')


@sync_cli.command('audit-paths')
def sync_audit_paths():
    """Report StoryFormat records where file_path doesn't exist on disk."""
    import os
    from app.models import StoryFormat
    from app.utils import story_epub_path, story_json_path

    fmt_map = {'epub': story_epub_path, 'json': story_json_path}
    broken_canonical = []
    broken_missing = []

    for fmt in StoryFormat.query.filter(StoryFormat.format_type.in_(['epub', 'json'])).all():
        if os.path.exists(fmt.file_path):
            continue
        story = fmt.story
        if story and fmt.format_type in fmt_map:
            canonical = fmt_map[fmt.format_type](story.id, story.filename_base)
            if os.path.exists(canonical):
                broken_canonical.append((fmt.story_id, fmt.format_type, fmt.file_path, canonical))
            else:
                broken_missing.append((fmt.story_id, fmt.format_type, fmt.file_path))

    if broken_canonical:
        click.echo(f"\n{len(broken_canonical)} record(s) with wrong path but canonical file exists (run fix-paths):")
        for story_id, fmt_type, bad_path, good_path in broken_canonical:
            click.echo(f"  story_id={story_id} [{fmt_type}]")
            click.echo(f"    stored:    {bad_path}")
            click.echo(f"    canonical: {good_path}")

    if broken_missing:
        click.echo(f"\n{len(broken_missing)} record(s) with missing path AND no canonical file:")
        for story_id, fmt_type, bad_path in broken_missing:
            click.echo(f"  story_id={story_id} [{fmt_type}] path={bad_path}")

    if not broken_canonical and not broken_missing:
        click.echo("All StoryFormat file_path values resolve to existing files.")


@sync_cli.command('fix-paths')
def sync_fix_paths():
    """Update StoryFormat.file_path records that point to non-existent files."""
    import os
    from app.models import StoryFormat
    from app.models.base import db
    from app.utils import story_epub_path, story_json_path

    fmt_map = {'epub': story_epub_path, 'json': story_json_path}
    fixed = 0
    missing = 0

    for fmt in StoryFormat.query.filter(StoryFormat.format_type.in_(['epub', 'json'])).all():
        if os.path.exists(fmt.file_path):
            continue
        story = fmt.story
        if story and fmt.format_type in fmt_map:
            canonical = fmt_map[fmt.format_type](story.id, story.filename_base)
            if os.path.exists(canonical):
                fmt.file_path = canonical
                fmt.file_size = os.path.getsize(canonical)
                fixed += 1
                click.echo(f"Fixed story_id={story.id} [{fmt.format_type}] -> {canonical}")
            else:
                missing += 1
                click.echo(f"No file found for story_id={story.id} [{fmt.format_type}] (stored: {fmt.file_path})")

    if fixed:
        db.session.commit()
    click.echo(f"\nFixed: {fixed}, No file found: {missing}.")


@sync_cli.command('adopt-legacy-json')
def sync_adopt_legacy_json():
    """Rename bare JSON files (no ID prefix) to {id}_{name}.json and link them to the DB."""
    import os
    import shutil
    import json as json_module
    from app.utils import get_html_directory
    from app.models import Story, StoryFormat
    from app.models.base import db

    html_dir = get_html_directory()
    stories = Story.query.all()
    renamed = 0
    linked = 0
    skipped = 0

    for story in stories:
        legacy_path = os.path.join(html_dir, f"{story.filename_base}.json")
        id_path = os.path.join(html_dir, f"{story.id}_{story.filename_base}.json")

        if not os.path.exists(legacy_path):
            skipped += 1
            continue

        if not os.path.exists(id_path):
            shutil.move(legacy_path, id_path)
            renamed += 1
        else:
            os.remove(legacy_path)

        existing = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
        with open(id_path, 'r', encoding='utf-8') as f:
            json_data = json_module.load(f)

        if existing:
            existing.file_path = id_path
            existing.file_size = os.path.getsize(id_path)
            existing.json_data = json_module.dumps(json_data)
        else:
            db.session.add(StoryFormat(
                story_id=story.id,
                format_type='json',
                file_path=id_path,
                file_size=os.path.getsize(id_path),
                json_data=json_module.dumps(json_data)
            ))
            linked += 1

    db.session.commit()
    click.echo(f'Renamed: {renamed}, Linked: {linked}, Skipped (no legacy file): {skipped}.')


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

            json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
            if json_fmt and json_fmt.file_path and os.path.exists(json_fmt.file_path):
                try:
                    with open(json_fmt.file_path, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                    if data.get('description') != description:
                        data['description'] = description
                        with open(json_fmt.file_path, 'w', encoding='utf-8') as f:
                            _json.dump(data, f, ensure_ascii=False, indent=2)
                        json_updated += 1
                except Exception as e:
                    click.echo(f'\nFailed to patch JSON for {story.filename_base}: {e}', err=True)
                    skipped += 1

            if json_fmt and json_fmt.json_data:
                try:
                    data = _json.loads(json_fmt.json_data)
                    if data.get('description') != description:
                        data['description'] = description
                        json_fmt.json_data = _json.dumps(data, ensure_ascii=False)
                except Exception:
                    pass

            epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
            epub_path = epub_fmt.file_path if epub_fmt else None
            if epub_path and os.path.exists(epub_path):
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
            epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
            epub_path = epub_fmt.file_path if epub_fmt else None
            if not epub_path or not os.path.exists(epub_path):
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


@redownload_cli.command('all')
@click.option('--dry-run', is_flag=True, default=False, help='Preview what would be enqueued without adding to queue.')
def redownload_all(dry_run: bool):
    """Enqueue all stories with a Literotica URL for re-download."""
    from app.models import Story, DownloadQueueItem
    from app.models.base import db

    stories = Story.query.filter(Story.literotica_url.isnot(None)).order_by(Story.title.asc()).all()
    if not stories:
        click.echo('No stories with a Literotica URL found.')
        return

    click.echo(f'Found {len(stories)} stories to re-download.')

    if dry_run:
        for story in stories:
            click.echo(f'  [DRY RUN] Would enqueue: {story.title} — {story.literotica_url}')
        click.echo('[DRY RUN] No items added to queue.')
        return

    if not click.confirm(f'Enqueue all {len(stories)} stories for re-download?'):
        click.echo('Aborted.')
        return

    enqueued = 0
    skipped = 0
    for story in stories:
        already_pending = DownloadQueueItem.query.filter_by(
            url=story.literotica_url, status='pending'
        ).first()
        if already_pending:
            click.echo(f'  Skipping (already pending): {story.title}')
            skipped += 1
            continue

        item = DownloadQueueItem(url=story.literotica_url, status='pending', job_type='redownload')
        item.set_formats(['epub', 'html'])
        db.session.add(item)
        enqueued += 1

    db.session.commit()
    click.echo(f'Done. Enqueued: {enqueued}, Skipped (already pending): {skipped}.')
    click.echo('The download queue worker will process them at up to 5 per minute.')


@redownload_cli.command('cancel')
def redownload_cancel():
    """Remove all pending download queue jobs (in-progress download completes first)."""
    from app.models import DownloadQueueItem
    from app.models.base import db

    pending = DownloadQueueItem.query.filter_by(status='pending').all()
    if not pending:
        click.echo('No pending jobs in the queue.')
        return

    count = len(pending)
    if not click.confirm(f'Delete {count} pending job(s) from the queue?'):
        click.echo('Aborted.')
        return

    for item in pending:
        db.session.delete(item)
    db.session.commit()
    click.echo(f'Removed {count} pending job(s). Any in-progress download will finish normally.')


def register_commands(app):
    app.cli.add_command(sync_cli)
    app.cli.add_command(migration_cli)
    app.cli.add_command(backfill_cli)
    app.cli.add_command(redownload_cli)

    @app.cli.command('update-check')
    def update_check():
        """Trigger a story update check (runs synchronously)."""
        from app.services.story_update_checker import check_all_stories_for_updates
        click.echo('Running update check...')
        check_all_stories_for_updates(app)
        click.echo('Done.')

