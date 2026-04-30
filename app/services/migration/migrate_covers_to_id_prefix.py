"""
One-time migration: rename cover files from "{filename_base}.jpg" to
"{story.id}_{filename_base}.jpg" and update Story.cover_filename records.

Run via Flask CLI (after adding a command) or call migrate_covers_to_id_prefix()
directly from a shell or admin endpoint.
"""
from __future__ import annotations
import os
from app.models import Story
from app.models.base import db
from app.utils import get_cover_directory
from app.services.logger import log_action, log_error


def migrate_covers_to_id_prefix() -> dict:
    """
    For every Story record, rename cover files from the legacy "{filename_base}.jpg"
    naming to "{story.id}_{filename_base}.jpg" and update the cover_filename column.

    Safe to run multiple times — skips files already using the new naming convention.
    Returns a summary dict with counts of renamed, skipped, and failed files.
    """
    cover_dir = get_cover_directory()

    renamed = 0
    skipped = 0
    failed = 0

    stories = Story.query.all()
    for story in stories:
        old_cover = os.path.join(cover_dir, f"{story.filename_base}.jpg")
        new_cover = os.path.join(cover_dir, f"{story.id}_{story.filename_base}.jpg")

        if os.path.exists(new_cover):
            # Already migrated; ensure DB record is correct.
            if story.cover_filename != f"{story.id}_{story.filename_base}.jpg":
                story.cover_filename = f"{story.id}_{story.filename_base}.jpg"
            skipped += 1
            continue

        if os.path.exists(old_cover):
            try:
                os.rename(old_cover, new_cover)
                story.cover_filename = f"{story.id}_{story.filename_base}.jpg"
                log_action(
                    f"[migrate-covers] Renamed cover: {story.filename_base}.jpg → "
                    f"{story.id}_{story.filename_base}.jpg (story {story.id})"
                )
                renamed += 1
            except Exception as e:
                log_error(f"[migrate-covers] Failed to rename cover for story {story.id}: {e}")
                failed += 1
        else:
            # Cover missing on disk; just update the DB record to the new convention
            story.cover_filename = f"{story.id}_{story.filename_base}.jpg"
            skipped += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log_error(f"[migrate-covers] DB commit failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'renamed': renamed,
            'skipped': skipped,
            'failed': failed
        }

    summary = (
        f"Cover migration complete: {renamed} renamed, {skipped} already migrated / missing, "
        f"{failed} failed."
    )
    log_action(f"[migrate-covers] {summary}")
    return {
        'success': True,
        'message': summary,
        'renamed': renamed,
        'skipped': skipped,
        'failed': failed
    }
