from __future__ import annotations
import os
import uuid
from datetime import datetime
from typing import Optional, Dict
from flask import current_app
from app.models.base import db
from app.models import Story, Author, Category, Tag, StoryFormat, MigrationLog, AppConfig
from .file_scanner import FileScanner
from .metadata_extractor import MetadataExtractor
from .deduplicator import Deduplicator

class MigrationResult:
    """Tracks the result of a migration session"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.total_files = 0
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.duplicates = 0
        self.errors = []
        self.started_at = datetime.utcnow()
        self.completed_at = None

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'total_files': self.total_files,
            'processed': self.processed,
            'successful': self.successful,
            'failed': self.failed,
            'skipped': self.skipped,
            'duplicates': self.duplicates,
            'errors': self.errors[:50],
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': (self.completed_at - self.started_at).total_seconds() if self.completed_at else None,
            'completed': self.completed_at is not None
        }

class DatabaseMigrator:
    """Main orchestrator for migrating files to database"""

    def __init__(self):
        self.scanner = FileScanner()
        self.extractor = MetadataExtractor()
        self.deduplicator = Deduplicator()
        self.result = MigrationResult()
        self.dry_run_stories = []

    def run_migration(self, dry_run: bool = False) -> MigrationResult:
        """
        Execute the full migration from files to database.

        Args:
            dry_run: If True, simulate migration without writing to DB
        """
        try:
            story_files = self.scanner.scan_story_files()
            self.result.total_files = len(story_files)

            for file_group in story_files:
                self._process_story_file(file_group, dry_run)
                self.result.processed += 1

            if not dry_run:
                self._finalize_migration()

            self.result.completed_at = datetime.utcnow()
            return self.result

        except Exception as e:
            self.result.errors.append(f"Fatal error: {str(e)}")
            self.result.completed_at = datetime.utcnow()
            raise

    def _process_story_file(self, file_group: dict, dry_run: bool):
        """Process a single story's files (EPUB + JSON)"""
        try:
            metadata = self.extractor.extract_metadata(file_group)

            duplicate = self.deduplicator.check_duplicate(metadata, file_group['filename_base'])
            if duplicate:
                self.result.duplicates += 1
                self._log_migration(file_group, 'duplicate', error=f"Duplicate of story ID {duplicate.id}")
                return

            if dry_run:
                for virtual_story in self.dry_run_stories:
                    if virtual_story['filename_base'] == file_group['filename_base']:
                        self.result.duplicates += 1
                        return

                    if virtual_story.get('literotica_url') and metadata.get('source_url'):
                        if virtual_story['literotica_url'] == metadata['source_url']:
                            self.result.duplicates += 1
                            return

                    if virtual_story['title'].lower() == metadata['title'].lower() and \
                       virtual_story['author'].lower() == metadata['author'].lower():
                        self.result.duplicates += 1
                        return

                self.dry_run_stories.append({
                    'filename_base': file_group['filename_base'],
                    'title': metadata['title'],
                    'author': metadata['author'],
                    'literotica_url': metadata.get('source_url')
                })
                self.result.successful += 1
                return

            story = self._create_story_record(metadata, file_group)
            self.result.successful += 1
            self._log_migration(file_group, 'success', story_id=story.id)

        except Exception as e:
            db.session.rollback()
            self.result.failed += 1
            self._log_migration(file_group, 'failed', error=str(e))
            self.result.errors.append(f"{file_group.get('filename_base')}: {str(e)}")

    def _create_story_record(self, metadata: dict, file_group: dict) -> Story:
        """Create Story and related records in database"""
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
            from app.models.category import Category as CategoryModel
            category = CategoryModel.query.filter_by(name=metadata['category']).first()
            if not category:
                category = CategoryModel(
                    name=metadata['category'],
                    slug=CategoryModel.create_slug(metadata['category'])
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
            chapter_count=metadata.get('chapter_count', 1),
            filename_base=file_group['filename_base'],
            cover_filename=metadata.get('cover'),
            imported_at=datetime.utcnow(),
            metadata_refresh_status='complete' if metadata.get('source_url') else 'never'
        )
        db.session.add(story)
        db.session.flush()

        unique_tags = list(dict.fromkeys(metadata.get('tags', [])))

        tag_objects = []
        seen_slugs = set()
        for tag_name in unique_tags:
            from app.models.tag import Tag as TagModel
            tag_slug = TagModel.create_slug(tag_name)

            if tag_slug in seen_slugs:
                continue
            seen_slugs.add(tag_slug)

            tag = TagModel.query.filter_by(slug=tag_slug).first()
            if not tag:
                tag = TagModel(
                    name=tag_name,
                    slug=tag_slug
                )
                db.session.add(tag)
                db.session.flush()
            tag_objects.append(tag)

        story.tags = tag_objects

        seen_formats = set()
        for format_info in file_group.get('formats', []):
            format_type = format_info['type']

            if format_type in seen_formats:
                continue
            seen_formats.add(format_type)

            existing_format = StoryFormat.query.filter_by(
                story_id=story.id,
                format_type=format_type
            ).first()

            if existing_format:
                continue

            json_data = None
            if format_type == 'json' and format_info.get('json_data'):
                import json
                json_data = json.dumps(format_info['json_data'])

            story_format = StoryFormat(
                story_id=story.id,
                format_type=format_type,
                file_path=format_info['path'],
                file_size=format_info.get('size'),
                json_data=json_data
            )
            db.session.add(story_format)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to commit story '{metadata.get('title')}': {str(e)}")

        return story

    def _log_migration(self, file_group: dict, status: str, story_id: Optional[int] = None, error: Optional[str] = None):
        """Log migration result for a file"""
        log = MigrationLog(
            migration_session_id=self.result.session_id,
            file_path=file_group.get('primary_file'),
            file_type=file_group.get('primary_type'),
            status=status,
            story_id=story_id,
            error_message=error
        )
        db.session.add(log)
        try:
            db.session.commit()
        except:
            db.session.rollback()

    def _finalize_migration(self):
        """Post-migration tasks"""
        config = AppConfig.query.filter_by(key='migration_completed').first()
        if config:
            config.value = 'true'
            config.updated_at = datetime.utcnow()
            db.session.commit()
