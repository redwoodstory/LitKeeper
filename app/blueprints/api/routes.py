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
    """Queue a story for background download (single URL or multi-URL combine)"""
    try:
        if request.is_json:
            data = request.get_json()
            url = data.get('url', '')
            extra_urls = data.get('extra_urls', data.get('urls', []))
        else:
            url = request.form.get('url', '')
            extra_urls = request.form.getlist('extra_urls') or request.form.getlist('urls')

        if extra_urls and not url:
            url = extra_urls[0]
            extra_urls = extra_urls[1:]

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

        is_multi = bool(extra_urls)

        if not is_multi:
            existing = DownloadQueueItem.query.filter(
                DownloadQueueItem.url == validated.url,
                DownloadQueueItem.status.in_(['pending', 'processing'])
            ).first()
            if existing:
                if request.headers.get('HX-Request'):
                    return render_template('partials/queue_status.html', queue_item=existing.to_dict())
                return jsonify({
                    "success": True,
                    "message": "Story is already queued or downloading",
                    "queue_item": existing.to_dict()
                })

        job_type = 'multi' if is_multi else 'single'
        queue_item = DownloadQueueItem(
            url=validated.url,
            status='pending',
            job_type=job_type,
        )
        queue_item.set_formats(validated.format)
        if is_multi:
            queue_item.set_extra_urls(list(extra_urls))
        db.session.add(queue_item)
        db.session.commit()
        current_app.download_worker.wake()

        log_action(f"Added story to download queue: {validated.url} job_type={job_type} (ID: {queue_item.id})")

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
            "success": False,
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
        current_app.download_worker.wake()

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
        return jsonify({"stories": stories})
    except Exception as e:
        log_error(f"Error fetching library: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"stories": []})

@api.route("/story/<int:story_id>/cover")
def get_story_cover(story_id: int) -> ResponseReturnValue:
    from app.models import Story
    from app.services import extract_cover_from_epub

    story = Story.query.get_or_404(story_id)
    cover_directory = get_cover_directory()
    filename = f"{story.id}_{story.filename_base}.jpg"

    if not validate_file_in_directory(cover_directory, filename):
        log_error(f"Path traversal blocked in cover for story {story_id}: {filename}")
        abort(403)

    cover_path = os.path.join(cover_directory, filename)
    os.makedirs(cover_directory, exist_ok=True)

    if os.path.exists(cover_path):
        return send_from_directory(cover_directory, filename, mimetype='image/jpeg')

    epub_path = os.path.join(get_epub_directory(), f"{story.id}_{story.filename_base}.epub")
    if os.path.exists(epub_path):
        try:
            if extract_cover_from_epub(epub_path, cover_path):
                return send_from_directory(cover_directory, filename, mimetype='image/jpeg')
        except Exception as e:
            log_error(f"Error extracting cover from EPUB for story {story_id}: {str(e)}")

    abort(404)

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

    # Try prefixed filename first, then legacy unprefixed
    json_path = os.path.join(html_directory, f"{sanitized_title}.json")
    epub_path = os.path.join(epub_directory, f"{sanitized_title}.epub")

    title = sanitized_title
    author = 'Unknown Author'

    from app.models import Story, db
    story_db = None
    if '_' in sanitized_title:
        try:
            story_id = int(sanitized_title.split('_')[0])
            story_db = db.session.get(Story, story_id)
        except (ValueError, IndexError):
            pass
    if not story_db:
        story_db = Story.query.filter_by(filename_base=sanitized_title).first()

    if story_db:
        title = story_db.title
        author = story_db.author.name if story_db.author else 'Unknown Author'

    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                story_data = json.load(f)
            title = story_data.get('title', sanitized_title)
            author = story_data.get('author', 'Unknown Author')
        except Exception as e:
            log_error(f"Error reading JSON metadata: {str(e)}")
    else:
        # Fallback to prefixed json path if story_db found
        if story_db:
            prefixed_json = os.path.join(html_directory, f"{story_db.id}_{story_db.filename_base}.json")
            if os.path.exists(prefixed_json):
                try:
                    with open(prefixed_json, 'r', encoding='utf-8') as f:
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
            except Exception as story_err:
                log_error(f"Error searching metadata for story {story.id}: {story_err}")
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
        'cover': f"{story.id}_{story.filename_base}.jpg",
        'formats': [fmt.format_type for fmt in story.formats],
        'filename_base': story.filename_base,
        'html_file': f"{story.id}_{story.filename_base}.html",
        'epub_file': os.path.basename(next((f.file_path for f in story.formats if f.format_type == 'epub'), '')) or None,
        'source_url': story.literotica_url,
        'series_url': story.literotica_series_url,
        'page_count': story.literotica_page_count,
        'word_count': story.word_count,
        'chapter_count': story.chapter_count,
        'size': next((f.file_size for f in story.formats if f.format_type == 'epub'), None),
        'created_at': story.created_at,
        'auto_update_enabled': story.auto_update_enabled,
        'is_series': bool(story.literotica_series_url and story.chapter_count > 1),
        'is_combined': bool(story.is_combined),
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
        
        story = db.session.get(Story, story_id)

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
        cover_filename = f"{story.id}_{story.filename_base}.jpg"
        current_category = story.category.name if story.category else None
        current_tags = [t.name for t in story.tags]

        epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
        json_fmt = next((f for f in story.formats if f.format_type == 'json'), None)

        if old_title != title or old_author != author_name:
            try:
                cover_directory = get_cover_directory()
                os.makedirs(cover_directory, exist_ok=True)

                cover_path = os.path.join(cover_directory, cover_filename)

                generate_cover_image(story.title, author_name or 'Unknown Author', cover_path, category=current_category)
                cover_regenerated = True
                log_action(f"Auto-regenerated cover for story: {story.title}")

                if epub_fmt and os.path.exists(epub_fmt.file_path):
                    if EpubService.update_epub_cover(epub_fmt.file_path, cover_path):
                        epub_updated = True
                        log_action(f"Updated EPUB cover for story: {story.title}")

                story.cover_filename = cover_filename
                db.session.commit()

            except Exception as cover_error:
                log_error(f"Error regenerating cover during metadata update: {str(cover_error)}")

        if json_fmt and os.path.exists(json_fmt.file_path):
            try:
                import json as _json
                with open(json_fmt.file_path, 'r', encoding='utf-8') as f:
                    story_data = _json.load(f)

                story_data['title'] = title
                story_data['author'] = author_name
                story_data['category'] = current_category
                story_data['tags'] = current_tags
                story_data['description'] = description if description else None

                tmp_path = json_fmt.file_path + '.tmp'
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    _json.dump(story_data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, json_fmt.file_path)

                json_fmt.json_data = _json.dumps(story_data, ensure_ascii=False)
                db.session.commit()
                log_action(f"Updated JSON file for story: {story.title}")
            except Exception as json_error:
                log_error(f"Error updating JSON file during metadata update: {str(json_error)}")

        if epub_fmt and os.path.exists(epub_fmt.file_path):
            try:
                if EpubService.update_epub_metadata(
                    epub_fmt.file_path,
                    title=title,
                    author=author_name or 'Unknown Author',
                    category=current_category,
                    tags=current_tags,
                    description=description if description else None,
                ):
                    epub_updated = True
                    log_action(f"Updated EPUB metadata for story: {story.title}")
            except Exception as epub_error:
                log_error(f"Error updating EPUB metadata: {str(epub_error)}")

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

    story = db.session.get(Story, story_id)
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

    story = db.session.get(Story, story_id)
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

    story = db.session.get(Story, story_id)
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


@api.route("/story/<int:story_id>/toggle-auto-update", methods=['POST'])
def toggle_auto_update(story_id: int) -> ResponseReturnValue:
    try:
        from app.models import Story, db

        story = db.session.get(Story, story_id)

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


@api.route("/story/<int:story_id>/toggle-exclusion", methods=['POST'])
def toggle_story_exclusion(story_id: int) -> ResponseReturnValue:
    """Toggle auto_refresh_excluded flag for a single story."""
    try:
        from app.models import Story, db

        story = db.session.get(Story, story_id)
        if not story:
            return jsonify({"success": False, "message": "Story not found"}), 404

        data = request.get_json(silent=True) or {}
        setting_excluded = data.get('excluded', not story.auto_refresh_excluded)

        if setting_excluded and not data.get('reason'):
            return jsonify({"success": False, "message": "A reason is required when excluding a story"}), 400

        story.auto_refresh_excluded = bool(setting_excluded)

        if story.auto_refresh_excluded:
            story.auto_refresh_exclusion_reason = data['reason']
            story.auto_refresh_exclusion_type = data.get('exclusion_type')
        else:
            story.auto_refresh_exclusion_reason = None
            story.auto_refresh_exclusion_type = None

        db.session.commit()

        log_action(f"Story {story_id} exclusion set to {story.auto_refresh_excluded}")
        return jsonify({
            "success": True,
            "excluded": story.auto_refresh_excluded,
            "story": story.to_library_dict()
        })
    except Exception as e:
        db.session.rollback()
        log_error(f"Error toggling exclusion: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

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
        'cover': f"{story.id}_{story.filename_base}.jpg",
        'formats': [fmt.format_type for fmt in story.formats],
        'filename_base': story.filename_base,
        'html_file': f"{story.id}_{story.filename_base}.html",
        'epub_file': os.path.basename(next((f.file_path for f in story.formats if f.format_type == 'epub'), '')) or None,
        'source_url': story.literotica_url,
        'series_url': story.literotica_series_url,
        'page_count': story.literotica_page_count,
        'word_count': story.word_count,
        'chapter_count': story.chapter_count,
        'size': next((f.file_size for f in story.formats if f.format_type == 'epub'), None),
        'created_at': story.created_at,
        'auto_update_enabled': story.auto_update_enabled,
        'is_series': bool(story.literotica_series_url and story.chapter_count > 1),
        'is_combined': bool(story.is_combined),
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
        
        cover_filename = f"{story.id}_{story.filename_base}.jpg"
        cover_path = os.path.join(cover_directory, cover_filename)
        
        author_name = story.author.name if story.author else 'Unknown Author'
        category_name = story.category.name if story.category else None
        generate_cover_image(story.title, author_name, cover_path, category=category_name)
        log_action(f"Regenerated cover for story: {story.title}")
        
        epub_updated = False
        epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
        if epub_fmt and os.path.exists(epub_fmt.file_path):
            if EpubService.update_epub_cover(epub_fmt.file_path, cover_path):
                epub_updated = True
                log_action(f"Updated EPUB cover for story: {story.title}")
            else:
                log_error(f"Failed to update EPUB cover for story: {story.title}")
        
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

        epub_fmt = next((f for f in story.formats if f.format_type == 'epub'), None)
        if epub_fmt and os.path.exists(epub_fmt.file_path):
            try:
                with open(epub_fmt.file_path, 'rb') as f:
                    entry['epub'] = base64.b64encode(f.read()).decode('ascii')
                entry['epub_filename'] = os.path.basename(epub_fmt.file_path)
            except Exception as e:
                log_error(f"Bulk download: error reading epub for story {story.id}: {e}")

        json_fmt = next((f for f in story.formats if f.format_type == 'json'), None)
        if json_fmt and os.path.exists(json_fmt.file_path):
            try:
                with open(json_fmt.file_path, 'rb') as f:
                    entry['html'] = base64.b64encode(f.read()).decode('ascii')
                entry['html_filename'] = os.path.basename(json_fmt.file_path)
            except Exception as e:
                log_error(f"Bulk download: error reading html for story {story.id}: {e}")

        cover_filename = f"{story.id}_{story.filename_base}.jpg"
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


@api.route('/queue/author', methods=['POST'])
def queue_author_download() -> ResponseReturnValue:
    """Queue an author URL scan to download all of their stories."""
    try:
        data = request.get_json() or {}
        author_url = (data.get('author_url') or '').strip()

        if not author_url:
            return jsonify({"success": False, "message": "author_url is required"}), 400

        from app.services.author_scraper import is_author_url, normalize_author_url
        if not is_author_url(author_url):
            return jsonify({"success": False, "message": "URL does not appear to be a Literotica author page"}), 400

        canonical = normalize_author_url(author_url) or author_url

        from app.models import DownloadQueueItem, Author, db

        existing = DownloadQueueItem.query.filter(
            DownloadQueueItem.url == canonical,
            DownloadQueueItem.status.in_(['pending', 'processing'])
        ).first()
        if existing:
            return jsonify({
                "success": True,
                "message": "Author scan already queued",
                "queue_item": existing.to_dict()
            })

        author_obj = Author.query.filter_by(literotica_url=canonical).first()
        author_name = author_obj.name if author_obj else canonical.rstrip('/').split('/')[-1]

        queue_item = DownloadQueueItem(
            url=canonical,
            formats=json.dumps(['epub', 'html']),
            status='pending',
            job_type='author',
            author=author_name,
            title=f'Author scan: {author_name}',
        )
        db.session.add(queue_item)

        if not author_obj:
            author_obj = Author(
                name=canonical.rstrip('/').split('/')[-1],
                literotica_url=canonical,
                watch_enabled=True,
            )
            db.session.add(author_obj)

        db.session.commit()
        current_app.download_worker.wake()
        log_action(f"Queued author scan: {canonical}")

        return jsonify({
            "success": True,
            "message": "Author scan queued",
            "queue_item": queue_item.to_dict()
        })

    except Exception as e:
        log_error(f"Error queuing author download: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/authors/preview', methods=['POST'])
def preview_author_stories() -> ResponseReturnValue:
    """Synchronously scrape an author page and return story list with metadata. No DB writes."""
    try:
        data = request.get_json() or {}
        author_url = (data.get('author_url') or '').strip()

        if not author_url:
            return jsonify({"success": False, "message": "author_url is required"}), 400

        from app.services.author_scraper import is_author_url, normalize_author_url, AuthorScraper
        if not is_author_url(author_url):
            return jsonify({"success": False, "message": "URL does not appear to be a Literotica author page"}), 400

        canonical = normalize_author_url(author_url) or author_url
        author_name = canonical.rstrip('/').split('/')[-1]

        scraper = AuthorScraper()
        stories = scraper.scrape_story_list_with_metadata(canonical, skip_jitter=True)

        if not stories:
            return jsonify({"success": False, "message": "No stories found for this author. The page may have changed or the author has no public submissions."}), 404

        return jsonify({
            "success": True,
            "author_name": author_name,
            "author_url": canonical,
            "stories": stories,
        })

    except Exception as e:
        log_error(f"Error previewing author stories: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Failed to fetch author page. Please try again."}), 500


@api.route('/authors/queue-stories', methods=['POST'])
def queue_author_stories() -> ResponseReturnValue:
    """Queue selected stories from an author preview and optionally enable author watching."""
    try:
        data = request.get_json() or {}
        author_url = (data.get('author_url') or '').strip()
        story_urls = data.get('story_urls') or []
        watch = bool(data.get('watch', False))

        if not author_url:
            return jsonify({"success": False, "message": "author_url is required"}), 400
        if not story_urls:
            return jsonify({"success": False, "message": "No story URLs provided"}), 400

        from app.services.author_scraper import is_author_url, normalize_author_url
        if not is_author_url(author_url):
            return jsonify({"success": False, "message": "Invalid author URL"}), 400

        canonical = normalize_author_url(author_url) or author_url

        from app.models import DownloadQueueItem, Author, SeenLiteroticaUrl, db

        author_obj = Author.query.filter_by(literotica_url=canonical).first()
        if not author_obj:
            author_name = canonical.rstrip('/').split('/')[-1]
            author_obj = Author(
                name=author_name,
                literotica_url=canonical,
                watch_enabled=watch,
            )
            db.session.add(author_obj)
        else:
            author_obj.watch_enabled = watch

        # Update known_story_urls with all submitted URLs (the full author story list)
        all_known = list(set(author_obj.get_known_story_urls() + story_urls))
        author_obj.set_known_story_urls(all_known)

        from datetime import datetime
        author_obj.last_watch_check_at = datetime.utcnow()
        db.session.flush()

        enqueued = 0
        skipped = 0

        for story_url in story_urls:
            active = DownloadQueueItem.query.filter(
                DownloadQueueItem.url == story_url,
                DownloadQueueItem.status.in_(['pending', 'processing', 'rate_limited'])
            ).first()
            if active:
                skipped += 1
                continue

            if SeenLiteroticaUrl.query.filter_by(url=story_url).first():
                skipped += 1
                continue

            child = DownloadQueueItem(
                url=story_url,
                formats=json.dumps(['epub', 'html']),
                status='pending',
                job_type='single',
                author=author_obj.name,
                progress_message='Queued from author preview',
            )
            db.session.add(child)
            enqueued += 1

        db.session.commit()
        if enqueued:
            current_app.download_worker.wake()

        log_action(f"[AuthorPreview] Queued {enqueued} stories for {canonical} (skipped {skipped}, watch={watch})")

        parts = [f"Queued {enqueued} {'story' if enqueued == 1 else 'stories'}"]
        if skipped:
            parts.append(f"{skipped} already queued or downloaded")
        if watch:
            parts.append("author added to watch list")

        return jsonify({
            "success": True,
            "queued": enqueued,
            "skipped": skipped,
            "message": " — ".join(parts),
        })

    except Exception as e:
        log_error(f"Error queuing author stories: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/authors', methods=['GET'])
def list_authors() -> ResponseReturnValue:
    """List all authors that have a Literotica URL (watchable authors)."""
    try:
        from app.models import Author
        authors = Author.query.filter(Author.literotica_url.isnot(None)).order_by(Author.name).all()
        return jsonify({"success": True, "authors": [a.to_dict() for a in authors]})
    except Exception as e:
        log_error(f"Error listing authors: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/authors/<int:author_id>/toggle-watch', methods=['POST'])
def toggle_author_watch(author_id: int) -> ResponseReturnValue:
    """Toggle watch_enabled for an author."""
    try:
        from app.models import Author, db
        author = db.session.get(Author, author_id)
        if not author:
            return jsonify({"success": False, "message": "Author not found"}), 404

        author.watch_enabled = not author.watch_enabled
        db.session.commit()
        log_action(f"Author '{author.name}' watch {'enabled' if author.watch_enabled else 'disabled'}")
        return jsonify({
            "success": True,
            "watch_enabled": author.watch_enabled,
            "message": f"Watch {'enabled' if author.watch_enabled else 'disabled'} for {author.name}"
        })
    except Exception as e:
        log_error(f"Error toggling author watch: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/authors/<int:author_id>/rescan', methods=['POST'])
def rescan_author(author_id: int) -> ResponseReturnValue:
    """Queue a manual re-scan of an author's story list."""
    try:
        from app.models import Author, DownloadQueueItem, db
        import json as _json
        author = db.session.get(Author, author_id)
        if not author or not author.literotica_url:
            return jsonify({"success": False, "message": "Author not found"}), 404

        existing = DownloadQueueItem.query.filter(
            DownloadQueueItem.url == author.literotica_url,
            DownloadQueueItem.status.in_(['pending', 'processing'])
        ).first()
        if existing:
            return jsonify({"success": True, "message": "Scan already queued"})

        queue_item = DownloadQueueItem(
            url=author.literotica_url,
            formats=_json.dumps(['epub', 'html']),
            status='pending',
            job_type='author',
            author=author.name,
            title=f'Author scan: {author.name}',
        )
        db.session.add(queue_item)
        db.session.commit()
        current_app.download_worker.wake()
        log_action(f"Manual rescan queued for author '{author.name}'")
        return jsonify({"success": True, "message": f"Rescan queued for {author.name}"})
    except Exception as e:
        log_error(f"Error queuing author rescan: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/settings/auto-update-enabled', methods=['GET'])
def api_get_auto_update_enabled() -> ResponseReturnValue:
    """Get the auto-update-stories server setting."""
    try:
        from app.models import AppConfig
        cfg = AppConfig.query.filter_by(key='auto_update_enabled').first()
        enabled = cfg.get_value() if cfg else False
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        log_error(f"Error getting auto-update setting: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/settings/toggle-auto-update', methods=['POST'])
def api_toggle_auto_update() -> ResponseReturnValue:
    """Set the auto-update-stories server setting."""
    try:
        from app.models import AppConfig, db
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))
        cfg = AppConfig.query.filter_by(key='auto_update_enabled').first()
        if cfg:
            cfg.set_value(enabled)
        else:
            cfg = AppConfig(key='auto_update_enabled',
                            value='true' if enabled else 'false',
                            value_type='bool',
                            description='Global setting to enable/disable automatic story updates')
            db.session.add(cfg)
        db.session.commit()
        log_action(f"Auto-update setting changed to: {enabled}")
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error toggling auto-update: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/settings/auto-watch-enabled', methods=['GET'])
def api_get_auto_watch_enabled() -> ResponseReturnValue:
    """Get the auto-download-from-watched-authors server setting."""
    try:
        from app.models import AppConfig
        cfg = AppConfig.query.filter_by(key='auto_watch_authors_enabled').first()
        enabled = cfg.get_value() if cfg else False
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        log_error(f"Error getting auto-watch setting: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/settings/toggle-auto-watch', methods=['POST'])
def api_toggle_auto_watch() -> ResponseReturnValue:
    """Set the auto-download-from-watched-authors server setting."""
    try:
        from app.models import AppConfig, db
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))
        cfg = AppConfig.query.filter_by(key='auto_watch_authors_enabled').first()
        if cfg:
            cfg.set_value(enabled)
        else:
            cfg = AppConfig(key='auto_watch_authors_enabled',
                            value='true' if enabled else 'false',
                            value_type='bool',
                            description='Auto-download new stories from watched authors on schedule')
            db.session.add(cfg)
        db.session.commit()
        log_action(f"Auto-watch-authors setting changed to: {enabled}")
        return jsonify({"success": True, "enabled": enabled})
    except Exception as e:
        db.session.rollback()
        log_error(f"Error toggling auto-watch: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/stories/excluded', methods=['GET'])
def get_excluded_stories() -> ResponseReturnValue:
    """List all stories that have been excluded from auto-refresh."""
    try:
        from app.models import Story

        stories = Story.query.filter(Story.auto_refresh_excluded == True).all()

        return jsonify({
            "success": True,
            "count": len(stories),
            "stories": [story.to_library_dict() for story in stories]
        })
    except Exception as e:
        log_error(f"Error fetching excluded stories: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@api.route('/stories/excluded/reset', methods=['POST'])
def reset_all_exclusions() -> ResponseReturnValue:
    """Clear auto_refresh_excluded flags on all stories so automation can re-check them."""
    try:
        from app.models import Story, db

        stories = Story.query.filter(Story.auto_refresh_excluded == True).all()
        count = len(stories)

        for story in stories:
            story.auto_refresh_excluded = False
            story.auto_refresh_exclusion_reason = None
            story.auto_refresh_exclusion_type = None

        db.session.commit()
        log_action(f"Reset {count} auto-refresh exclusions")

        return jsonify({
            "success": True,
            "message": f"Reset {count} exclusion(s)",
            "count": count
        })
    except Exception as e:
        db.session.rollback()
        log_error(f"Error resetting exclusions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


