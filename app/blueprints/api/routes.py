from __future__ import annotations
from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort, Flask, render_template
from flask.typing import ResponseReturnValue
from app.services import download_story_and_create_files, log_error, log_url, log_action, generate_cover_image, extract_cover_from_epub, get_library_data
from app.utils import get_epub_directory, get_html_directory, get_cover_directory
from app.utils.security import validate_file_in_directory
from app.validators import StoryDownloadRequest, StoryMetadataUpdate
from app.services.story_downloader import download_story, fetch_story_metadata
from app.services.metadata_refresh_service import MetadataRefreshService
from pydantic import ValidationError
import os
import base64
from datetime import datetime
import traceback
import json
from typing import Optional
from sqlalchemy.orm import joinedload

api = Blueprint('api', __name__, url_prefix='/api')

@api.route("/queue", methods=['POST'])
def queue_download() -> ResponseReturnValue:
    """Queue a story for background download"""
    try:
        if request.is_json:
            data = request.get_json()
            url = data.get('url', '')
        else:
            url = request.form.get('url', '')
        
        formats = ['epub', 'html']
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
            "message": "Story added to queue",
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
        metadata = fetch_story_metadata(validated.url)

        if not metadata or not metadata.get('title'):
            return jsonify({
                "success": False,
                "message": "Failed to extract story metadata"
            }), 500

        return jsonify({
            "success": True,
            "metadata": {
                "url": validated.url,
                "title": metadata.get('title', 'Unknown Title'),
                "author": metadata.get('author', 'Unknown Author'),
                "category": metadata.get('category'),
                "tags": metadata.get('tags', []),
                "author_url": metadata.get('author_url'),
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
            "message": "Story added to queue",
            "queue_item": queue_item.to_dict()
        })

    result = download_story_and_create_files(url, validated.format)
    return jsonify(result.to_dict())

@api.route("/library", methods=["GET"])
def get_library() -> ResponseReturnValue:
    try:
        stories = get_library_data()
        for s in stories:
            print(f"[LK-API] Story '{s['title']}' (id={s['id']}) tags={s['tags']}")
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
                return render_template('components/story_modal.html', story=_story_to_modal_dict(story))

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
        from app.models import Story, db
        from app.models.format_queue import FormatQueueItem

        story = db.session.get(Story, story_id)
        if not story:
            return jsonify({"success": False, "message": "Story not found"}), 404

        if not story.literotica_url:
            return jsonify({"success": False, "needs_url": True, "message": "Story requires Literotica URL"})

        existing = FormatQueueItem.query.filter(
            FormatQueueItem.story_id == story_id,
            FormatQueueItem.job_type == 'generate_html',
            FormatQueueItem.status.in_(['pending', 'processing'])
        ).first()

        if existing:
            if request.headers.get('HX-Request'):
                return render_template('partials/format_generating.html', job=existing.to_dict(), story_id=story_id)
            return jsonify({"success": True, "queued": True, "job_id": existing.id, "message": "Already queued"})

        job = FormatQueueItem(story_id=story_id, job_type='generate_html')
        db.session.add(job)
        db.session.commit()

        log_action(f"Queued HTML generation for story {story_id} (job {job.id})")

        if request.headers.get('HX-Request'):
            return render_template('partials/format_generating.html', job=job.to_dict(), story_id=story_id)

        return jsonify({"success": True, "queued": True, "job_id": job.id, "message": "HTML generation queued"})

    except Exception as e:
        error_msg = f"Error queuing HTML generation: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "An error occurred while queuing HTML generation"}), 500

@api.route("/format/generate-html-with-metadata/<int:story_id>", methods=['POST'])
def generate_html_with_metadata(story_id: int) -> ResponseReturnValue:
    try:
        from app.models import db
        from app.models.format_queue import FormatQueueItem

        data = request.get_json()
        url = data.get('url') if data else None
        method = data.get('method', 'manual') if data else 'manual'

        if not url:
            return jsonify({"success": False, "message": "URL is required"}), 400

        existing = FormatQueueItem.query.filter(
            FormatQueueItem.story_id == story_id,
            FormatQueueItem.job_type == 'generate_html_with_metadata',
            FormatQueueItem.status.in_(['pending', 'processing'])
        ).first()

        if existing:
            return jsonify({"success": True, "queued": True, "job_id": existing.id, "message": "Already queued"})

        job = FormatQueueItem(story_id=story_id, job_type='generate_html_with_metadata', url=url, method=method)
        db.session.add(job)
        db.session.commit()

        log_action(f"Queued HTML+metadata generation for story {story_id} (job {job.id})")

        return jsonify({"success": True, "queued": True, "job_id": job.id, "message": "HTML generation queued"})

    except Exception as e:
        error_msg = f"Error queuing HTML+metadata generation: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({"success": False, "message": "An error occurred while queuing HTML generation"}), 500

@api.route("/format/status/<int:job_id>", methods=['GET'])
def get_format_job_status(job_id: int) -> ResponseReturnValue:
    """Poll status of a background format generation job."""
    try:
        from app.models.format_queue import FormatQueueItem
        from app.models import Story, db

        job = db.session.get(FormatQueueItem, job_id)
        if not job:
            return jsonify({"success": False, "message": "Job not found"}), 404

        if request.headers.get('HX-Request'):
            if job.status == 'completed':
                story = db.session.get(Story, job.story_id)
                if story:
                    story_data = _story_to_modal_dict(story)
                    return render_template('components/story_modal.html', story=story_data)
            if job.status == 'failed':
                return render_template('partials/format_generating.html', job=job.to_dict(), story_id=job.story_id)
            return render_template('partials/format_generating.html', job=job.to_dict(), story_id=job.story_id)

        data = job.to_dict()
        if job.status == 'completed':
            story = db.session.get(Story, job.story_id)
            if story:
                data['story'] = story.to_library_dict()
        return jsonify({"success": True, **data})

    except Exception as e:
        log_error(f"Error fetching format job status: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Error fetching job status"}), 500


def _story_to_modal_dict(story) -> dict:
    return {
        'id': story.id,
        'title': story.title,
        'author': {'name': story.author.name, 'literotica_url': story.author.literotica_url} if story.author else None,
        'category': {'name': story.category.name} if story.category else None,
        'tags': [tag.name for tag in story.tags],
        'cover': story.cover_filename,
        'formats': [fmt.format_type for fmt in story.formats],
        'filename_base': story.filename_base,
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
        'rating': story.rating,
        'in_queue': bool(story.in_queue),
        'description': story.description,
    }


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
        description = data.get('description', '').strip()

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
        story.description = description if description else None

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

@api.route("/story/<int:story_id>/rating", methods=['POST'])
def set_story_rating(story_id: int) -> ResponseReturnValue:
    from app.models import Story, db

    story = Story.query.get(story_id)
    if not story:
        return jsonify({"success": False, "message": "Story not found"}), 404

    data = request.get_json(silent=True) or {}
    rating = data.get('rating')

    if rating is not None:
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"success": False, "message": "Rating must be 1–5 or null"}), 400

    story.rating = rating
    db.session.commit()
    return jsonify({"rating": story.rating})


@api.route("/story/<int:story_id>/queue", methods=['POST'])
def toggle_story_queue(story_id: int) -> ResponseReturnValue:
    from app.models import Story, db
    from datetime import datetime

    story = Story.query.get(story_id)
    if not story:
        return jsonify({"success": False, "message": "Story not found"}), 404

    data = request.get_json(silent=True) or {}
    in_queue = data.get('in_queue')

    if not isinstance(in_queue, bool):
        return jsonify({"success": False, "message": "in_queue must be a boolean"}), 400

    story.in_queue = in_queue
    
    if in_queue:
        queued_at_str = data.get('queued_at')
        if queued_at_str:
            try:
                from datetime import datetime as dt
                story.queued_at = dt.fromisoformat(queued_at_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                story.queued_at = datetime.utcnow()
        else:
            story.queued_at = datetime.utcnow()
    else:
        story.queued_at = None
    
    db.session.commit()
    return jsonify({
        "in_queue": story.in_queue,
        "queued_at": story.queued_at.isoformat() if story.queued_at else None
    })


@api.route("/story/<int:story_id>/last_opened", methods=['POST'])
def update_last_opened(story_id: int) -> ResponseReturnValue:
    from app.models import Story, db
    from datetime import datetime as dt

    story = Story.query.get(story_id)
    if not story:
        return jsonify({"success": False, "message": "Story not found"}), 404

    data = request.get_json(silent=True) or {}
    last_opened_at_str = data.get('last_opened_at')
    
    if last_opened_at_str:
        try:
            story.last_opened_at = dt.fromisoformat(last_opened_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            story.last_opened_at = datetime.utcnow()
    else:
        story.last_opened_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({
        "success": True,
        "last_opened_at": story.last_opened_at.isoformat() if story.last_opened_at else None
    })


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
        'filename_base': story.filename_base,
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
        'rating': story.rating,
        'in_queue': bool(story.in_queue),
        'description': story.description,
        'reading_progress': {
            'percentage': story.reading_progress.percentage,
            'is_completed': story.reading_progress.is_completed,
        } if story.reading_progress and story.reading_progress.percentage else None,
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

@api.route("/download/bulk", methods=['GET'])
def download_bulk() -> ResponseReturnValue:
    """Bulk content download — returns base64-encoded epub, html, and cover for each requested story ID.

    Used by the iOS app to fetch multiple stories in a single request, avoiding per-story
    requests that trigger CrowdSec rate-limiting rules.
    """
    from app.models import Story

    ids_param = request.args.get('ids', '')
    if not ids_param:
        return jsonify({'stories': {}})

    try:
        story_ids = [int(i) for i in ids_param.split(',') if i.strip()]
    except ValueError:
        return jsonify({'error': 'Invalid ids parameter'}), 400

    if not story_ids:
        return jsonify({'stories': {}})

    stories = Story.query.filter(Story.id.in_(story_ids)).all()
    epub_dir = get_epub_directory()
    html_dir = get_html_directory()
    cover_dir = get_cover_directory()

    result = {}
    for story in stories:
        entry = {}

        epub_path = os.path.join(epub_dir, f"{story.filename_base}.epub")
        if os.path.exists(epub_path):
            try:
                with open(epub_path, 'rb') as f:
                    entry['epub'] = base64.b64encode(f.read()).decode('ascii')
                entry['epub_filename'] = f"{story.filename_base}.epub"
            except Exception as e:
                log_error(f"Bulk download: error reading epub for story {story.id}: {e}")

        html_path = os.path.join(html_dir, f"{story.filename_base}.json")
        if os.path.exists(html_path):
            try:
                with open(html_path, 'rb') as f:
                    entry['html'] = base64.b64encode(f.read()).decode('ascii')
                entry['html_filename'] = f"{story.filename_base}.json"
            except Exception as e:
                log_error(f"Bulk download: error reading html for story {story.id}: {e}")

        cover_filename = story.cover_filename or f"{story.filename_base}.jpg"
        cover_path = os.path.join(cover_dir, cover_filename)
        if os.path.exists(cover_path):
            try:
                with open(cover_path, 'rb') as f:
                    entry['cover'] = base64.b64encode(f.read()).decode('ascii')
                entry['cover_filename'] = cover_filename
            except Exception as e:
                log_error(f"Bulk download: error reading cover for story {story.id}: {e}")

        result[str(story.id)] = entry

    return jsonify({'stories': result})


# ---------------------------------------------------------------------------
# Highlights / saved quotes
# ---------------------------------------------------------------------------

def _serialize_highlight(h) -> dict:
    return {
        'id': h.id,
        'story_id': h.story_id,
        'story_title': h.story.title if h.story else None,
        'story_author': h.story.author.name if h.story and h.story.author else None,
        'filename_base': h.story.filename_base if h.story else None,
        'chapter_index': h.chapter_index,
        'paragraph_index': h.paragraph_index,
        'quote_text': h.quote_text,
        'note': h.note,
        'created_at': h.created_at.isoformat() if h.created_at else None,
    }


@api.route('/highlights', methods=['GET'])
def get_highlights() -> ResponseReturnValue:
    from app.models import Highlight, Story
    records = (Highlight.query
               .options(joinedload(Highlight.story).joinedload(Story.author))
               .order_by(Highlight.created_at.desc())
               .all())
    return jsonify({'highlights': [_serialize_highlight(h) for h in records]})


@api.route('/highlights', methods=['POST'])
def create_highlight() -> ResponseReturnValue:
    from app.models import Highlight, Story, db
    data = request.get_json(silent=True) or {}
    story_id = data.get('story_id')
    chapter_index = data.get('chapter_index')
    paragraph_index = data.get('paragraph_index')
    quote_text = data.get('quote_text', '').strip()

    if not story_id or chapter_index is None or paragraph_index is None or not quote_text:
        return jsonify({'error': 'story_id, chapter_index, paragraph_index, and quote_text are required'}), 400

    story = Story.query.get_or_404(story_id)

    highlight = Highlight(
        story_id=story.id,
        chapter_index=int(chapter_index),
        paragraph_index=int(paragraph_index),
        quote_text=quote_text,
        note=data.get('note'),
    )
    db.session.add(highlight)
    db.session.commit()

    return jsonify({'success': True, 'id': highlight.id}), 201


@api.route('/highlights/<int:highlight_id>', methods=['DELETE'])
def delete_highlight(highlight_id: int) -> ResponseReturnValue:
    from app.models import Highlight, db
    highlight = Highlight.query.get_or_404(highlight_id)
    db.session.delete(highlight)
    db.session.commit()
    return '', 204


