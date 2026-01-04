from __future__ import annotations
import os
from typing import Optional
from flask import current_app
from app.models import Story, db
from app.utils import get_epub_directory, get_html_directory, get_cover_directory
from app.services import log_error
import traceback


class StoryDeletionService:
    
    def delete_story(self, story_id: int) -> dict:
        try:
            story = Story.query.get(story_id)
            if not story:
                return {
                    "success": False,
                    "message": "Story not found"
                }
            
            story_title = story.title
            filename_base = story.filename_base
            cover_filename = story.cover_filename
            
            deleted_files = []
            failed_files = []
            
            epub_dir = get_epub_directory()
            html_dir = get_html_directory()
            cover_dir = get_cover_directory()
            
            for story_format in story.formats:
                file_path = story_format.file_path
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(os.path.basename(file_path))
                    except Exception as e:
                        log_error(f"Failed to delete file {file_path}: {str(e)}")
                        failed_files.append(os.path.basename(file_path))
            
            json_file = os.path.join(html_dir, f"{filename_base}.json")
            if os.path.exists(json_file):
                try:
                    os.remove(json_file)
                    deleted_files.append(f"{filename_base}.json")
                except Exception as e:
                    log_error(f"Failed to delete JSON file {json_file}: {str(e)}")
                    failed_files.append(f"{filename_base}.json")
            
            if cover_filename:
                cover_file = os.path.join(cover_dir, cover_filename)
                if os.path.exists(cover_file):
                    try:
                        os.remove(cover_file)
                        deleted_files.append(cover_filename)
                    except Exception as e:
                        log_error(f"Failed to delete cover file {cover_file}: {str(e)}")
                        failed_files.append(cover_filename)
            else:
                default_cover = os.path.join(cover_dir, f"{filename_base}.jpg")
                if os.path.exists(default_cover):
                    try:
                        os.remove(default_cover)
                        deleted_files.append(f"{filename_base}.jpg")
                    except Exception as e:
                        log_error(f"Failed to delete cover file {default_cover}: {str(e)}")
                        failed_files.append(f"{filename_base}.jpg")
            
            db.session.delete(story)
            db.session.commit()
            
            return {
                "success": True,
                "message": f"Story '{story_title}' deleted successfully",
                "deleted_files": deleted_files,
                "failed_files": failed_files
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error deleting story: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return {
                "success": False,
                "message": "An error occurred while deleting the story"
            }
