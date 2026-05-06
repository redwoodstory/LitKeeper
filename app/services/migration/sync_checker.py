from __future__ import annotations
import os
from typing import Dict, List
from app.utils import get_epub_directory, get_html_directory, story_epub_path, story_json_path
from app.models import Story, StoryFormat
from .file_scanner import FileScanner

_CANONICAL_FN = {'epub': story_epub_path, 'json': story_json_path}


class SyncChecker:
    """Checks filesystem and database sync status"""

    def __init__(self):
        self.scanner = FileScanner()

    def check_sync(self) -> Dict:
        """
        Compare filesystem to database and detect discrepancies.

        Returns:
            {
                'in_sync': bool,
                'orphaned_db_records': [Story objects in DB but not on disk (no fixable path)],
                'broken_format_paths': [Story objects whose format paths are stale but canonical exists],
                'orphaned_files': [filename_bases on disk but not in DB],
                'orphaned_db_count': int,
                'broken_format_paths_count': int,
                'orphaned_files_count': int,
                'duplicate_files_count': int
            }
        """
        from app.services.migration.metadata_extractor import MetadataExtractor
        from app.services.migration.deduplicator import Deduplicator

        orphaned_db_records = []
        broken_format_paths = []
        orphaned_files = []
        duplicate_files = []

        file_groups = self.scanner.scan_story_files()
        filesystem_bases = {group['filename_base'] for group in file_groups}

        db_stories = Story.query.all()

        for story in db_stories:
            story_exists = any(os.path.exists(f.file_path) for f in story.formats)
            if story_exists:
                continue

            # Stored paths are all missing — check whether canonical paths exist (fixable)
            has_fixable_path = any(
                os.path.exists(_CANONICAL_FN[f.format_type](story.id, story.filename_base))
                for f in story.formats
                if f.format_type in _CANONICAL_FN
            )
            if has_fixable_path:
                broken_format_paths.append(story)
            else:
                orphaned_db_records.append(story)

        db_filename_bases = {story.filename_base for story in db_stories}

        extractor = MetadataExtractor()
        deduplicator = Deduplicator()

        for group in file_groups:
            base = group['filename_base']
            # If the file's embedded story_id matches a DB story, it's already accounted for
            embedded_id = group.get('story_id')
            if embedded_id is not None:
                from app.models.base import db
                if db.session.get(Story, embedded_id):
                    continue

            if base not in db_filename_bases:
                try:
                    metadata = extractor.extract_metadata(group)
                    duplicate = deduplicator.check_duplicate(metadata, base)

                    if duplicate:
                        duplicate_files.append(base)
                    else:
                        orphaned_files.append(base)
                except Exception:
                    orphaned_files.append(base)

        return {
            'in_sync': len(orphaned_db_records) == 0 and len(orphaned_files) == 0,
            'orphaned_db_records': orphaned_db_records,
            'broken_format_paths': broken_format_paths,
            'orphaned_files': orphaned_files,
            'duplicate_files': duplicate_files,
            'orphaned_db_count': len(orphaned_db_records),
            'broken_format_paths_count': len(broken_format_paths),
            'orphaned_files_count': len(orphaned_files),
            'duplicate_files_count': len(duplicate_files),
        }

    def clean_orphaned_records(self) -> int:
        """
        Remove database records for stories that no longer exist on disk.
        Stories with stale-but-fixable paths are NOT deleted (see broken_format_paths).

        Returns:
            Number of records deleted
        """
        from app.models.base import db

        sync_status = self.check_sync()
        orphaned_records = sync_status['orphaned_db_records']

        count = 0
        for story in orphaned_records:
            db.session.delete(story)
            count += 1

        if count > 0:
            db.session.commit()

        return count

    def add_orphaned_files(self) -> int:
        """
        Scan filesystem and add untracked files to database.

        Returns:
            Number of files added to database
        """
        from app.models.base import db
        from app.models import Story, Author, Category, Tag, StoryFormat
        from app.services.migration.metadata_extractor import MetadataExtractor
        from app.services.migration.deduplicator import Deduplicator
        from datetime import datetime

        sync_status = self.check_sync()
        orphaned_files = sync_status['orphaned_files']

        if not orphaned_files:
            return 0

        file_groups = self.scanner.scan_story_files()
        extractor = MetadataExtractor()
        deduplicator = Deduplicator()

        files_to_migrate = [
            group for group in file_groups
            if group['filename_base'] in orphaned_files
        ]

        count = 0
        for file_group in files_to_migrate:
            try:
                metadata = extractor.extract_metadata(file_group)

                duplicate = deduplicator.check_duplicate(metadata, file_group['filename_base'])
                if duplicate:
                    continue

                author = Author.query.filter_by(name=metadata['author']).first()
                if not author:
                    author = Author(
                        name=metadata['author'],
                        literotica_url=metadata.get('author_url')
                    )
                    db.session.add(author)
                    db.session.flush()

                category = None
                if metadata.get('category'):
                    category = Category.query.filter_by(name=metadata['category']).first()
                    if not category:
                        category = Category(
                            name=metadata['category'],
                            slug=Category.create_slug(metadata['category'])
                        )
                        db.session.add(category)
                        db.session.flush()

                story = Story(
                    title=metadata['title'],
                    author_id=author.id,
                    category_id=category.id if category else None,
                    literotica_url=metadata.get('source_url'),
                    literotica_page_count=metadata.get('page_count'),
                    word_count=metadata.get('word_count'),
                    chapter_count=1,
                    filename_base=file_group['filename_base'],
                    imported_at=datetime.utcnow(),
                    metadata_refresh_status='complete' if metadata.get('source_url') else 'never'
                )
                db.session.add(story)
                db.session.flush()

                if metadata.get('tags'):
                    tag_objects = []
                    seen_slugs = set()
                    for tag_name in metadata['tags']:
                        tag_slug = Tag.create_slug(tag_name)
                        if tag_slug in seen_slugs:
                            continue
                        seen_slugs.add(tag_slug)

                        tag = Tag.query.filter_by(slug=tag_slug).first()
                        if not tag:
                            tag = Tag(name=tag_name, slug=tag_slug)
                            db.session.add(tag)
                            db.session.flush()
                        tag_objects.append(tag)
                    story.tags = tag_objects

                for format_info in file_group['formats']:
                    import json as json_module
                    json_data_str = None
                    if format_info.get('json_data'):
                        json_data_str = json_module.dumps(format_info['json_data'])

                    story_format = StoryFormat(
                        story_id=story.id,
                        format_type=format_info['type'],
                        file_path=format_info['path'],
                        file_size=format_info.get('size'),
                        json_data=json_data_str
                    )
                    db.session.add(story_format)

                db.session.commit()
                count += 1

            except Exception:
                db.session.rollback()
                continue

        return count

    def full_sync(self) -> Dict:
        """
        Perform full sync: clean orphaned records and add orphaned files.

        Returns:
            {
                'records_cleaned': int,
                'files_added': int
            }
        """
        records_cleaned = self.clean_orphaned_records()
        files_added = self.add_orphaned_files()

        return {
            'records_cleaned': records_cleaned,
            'files_added': files_added
        }
