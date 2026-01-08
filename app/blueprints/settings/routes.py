from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.bulk_format_generator import BulkFormatGeneratorService
from app.services.logger import log_error, log_action
from app.models import Story
import traceback


@settings.route('/')
def index() -> ResponseReturnValue:
    return render_template('settings.html')


@settings.route('/generate-missing-epubs', methods=['POST'])
def generate_missing_epubs() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_epubs()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating missing EPUBs: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating EPUBs"
        }), 500


@settings.route('/generate-missing-html', methods=['POST'])
def generate_missing_html() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_html()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating missing HTML: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML"
        }), 500


@settings.route('/generate-all-missing-formats', methods=['POST'])
def generate_all_missing_formats() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_all_missing_formats()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating all missing formats: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating formats"
        }), 500


@settings.route('/get-generation-log')
def get_generation_log() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        log_data = service.get_generation_log()
        return jsonify(log_data)
    except Exception as e:
        error_msg = f"Error fetching generation log: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching log"
        }), 500


@settings.route('/get-excluded-stories')
def get_excluded_stories() -> ResponseReturnValue:
    try:
        excluded_stories = Story.query.filter(
            Story.auto_refresh_excluded == True
        ).all()
        
        return jsonify({
            "success": True,
            "stories": [
                {
                    "id": story.id,
                    "title": story.title,
                    "author": story.author.name if story.author else "Unknown",
                    "exclusion_reason": story.auto_refresh_exclusion_reason,
                    "exclusion_type": story.auto_refresh_exclusion_type,
                    "filename_base": story.filename_base
                }
                for story in excluded_stories
            ]
        })
    except Exception as e:
        error_msg = f"Error fetching excluded stories: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching excluded stories"
        }), 500


@settings.route('/remove-exclusion/<int:story_id>', methods=['POST'])
def remove_exclusion(story_id: int) -> ResponseReturnValue:
    try:
        from app.models import db
        
        story = db.session.get(Story, story_id)
        if not story:
            return jsonify({
                "success": False,
                "message": "Story not found"
            }), 404
        
        story.auto_refresh_excluded = False
        story.auto_refresh_exclusion_reason = None
        story.auto_refresh_exclusion_type = None
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Removed exclusion for '{story.title}'"
        })
    except Exception as e:
        error_msg = f"Error removing exclusion: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while removing exclusion"
        }), 500


@settings.route('/reset-all-exclusions', methods=['POST'])
def reset_all_exclusions() -> ResponseReturnValue:
    try:
        from app.models import db
        
        excluded_stories = Story.query.filter(
            Story.auto_refresh_excluded == True
        ).all()
        
        count = len(excluded_stories)
        
        for story in excluded_stories:
            story.auto_refresh_excluded = False
            story.auto_refresh_exclusion_reason = None
            story.auto_refresh_exclusion_type = None
        
        db.session.commit()
        
        log_action(f"Reset all exclusions for {count} stories")
        
        return jsonify({
            "success": True,
            "message": f"Reset exclusions for {count} stories. They will be checked again during the next automation cycle.",
            "count": count
        })
    except Exception as e:
        error_msg = f"Error resetting all exclusions: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while resetting exclusions"
        }), 500
