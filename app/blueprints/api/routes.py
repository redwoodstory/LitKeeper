from __future__ import annotations
from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort, Flask, render_template
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error, log_url, log_action, generate_cover_image, extract_cover_from_epub, get_library_data
from app.utils import get_epub_directory, get_html_directory, get_cover_directory
from app.utils.security import validate_file_in_directory
from app.validators import StoryDownloadRequest, StoryMetadataUpdate
from app.services.story_downloader import download_story
from app.services.metadata_refresh_service import MetadataRefreshService
from pydantic import ValidationError
import os
from datetime import datetime
import traceback
import json
from typing import Optional

api = Blueprint('api', __name__, url_prefix='/api')

@api.route("/queue", methods=['POST'])
def queue_download() -> ResponseReturnValue:
    """Queue a story for background download"""
    try:
        if request.is_json:
            data = request.get_json()
            url = data.get('url', '')
            formats = data.get('format', ['epub', 'html'])
        else:
            url = request.form.get('url', '')
            formats = request.form.getlist('format') or ['epub', 'html']

        validated = StoryDownloadRequest(url=url, format=formats)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nData: {request.get_data(as_text=True)}")
        
        if request.headers.get('HX-Request'):
            return render_template('partials/queue_status.html', 
                                 queue_item={'status': 'failed', 'error_message': error_msg})
        
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    log_url(validated.url)

    try:
        from app.models import DownloadQueueItem, db

        existing = DownloadQueueItem.query.filter_by(
            url=validated.url,
            status='pending'
        ).first()

        if existing:
            if request.headers.get('HX-Request'):
                return render_template('partials/queue_status.html', queue_item=existing.to_dict())
            return jsonify({
                "success": True,
                "message": "Story is already in the download queue",
                "queue_item": existing.to_dict()
            })

        existing_processing = DownloadQueueItem.query.filter_by(
            url=validated.url,
            status='processing'
        ).first()

        if existing_processing:
            if request.headers.get('HX-Request'):
                return render_template('partials/queue_status.html', queue_item=existing_processing.to_dict())
            return jsonify({
                "success": True,
                "message": "Story is currently being downloaded",
                "queue_item": existing_processing.to_dict()
            })

        queue_item = DownloadQueueItem(
            url=validated.url,
            status='pending'
        )
        queue_item.set_formats(validated.format)
        db.session.add(queue_item)
        db.session.commit()

        log_action(f"Added story to download queue: {validated.url} (ID: {queue_item.id})")

        if request.headers.get('HX-Request'):
            return render_template('partials/queue_status.html', queue_item=queue_item.to_dict())
        
        return jsonify({
            "success": True,
            "message": "Story added to download queue",
            "queue_item": queue_item.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        error_msg = f"Error adding to queue: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        
        if request.headers.get('HX-Request'):
            return render_template('partials/queue_status.html', 
                                 queue_item={'status': 'failed', 'error_message': 'An error occurred while adding story to queue'})
        
        return jsonify({
            "success": False,
            "message": "An error occurred while adding story to queue"
        }), 500

@api.route("/preview", methods=['POST'])
def preview_story() -> ResponseReturnValue:
    try:
        data = request.get_json()
        url = data.get('url', '')
        formats = data.get('format', ['epub'])

        validated = StoryDownloadRequest(url=url, format=formats)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    log_url(validated.url)

    try:
        from app.services import story_processor
        story_data = download_story(validated.url)
        story_content, title, author, category, tags, author_url, page_count, series_url = story_data

        if not story_content or not title:
            return jsonify({
                "success": False,
                "message": "Failed to extract story metadata"
            }), 500

        story_processor._story_cache[validated.url] = story_data

        return jsonify({
            "success": True,
            "metadata": {
                "url": validated.url,
                "title": title or "Unknown Title",
                "author": author or "Unknown Author",
                "category": category,
                "tags": tags or [],
                "author_url": author_url,
                "formats": validated.format
            }
        })

    except Exception as e:
        error_msg = f"Error previewing story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching story metadata"
        }), 500

@api.route("/save", methods=['POST'])
def save_story() -> ResponseReturnValue:
    try:
        data = request.get_json()
        validated = StoryMetadataUpdate(**data)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": False,
            "message": error_msg
        }), 400

    log_url(validated.url)

    try:
        from app.services.story_processor import save_story_with_metadata
        result = save_story_with_metadata(
            url=validated.url,
            formats=validated.formats,
            title=validated.title,
            author=validated.author,
            category=validated.category,
            tags=validated.tags
        )
        return jsonify(result.to_dict())

    except Exception as e:
        error_msg = f"Error saving story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while saving the story"
        }), 500

@api.route("/download", methods=['GET', 'POST'])
def download() -> ResponseReturnValue:
    """DEPRECATED: Use /api/queue for new clients. Maintained for backward compatibility."""
    try:
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                url = data.get('url', '')
                wait = data.get('wait', True)
                if isinstance(wait, str):
                    wait = wait.lower() == 'true'
                formats = data.get('format', ['epub'])
            else:
                url = request.form.get('url', '')
                wait = request.form.get('wait', 'true').lower() == 'true'
                formats = request.form.getlist('format') or ['epub']
        else:
            url = request.args.get('url', '')
            wait = request.args.get('wait', 'true').lower() == 'true'
            formats_param = request.args.get('format', 'epub')
            formats = formats_param.split(',') if formats_param else ['epub']

        validated = StoryDownloadRequest(url=url, wait=wait, format=formats)

    except ValidationError as e:
        error_details = e.errors()[0]
        error_msg = f"{error_details['loc'][0]}: {error_details['msg']}"
        log_error(f"Validation error: {error_msg}\nRequest Method: {request.method}\nData: {request.get_data(as_text=True)}")
        return jsonify({
            "success": "false",
            "message": error_msg
        }), 400

    url = validated.url
    log_url(url)

    if not validated.wait:
        from app.models import DownloadQueueItem, db

        existing = DownloadQueueItem.query.filter_by(
            url=validated.url,
            status='pending'
        ).first()

        if existing:
            return jsonify({
                "success": True,
                "message": "Already in queue",
                "queue_item": existing.to_dict()
            })

        queue_item = DownloadQueueItem(url=validated.url, status='pending')
        queue_item.set_formats(validated.format)
        db.session.add(queue_item)
        db.session.commit()

        log_action(f"Added to queue via /download: {validated.url} (ID: {queue_item.id})")

        return jsonify({
            "success": True,
            "message": "Story added to download queue",
            "queue_item": queue_item.to_dict()
        })

    result = download_story_and_create_files(url, validated.format)
    return jsonify(result.to_dict())

@api.route("/library", methods=["GET"])
def get_library() -> ResponseReturnValue:
    try:
        stories = get_library_data()
        return jsonify({"stories": stories})
    except Exception as e:
        log_error(f"Error fetching library: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"stories": []})

@api.route("/cover/<filename>")
def get_cover(filename: str) -> ResponseReturnValue:
    from app.services import generate_cover_image, extract_cover_from_epub

    if not filename or not filename.endswith('.jpg'):
        abort(404)

    cover_directory = get_cover_directory()

    if not validate_file_in_directory(cover_directory, filename):
        log_error(f"Path traversal blocked in cover: {filename}")
        abort(403)

    cover_path = os.path.join(cover_directory, filename)

    if os.path.exists(cover_path):
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')

    os.makedirs(cover_directory, exist_ok=True)

    sanitized_title = filename.replace('.jpg', '')
    html_directory = get_html_directory()
    epub_directory = get_epub_directory()
    json_path = os.path.join(html_directory, f"{sanitized_title}.json")
    epub_path = os.path.join(epub_directory, f"{sanitized_title}.epub")

    title = sanitized_title
    author = 'Unknown Author'

    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            title = story_data.get('title', sanitized_title)
            author = story_data.get('author', 'Unknown Author')
        except Exception as e:
            log_error(f"Error reading JSON metadata: {str(e)}")

    if os.path.exists(epub_path):
        try:
            if extract_cover_from_epub(epub_path, cover_path):
                return send_from_directory(cover_directory, filename, mimetype='image/jpeg')
        except Exception as e:
            log_error(f"Error extracting cover from EPUB: {str(e)}\n{traceback.format_exc()}")

    try:
        generate_cover_image(title, author, cover_path)
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')
    except Exception as e:
        log_error(f"Error generating cover: {str(e)}\n{traceback.format_exc()}")
        abort(500)

@api.route("/metadata/search/<int:story_id>", methods=['POST'])
def search_metadata(story_id: int) -> ResponseReturnValue:
    try:
        service = MetadataRefreshService()
        result = service.search_for_story(story_id)
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error searching for story metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while searching for metadata"
        }), 500

@api.route("/metadata/refresh/<int:story_id>", methods=['POST'])
def refresh_metadata(story_id: int) -> ResponseReturnValue:
    try:
        data = request.get_json()
        url = data.get('url')
        method = data.get('method', 'manual')
        
        if not url:
            return jsonify({
                "success": False,
                "message": "URL is required"
            }), 400
        
        service = MetadataRefreshService()
        result = service.refresh_metadata_from_url(story_id, url, method)
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error refreshing metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while refreshing metadata"
        }), 500

@api.route("/metadata/missing", methods=['GET'])
def get_missing_metadata() -> ResponseReturnValue:
    try:
        from app.models import Story
        from app.services.metadata_refresh_service import MetadataRefreshService

        stories = Story.query.filter(Story.literotica_url.is_(None)).all()
        
        stories_needing_manual_intervention = []
        service = MetadataRefreshService()
        
        for story in stories:
            try:
                search_result = service.search_for_story(story.id)
                
                if search_result.get('success') and search_result.get('auto_match'):
                    best_match = search_result.get('best_match')
                    if best_match and best_match.get('confidence', 0.0) >= 1.0:
                        continue
                
                stories_needing_manual_intervention.append(story)
            except:
                stories_needing_manual_intervention.append(story)

        return jsonify({
            "success": True,
            "count": len(stories_needing_manual_intervention),
            "stories": [story.to_library_dict() for story in stories_needing_manual_intervention]
        })
    except Exception as e:
        error_msg = f"Error fetching missing metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching stories"
        }), 500

@api.route("/format/generate-epub/<int:story_id>", methods=['POST'])
def generate_epub_format(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story, db

        service = FormatGeneratorService()
        result = service.generate_epub_from_json(story_id)

        if result.get('success') and request.headers.get('HX-Request'):
            story = db.session.get(Story, story_id)
            if story:
                story_data = {
                    'id': story.id,
                    'title': story.title,
                    'author': {'name': story.author.name, 'literotica_url': story.author.literotica_url} if story.author else None,
                    'category': {'name': story.category.name} if story.category else None,
                    'tags': [tag.name for tag in story.tags],
                    'cover': story.cover_filename,
                    'formats': [fmt.format_type for fmt in story.formats],
                    'html_file': f"{story.filename_base}.html",
                    'epub_file': f"{story.filename_base}.epub",
                    'source_url': story.literotica_url,
                    'series_url': story.literotica_series_url,
                    'page_count': story.literotica_page_count,
                    'word_count': story.word_count,
                    'chapter_count': story.chapter_count,
                    'size': next((f.file_size for f in story.formats if f.format_type == 'epub'), None),
                    'created_at': story.created_at,
                    'auto_update_enabled': story.auto_update_enabled,
                    'is_series': bool(story.literotica_series_url and story.chapter_count > 1),
                }
                return render_template('components/story_modal.html', story=story_data)

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating EPUB format: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating EPUB format"
        }), 500

@api.route("/format/generate-html/<int:story_id>", methods=['POST'])
def generate_html_format(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story, db

        service = FormatGeneratorService()
        result = service.generate_html_from_url(story_id)

        if result.get('success') and request.headers.get('HX-Request'):
            story = db.session.get(Story, story_id)
            if story:
                story_data = {
                    'id': story.id,
                    'title': story.title,
                    'author': {'name': story.author.name, 'literotica_url': story.author.literotica_url} if story.author else None,
                    'category': {'name': story.category.name} if story.category else None,
                    'tags': [tag.name for tag in story.tags],
                    'cover': story.cover_filename,
                    'formats': [fmt.format_type for fmt in story.formats],
                    'html_file': f"{story.filename_base}.html",
                    'epub_file': f"{story.filename_base}.epub",
                    'source_url': story.literotica_url,
                    'series_url': story.literotica_series_url,
                    'page_count': story.literotica_page_count,
                    'word_count': story.word_count,
                    'chapter_count': story.chapter_count,
                    'size': next((f.file_size for f in story.formats if f.format_type == 'epub'), None),
                    'created_at': story.created_at,
                    'auto_update_enabled': story.auto_update_enabled,
                    'is_series': bool(story.literotica_series_url and story.chapter_count > 1),
                }
                return render_template('components/story_modal.html', story=story_data)

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating HTML format: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML format"
        }), 500

@api.route("/format/generate-html-with-metadata/<int:story_id>", methods=['POST'])
def generate_html_with_metadata(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.format_generator import FormatGeneratorService
        from app.models import Story
        
        data = request.get_json()
        url = data.get('url')
        method = data.get('method', 'manual')
        
        if not url:
            return jsonify({
                "success": False,
                "message": "URL is required"
            }), 400

        service = FormatGeneratorService()
        result = service.generate_html_with_metadata(story_id, url, method)

        if result.get('success') and request.headers.get('HX-Request'):
            story = Story.query.get(story_id)
            if story:
                return jsonify({
                    "success": True,
                    "message": result.get('message'),
                    "fields_changed": result.get('fields_changed', []),
                    "story": story.to_library_dict()
                })

        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating HTML format with metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML format"
        }), 500

@api.route("/story/delete/<int:story_id>", methods=['DELETE'])
def delete_story(story_id: int) -> ResponseReturnValue:
    try:
        from app.services.story_deletion import StoryDeletionService

        service = StoryDeletionService()
        result = service.delete_story(story_id)

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 404 if 'not found' in result.get('message', '').lower() else 500

    except Exception as e:
        error_msg = f"Error deleting story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while deleting the story"
        }), 500

@api.route("/story/<int:story_id>/metadata", methods=['PUT'])
def update_story_metadata(story_id: int) -> ResponseReturnValue:
    try:
        from app.models import Story, Author, Category, db
        from app.services.epub_service import EpubService
        
        story = Story.query.get(story_id)
        
        if not story:
            return jsonify({
                "success": False,
                "message": "Story not found"
            }), 404
        
        data = request.get_json()
        title = data.get('title', '').strip()
        author_name = data.get('author', '').strip()
        category_name = data.get('category', '').strip()
        tags = data.get('tags', [])
        
        if not title:
            return jsonify({
                "success": False,
                "message": "Title is required"
            }), 400
        
        old_title = story.title
        old_author = story.author.name if story.author else ''
        
        story.title = title
        
        if author_name:
            author_obj = Author.query.filter_by(name=author_name).first()
            if not author_obj:
                author_obj = Author(name=author_name)
                db.session.add(author_obj)
                db.session.flush()
            story.author = author_obj
        
        if category_name:
            category_obj = Category.query.filter_by(name=category_name).first()
            if not category_obj:
                category_obj = Category(name=category_name)
                db.session.add(category_obj)
                db.session.flush()
            story.category = category_obj
        else:
            story.category = None
        
        story.set_tags(tags)
        
        db.session.commit()
        
        log_action(f"Updated metadata for story {story_id}: {title}")
        
        cover_regenerated = False
        epub_updated = False
        cover_filename = None
        
        if old_title != title or old_author != author_name:
            try:
                cover_directory = get_cover_directory()
                os.makedirs(cover_directory, exist_ok=True)
                
                cover_filename = story.cover_filename or f"{story.filename_base}.jpg"
                cover_path = os.path.join(cover_directory, cover_filename)
                
                generate_cover_image(story.title, author_name or 'Unknown Author', cover_path)
                cover_regenerated = True
                log_action(f"Auto-regenerated cover for story: {story.title}")
                
                has_epub = any(f.format_type == 'epub' for f in story.formats)
                if has_epub:
                    epub_directory = get_epub_directory()
                    epub_path = os.path.join(epub_directory, f"{story.filename_base}.epub")
                    
                    if os.path.exists(epub_path):
                        if EpubService.update_epub_cover(epub_path, cover_path):
                            epub_updated = True
                            log_action(f"Updated EPUB cover for story: {story.title}")
                
                if not story.cover_filename:
                    story.cover_filename = cover_filename
                    db.session.commit()
                    
            except Exception as cover_error:
                log_error(f"Error regenerating cover during metadata update: {str(cover_error)}")
        
        return jsonify({
            "success": True,
            "message": "Metadata updated successfully",
            "story": story.to_library_dict(),
            "cover_regenerated": cover_regenerated,
            "epub_updated": epub_updated,
            "cover_filename": cover_filename
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error updating story metadata: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while updating metadata"
        }), 500

@api.route("/story/toggle-auto-update/<int:story_id>", methods=['POST'])
def toggle_auto_update(story_id: int) -> ResponseReturnValue:
    try:
        from app.models import Story, db

        story = Story.query.get(story_id)

        if not story:
            return jsonify({
                "success": False,
                "message": "Story not found"
            }), 404

        story.auto_update_enabled = not story.auto_update_enabled
        db.session.commit()

        return jsonify({
            "success": True,
            "auto_update_enabled": story.auto_update_enabled,
            "message": f"Auto-update {'enabled' if story.auto_update_enabled else 'disabled'}"
        })

    except Exception as e:
        db.session.rollback()
        error_msg = f"Error toggling auto-update: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while toggling auto-update"
        }), 500

@api.route("/queue", methods=['GET'])
def get_queue() -> ResponseReturnValue:
    """Get all queued/processing downloads"""
    try:
        from app.models import DownloadQueueItem

        items = DownloadQueueItem.query.filter(
            DownloadQueueItem.status.in_(['pending', 'processing'])
        ).order_by(DownloadQueueItem.created_at.asc()).all()

        return jsonify({
            "success": True,
            "queue": [item.to_dict() for item in items],
            "count": len(items)
        })

    except Exception as e:
        error_msg = f"Error fetching queue: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching download queue"
        }), 500

@api.route("/queue/<int:queue_id>", methods=['GET'])
def get_queue_item(queue_id: int) -> ResponseReturnValue:
    """Get status of a specific queue item"""
    try:
        from app.models import DownloadQueueItem

        item = DownloadQueueItem.query.get(queue_id)

        if not item:
            return jsonify({
                "success": False,
                "message": "Queue item not found"
            }), 404

        return jsonify({
            "success": True,
            "queue_item": item.to_dict()
        })

    except Exception as e:
        error_msg = f"Error fetching queue item: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching queue item"
        }), 500

@api.route("/queue/<int:queue_id>", methods=['DELETE'])
def cancel_queue_item(queue_id: int) -> ResponseReturnValue:
    """Cancel a pending queue item"""
    try:
        from app.models import DownloadQueueItem, db

        item = DownloadQueueItem.query.get(queue_id)

        if not item:
            return jsonify({
                "success": False,
                "message": "Queue item not found"
            }), 404

        if item.status == 'processing':
            return jsonify({
                "success": False,
                "message": "Cannot cancel item that is currently processing"
            }), 400

        if item.status in ['completed', 'failed']:
            return jsonify({
                "success": False,
                "message": f"Cannot cancel item with status: {item.status}"
            }), 400

        db.session.delete(item)
        db.session.commit()

        log_action(f"Cancelled queue item {queue_id}")

        return jsonify({
            "success": True,
            "message": "Queue item cancelled"
        })

    except Exception as e:
        db.session.rollback()
        error_msg = f"Error cancelling queue item: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while cancelling queue item"
        }), 500

@api.route("/queue/status-card/<int:queue_id>", methods=['GET'])
def get_queue_status_card(queue_id: int) -> ResponseReturnValue:
    """Get HTML status card for a queue item (for HTMX polling)"""
    try:
        from app.models import DownloadQueueItem
        from app.blueprints.library.routes import get_library_data

        item = DownloadQueueItem.query.get(queue_id)

        if not item:
            return render_template('partials/queue_status.html', 
                                 queue_item={'status': 'failed', 'error_message': 'Queue item not found'})

        library_content = None
        if item.status == 'completed':
            stories = get_library_data()
            library_html = render_template('_library_content.html', stories=stories)
            library_content = f'<div id="library-content" hx-swap-oob="true">{library_html}</div>'

        return render_template('partials/queue_status.html', 
                             queue_item=item.to_dict(), 
                             library_content=library_content)

    except Exception as e:
        error_msg = f"Error fetching queue status card: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return render_template('partials/queue_status.html', 
                             queue_item={'status': 'failed', 'error_message': 'Error loading status'})

@api.route("/story/<int:story_id>/card", methods=['GET'])
def get_story_card(story_id: int) -> ResponseReturnValue:
    from app.models import Story
    
    story = Story.query.get_or_404(story_id)
    story_dict = story.to_library_dict()
    
    return render_template('partials/story_card.html', story=story_dict)

@api.route("/story/<int:story_id>/modal", methods=['GET'])
def get_story_modal(story_id: int) -> ResponseReturnValue:
    from app.models import Story
    
    story = Story.query.get_or_404(story_id)
    
    story_data = {
        'id': story.id,
        'title': story.title,
        'author': {'name': story.author.name, 'literotica_url': story.author.literotica_url} if story.author else None,
        'category': {'name': story.category.name} if story.category else None,
        'tags': [tag.name for tag in story.tags],
        'cover': story.cover_filename,
        'formats': [fmt.format_type for fmt in story.formats],
        'html_file': f"{story.filename_base}.html",
        'epub_file': f"{story.filename_base}.epub",
        'source_url': story.literotica_url,
        'series_url': story.literotica_series_url,
        'page_count': story.literotica_page_count,
        'word_count': story.word_count,
        'chapter_count': story.chapter_count,
        'size': next((f.file_size for f in story.formats if f.format_type == 'epub'), None),
        'created_at': story.created_at,
        'auto_update_enabled': story.auto_update_enabled,
        'is_series': bool(story.literotica_series_url and story.chapter_count > 1),
    }
    
    return render_template('components/story_modal.html', story=story_data)

@api.route("/story/<int:story_id>/regenerate-cover", methods=['POST'])
def regenerate_cover(story_id: int) -> ResponseReturnValue:
    """Regenerate cover image for a story and update both the covers directory and EPUB file"""
    try:
        from app.models import Story
        from app.models.base import db
        from app.services.epub_service import EpubService
        
        story = Story.query.get_or_404(story_id)
        
        cover_directory = get_cover_directory()
        os.makedirs(cover_directory, exist_ok=True)
        
        cover_filename = story.cover_filename or f"{story.filename_base}.jpg"
        cover_path = os.path.join(cover_directory, cover_filename)
        
        author_name = story.author.name if story.author else 'Unknown Author'
        
        generate_cover_image(story.title, author_name, cover_path)
        log_action(f"Regenerated cover for story: {story.title}")
        
        epub_updated = False
        has_epub = any(f.format_type == 'epub' for f in story.formats)
        
        if has_epub:
            epub_directory = get_epub_directory()
            epub_path = os.path.join(epub_directory, f"{story.filename_base}.epub")
            
            if os.path.exists(epub_path):
                if EpubService.update_epub_cover(epub_path, cover_path):
                    epub_updated = True
                    log_action(f"Updated EPUB cover for story: {story.title}")
                else:
                    log_error(f"Failed to update EPUB cover for story: {story.title}")
        
        if not story.cover_filename:
            story.cover_filename = cover_filename
            db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Cover regenerated successfully",
            "epub_updated": epub_updated,
            "cover_filename": cover_filename
        })
        
    except Exception as e:
        error_msg = f"Error regenerating cover: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "Failed to regenerate cover"
        }), 500

@api.route("/offline/story-urls", methods=['GET'])
def get_offline_story_urls() -> ResponseReturnValue:
    """Return all URLs needed for offline reading.

    Returns two lists:
    - reader_urls: /read/<filename> JSON reader pages (all stories)
    - epub_urls:   /epub/reader/<id> page + /epub/file/<id> binary (epub stories only)

    Caching both lists gives full offline support for both reader types.
    """
    try:
        from app.models import Story, StoryFormat

        # All stories get a JSON reader URL
        all_stories = Story.query.with_entities(Story.id, Story.filename_base).all()
        reader_urls = [f"/read/{row.filename_base}.html" for row in all_stories]

        # Only stories with an epub format get epub URLs
        epub_story_ids = {
            row.story_id
            for row in StoryFormat.query.with_entities(StoryFormat.story_id)
            .filter(StoryFormat.format_type == 'epub').all()
        }
        epub_urls = []
        for row in all_stories:
            if row.id in epub_story_ids:
                epub_urls.append(f"/epub/reader/{row.id}")
                epub_urls.append(f"/epub/file/{row.id}")

        return jsonify({
            "success": True,
            "reader_urls": reader_urls,
            "epub_urls": epub_urls,
            "count": len(reader_urls) + len(epub_urls),
            # Legacy key — keep for any old clients
            "urls": reader_urls,
        })

    except Exception as e:
        log_error(f"Error fetching offline story URLs: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching story URLs",
            "reader_urls": [],
            "epub_urls": [],
            "urls": [],
        }), 500
