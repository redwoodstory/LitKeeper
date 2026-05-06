from __future__ import annotations
from flask import render_template, jsonify
from flask.typing import ResponseReturnValue
from . import auto_update_stories
from app.models import Story, db
from app.services.logger import log_action, log_error
import traceback


@auto_update_stories.route('/')
def index() -> ResponseReturnValue:
    """List all stories with their auto-update status."""
    stories = Story.query.order_by(
        Story.auto_update_enabled.desc(),
        Story.title
    ).all()
    return render_template('auto_update_stories/index.html', stories=stories)


@auto_update_stories.route('/<int:story_id>/toggle', methods=['POST'])
def toggle_story_auto_update(story_id: int) -> ResponseReturnValue:
    """Toggle auto_update_enabled for a single story."""
    try:
        story = db.session.get(Story, story_id)
        if not story:
            return jsonify({"success": False, "message": "Story not found"}), 404

        if story.auto_refresh_excluded and not story.auto_update_enabled:
            return jsonify({
                "success": False,
                "message": "Cannot enable auto-update: this story is excluded from auto-refresh"
            }), 400

        story.auto_update_enabled = not story.auto_update_enabled
        db.session.commit()

        log_action(f"Story {story_id} auto-update set to {story.auto_update_enabled}")
        return jsonify({
            "success": True,
            "auto_update_enabled": story.auto_update_enabled,
            "message": f"Auto-update {'enabled' if story.auto_update_enabled else 'disabled'}"
        })
    except Exception as e:
        db.session.rollback()
        log_error(f"Error toggling auto-update for story {story_id}: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
