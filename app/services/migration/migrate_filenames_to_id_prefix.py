"""
One-time migration: rename story files from "{filename_base}.epub/.json" to
"{story.id}_{filename_base}.epub/.json" and update StoryFormat.file_path records.

Run via Flask CLI:
    flask migrate-filenames

Or call migrate_filenames_to_id_prefix() directly from a shell or admin endpoint.
"""
from __future__ import annotations
import os
from app.models import Story, StoryFormat
from app.models.base import db
from app.utils import get_epub_directory, get_html_directory
from app.services.logger import log_action, log_error


def migrate_filenames_to_id_prefix() -> dict:
    """
    For every Story record, rename files from the legacy "{filename_base}" naming to
    "{story.id}_{filename_base}" and update the corresponding StoryFormat records.

    Safe to run multiple times — skips files already using the new naming convention.
    Returns a summary dict with counts of renamed, skipped, and failed files.
    """
    epub_dir = get_epub_directory()
    html_dir = get_html_directory()

    renamed = 0
    skipped = 0
    failed = 0

    stories = Story.query.all()
    for story in stories:
        old_base = story.filename_base
        new_base = f"{story.id}_{old_base}"

        # --- EPUB ---
        old_epub = os.path.join(epub_dir, f"{old_base}.epub")
        new_epub = os.path.join(epub_dir, f"{new_base}.epub")
        epub_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()

        if os.path.exists(new_epub):
            # Already migrated; just ensure the DB record is correct.
            if epub_fmt and epub_fmt.file_path != new_epub:
                epub_fmt.file_path = new_epub
                epub_fmt.file_size = os.path.getsize(new_epub)
            skipped += 1
        elif os.path.exists(old_epub):
            try:
                os.rename(old_epub, new_epub)
                if epub_fmt:
                    epub_fmt.file_path = new_epub
                    epub_fmt.file_size = os.path.getsize(new_epub)
                else:
                    db.session.add(StoryFormat(
                        story_id=story.id,
                        format_type='epub',
                        file_path=new_epub,
                        file_size=os.path.getsize(new_epub)
                    ))
                log_action(f"[migrate] Renamed EPUB: {old_base} → {new_base} (story {story.id})")
                renamed += 1
            except Exception as e:
                log_error(f"[migrate] Failed to rename EPUB for story {story.id}: {e}")
                failed += 1

        # --- JSON ---
        old_json = os.path.join(html_dir, f"{old_base}.json")
        new_json = os.path.join(html_dir, f"{new_base}.json")
        json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()

        if os.path.exists(new_json):
            if json_fmt and json_fmt.file_path != new_json:
                json_fmt.file_path = new_json
                json_fmt.file_size = os.path.getsize(new_json)
            skipped += 1
        elif os.path.exists(old_json):
            try:
                import json as _json
                os.rename(old_json, new_json)
                if json_fmt:
                    json_fmt.file_path = new_json
                    json_fmt.file_size = os.path.getsize(new_json)
                    with open(new_json, 'r', encoding='utf-8') as f:
                        json_fmt.json_data = _json.dumps(_json.load(f))
                else:
                    with open(new_json, 'r', encoding='utf-8') as f:
                        json_data = _json.load(f)
                    db.session.add(StoryFormat(
                        story_id=story.id,
                        format_type='json',
                        file_path=new_json,
                        file_size=os.path.getsize(new_json),
                        json_data=_json.dumps(json_data)
                    ))
                log_action(f"[migrate] Renamed JSON: {old_base} → {new_base} (story {story.id})")
                renamed += 1
            except Exception as e:
                log_error(f"[migrate] Failed to rename JSON for story {story.id}: {e}")
                failed += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log_error(f"[migrate] DB commit failed: {e}")
        return {'success': False, 'error': str(e), 'renamed': renamed, 'skipped': skipped, 'failed': failed}

    summary = f"Migration complete: {renamed} renamed, {skipped} already migrated, {failed} failed."
    log_action(f"[migrate] {summary}")
    return {'success': True, 'message': summary, 'renamed': renamed, 'skipped': skipped, 'failed': failed}
