from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.bulk_format_generator import BulkFormatGeneratorService
from app.services.logger import log_error, log_action
from app.models import Story, AppConfig, ReadingProgress, db
import traceback


@settings.route('/')
def index() -> ResponseReturnValue:
    theme_config = AppConfig.query.filter_by(key='theme_preference').first()
    theme_preference = theme_config.get_value() if theme_config else 'system'
    return render_template('settings.html', theme_preference=theme_preference)


@settings.route('/theme-preference', methods=['GET'])
def get_theme_preference() -> ResponseReturnValue:
    try:
        theme_config = AppConfig.query.filter_by(key='theme_preference').first()
        theme = theme_config.get_value() if theme_config else 'system'
        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        error_msg = f"Error getting theme preference: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error loading theme preference"}), 500


@settings.route('/theme-preference', methods=['POST'])
def save_theme_preference() -> ResponseReturnValue:
    try:
        data = request.get_json()
        theme = data.get('theme', 'system')

        if theme not in ['light', 'dark', 'system']:
            return jsonify({"success": False, "message": "Invalid theme value"}), 400

        theme_config = AppConfig.query.filter_by(key='theme_preference').first()
        if theme_config:
            theme_config.set_value(theme)
        else:
            theme_config = AppConfig(
                key='theme_preference',
                value=theme,
                value_type='string',
                description='User theme preference (light, dark, or system)'
            )
            db.session.add(theme_config)

        db.session.commit()
        log_action(f"Theme preference updated to: {theme}")

        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error saving theme preference: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "Error saving theme preference"}), 500


@settings.route('/generate-missing-epubs', methods=['POST'])
def generate_missing_epubs() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_epubs()
        return render_template('partials/generation_status.html', result=result, generation_type='epub')
    except Exception as e:
        error_msg = f"Error generating missing EPUBs: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/generation_status.html', 
                             result={"success": False, "message": "An error occurred while generating EPUBs"}, 
                             generation_type='epub'), 500


@settings.route('/generate-missing-html', methods=['POST'])
def generate_missing_html() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_html()
        return render_template('partials/generation_status.html', result=result, generation_type='html')
    except Exception as e:
        error_msg = f"Error generating missing HTML: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/generation_status.html', 
                             result={"success": False, "message": "An error occurred while generating HTML"}, 
                             generation_type='html'), 500


@settings.route('/generate-all-missing-formats', methods=['POST'])
def generate_all_missing_formats() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_all_missing_formats()
        return render_template('partials/generation_status.html', result=result, generation_type='all')
    except Exception as e:
        error_msg = f"Error generating all missing formats: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/generation_status.html', 
                             result={"success": False, "message": "An error occurred while generating formats"}, 
                             generation_type='all'), 500


@settings.route('/regenerate-covers-new', methods=['POST'])
def regenerate_covers_new() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.regenerate_all_covers()
        return render_template('partials/generation_status.html', result=result, generation_type='covers_new')
    except Exception as e:
        error_msg = f"Error regenerating covers: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/generation_status.html',
                             result={"success": False, "message": "An error occurred while regenerating covers"},
                             generation_type='covers_new'), 500


@settings.route('/regenerate-covers-same', methods=['POST'])
def regenerate_covers_same() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.reembed_existing_covers()
        return render_template('partials/generation_status.html', result=result, generation_type='covers_same')
    except Exception as e:
        error_msg = f"Error re-embedding covers: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/generation_status.html',
                             result={"success": False, "message": "An error occurred while re-embedding covers"},
                             generation_type='covers_same'), 500


@settings.route('/get-generation-log')
def get_generation_log() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        log_data = service.get_generation_log()
        return render_template('partials/generation_log.html', log_data=log_data)
    except Exception as e:
        error_msg = f"Error fetching generation log: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return "Error loading log", 500


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


@settings.route('/get-excluded-stories-html')
def get_excluded_stories_html() -> ResponseReturnValue:
    try:
        excluded_stories = Story.query.filter(
            Story.auto_refresh_excluded == True
        ).all()
        
        stories_data = [
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
        
        return render_template('partials/excluded_stories.html', stories=stories_data)
    except Exception as e:
        error_msg = f"Error fetching excluded stories: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return '<div class="text-center py-8 text-red-600 dark:text-red-400">Error loading excluded stories</div>', 500


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


@settings.route('/clear-all-reading-progress', methods=['POST'])
def clear_all_reading_progress() -> ResponseReturnValue:
    try:
        count = ReadingProgress.query.count()
        
        ReadingProgress.query.delete()
        db.session.commit()
        
        log_action(f"Cleared reading progress for {count} stories")
        
        return jsonify({
            "success": True,
            "message": f"Cleared reading progress for {count} {'story' if count == 1 else 'stories'}. All stories will start from the beginning.",
            "count": count
        })
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error clearing reading progress: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while clearing reading progress"
        }), 500
