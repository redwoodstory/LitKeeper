from __future__ import annotations
import os
import sqlite3


def sync_community_scores() -> int:
    """
    Populate literotica_score/views/favorites/comments on Story records by
    matching literotica_url against the mounted custom_url_dataset.db.
    Returns the number of stories updated.
    """
    from flask import current_app
    from app.models import Story
    from app.models.base import db
    from app.services.logger import log_action, log_error

    db_path = os.path.join(current_app.root_path, 'data', 'custom_url_dataset.db')
    if not os.path.exists(db_path):
        return 0

    try:
        with sqlite3.connect(db_path) as con:
            rows = con.execute(
                "SELECT url, score, views, favorites, comments FROM stories"
            ).fetchall()
    except Exception as e:
        log_error(f"[community_scores] Failed to read custom_url_dataset.db: {e}")
        return 0

    if not rows:
        return 0

    url_map: dict[str, tuple] = {
        row[0]: (row[1], row[2], row[3], row[4]) for row in rows
    }

    stories = Story.query.filter(Story.literotica_url.in_(list(url_map.keys()))).all()
    updated = 0

    for story in stories:
        stats = url_map.get(story.literotica_url)
        if not stats:
            continue
        score, views, favorites, comments = stats
        changed = False
        if score is not None:
            val = float(score)
            if story.literotica_score != val:
                story.literotica_score = val
                changed = True
        if views is not None:
            val = int(views)
            if story.literotica_views != val:
                story.literotica_views = val
                changed = True
        if favorites is not None:
            val = int(favorites)
            if story.literotica_favorites != val:
                story.literotica_favorites = val
                changed = True
        if comments is not None:
            val = int(comments)
            if story.literotica_comments != val:
                story.literotica_comments = val
                changed = True
        if changed:
            updated += 1

    if updated:
        try:
            db.session.commit()
            log_action(f"[community_scores] Synced stats for {updated} stories from custom dataset")
        except Exception as e:
            db.session.rollback()
            log_error(f"[community_scores] Failed to commit: {e}")
            return 0

    return updated
