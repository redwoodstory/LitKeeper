from __future__ import annotations
import json
import os
import traceback
from typing import Optional
from app.models import Story, StoryFormat
from app.models.base import db
from app.utils import get_epub_directory, get_html_directory
from .story_downloader import download_story, extract_chapter_titles, CHAPTER_SENTINEL
from .epub_generator import create_epub_file
from .html_generator import create_html_file
from .logger import log_action, log_error


class FormatGeneratorService:
    def generate_html_with_metadata(self, story_id: int, url: str, method: str = "manual") -> dict:
        """
        Generate HTML/JSON format from Literotica URL and update metadata in one operation.
        This avoids the double scraping issue by doing both in a single download_story call.
        """
        try:
            from app.models import Category, Tag
            from datetime import datetime
            
            story = Story.query.get(story_id)
            if not story:
                return {
                    "success": False,
                    "message": "Story not found"
                }

            json_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='json'
            ).first()

            if json_format:
                return {
                    "success": False,
                    "message": "HTML/JSON format already exists for this story"
                }

            epub_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='epub'
            ).first()

            if not epub_format:
                return {
                    "success": False,
                    "message": "No EPUB format found for this story"
                }

            log_action(f"Generating HTML/JSON and updating metadata for story: {story.title}")

            story_content, _, _, story_category, story_tags, story_author_url, story_pages, _, story_description = download_story(url)

            if not story_content:
                return {
                    "success": False,
                    "message": "Failed to download story content from Literotica"
                }

            fields_changed = []
            
            if story.literotica_url != url:
                story.literotica_url = url
                fields_changed.append('literotica_url')
            
            if story_pages and story.literotica_page_count != story_pages:
                story.literotica_page_count = story_pages
                fields_changed.append('page_count')
            
            if story_category:
                category = Category.query.filter_by(name=story_category).first()
                if not category:
                    slug = Category.create_slug(story_category)
                    category = Category.query.filter_by(slug=slug).first()
                    if not category:
                        category = Category(name=story_category)
                        db.session.add(category)
                        db.session.flush()
                
                if story.category_id != category.id:
                    story.category_id = category.id
                    fields_changed.append('category')
            
            if story_tags:
                existing_tag_names = {tag.name for tag in story.tags}
                new_tag_names = set(story_tags)
                
                if existing_tag_names != new_tag_names:
                    tags_to_add = []
                    for tag_name in new_tag_names:
                        tag = Tag.query.filter_by(name=tag_name).first()
                        if not tag:
                            slug = Tag.create_slug(tag_name)
                            tag = Tag.query.filter_by(slug=slug).first()
                            if not tag:
                                tag = Tag(name=tag_name)
                                db.session.add(tag)
                                db.session.flush()
                        tags_to_add.append(tag)
                    
                    story.tags = tags_to_add
                    fields_changed.append('tags')
            
            if story_author_url and story.author:
                if story.author.literotica_url != story_author_url:
                    story.author.literotica_url = story_author_url
                    fields_changed.append('author_url')

            if story_description and story.description != story_description:
                story.description = story_description
                fields_changed.append('description')

            story.last_metadata_refresh = datetime.utcnow()
            story.metadata_refresh_status = 'success'

            chapter_titles = extract_chapter_titles(story_content)

            json_path = create_html_file(
                story_title=story.title,
                story_author=story.author.name,
                story_content=story_content,
                output_directory=get_html_directory(),
                story_category=story_category,
                story_tags=story_tags,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=url,
                author_url=story_author_url,
                page_count=story_pages,
                filename_base=f"{story.id}_{story.filename_base}",
                story_description=story_description
            )

            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            existing_json = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
            if existing_json:
                existing_json.file_path = json_path
                existing_json.file_size = os.path.getsize(json_path)
                existing_json.json_data = json.dumps(json_data)
            else:
                db.session.add(StoryFormat(
                    story_id=story.id,
                    format_type='json',
                    file_path=json_path,
                    file_size=os.path.getsize(json_path),
                    json_data=json.dumps(json_data)
                ))
            db.session.commit()

            log_action(f"Successfully generated HTML/JSON and updated metadata for story: {story.title}")

            return {
                "success": True,
                "message": f"HTML format generated and metadata updated for '{story.title}'",
                "fields_changed": fields_changed
            }

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error generating HTML format with metadata: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return {
                "success": False,
                "message": "An error occurred while generating HTML format"
            }

    def generate_epub_from_json(self, story_id: int) -> dict:
        """
        Generate EPUB format from existing JSON data stored in the database.
        """
        try:
            story = Story.query.get(story_id)
            if not story:
                return {
                    "success": False,
                    "message": "Story not found"
                }

            json_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='json'
            ).first()

            if not json_format:
                return {
                    "success": False,
                    "message": "No JSON format found for this story"
                }

            epub_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='epub'
            ).first()

            if epub_format:
                return {
                    "success": False,
                    "message": "EPUB format already exists for this story"
                }

            if not json_format.json_data:
                return {
                    "success": False,
                    "message": "JSON data is empty, cannot generate EPUB"
                }

            log_action(f"Generating EPUB from JSON for story: {story.title}")

            story_data = json.loads(json_format.json_data)

            chapters = story_data.get('chapters', [])
            story_content_parts = []

            for chapter in chapters:
                num = chapter.get('number', len(story_content_parts) + 1)
                raw_title = chapter.get('title', f"Part {num}")
                # Legacy JSON stored "Chapter N: Title" — strip the prefix for bare title
                import re as _re
                bare_title = _re.sub(r'^Chapter \d+:\s*', '', raw_title)
                paragraphs = chapter.get('paragraphs', [])
                chapter_content = '\n\n'.join(paragraphs)
                story_content_parts.append(f"{CHAPTER_SENTINEL}CHAPTER:{num}{CHAPTER_SENTINEL}{bare_title}\n\n{chapter_content}")

            story_content = ''.join(story_content_parts)

            epub_path = create_epub_file(
                story_title=story.title,
                story_author=story.author.name,
                story_content=story_content,
                output_directory=get_epub_directory(),
                story_category=story.category.name if story.category else None,
                story_tags=[tag.name for tag in story.tags],
                story_description=story.description,
                filename_base=f"{story.id}_{story.filename_base}",
            )

            existing_epub = StoryFormat.query.filter_by(story_id=story.id, format_type='epub').first()
            if existing_epub:
                existing_epub.file_path = epub_path
                existing_epub.file_size = os.path.getsize(epub_path)
            else:
                db.session.add(StoryFormat(
                    story_id=story.id,
                    format_type='epub',
                    file_path=epub_path,
                    file_size=os.path.getsize(epub_path)
                ))
            db.session.commit()

            log_action(f"Successfully generated EPUB for story: {story.title}")

            return {
                "success": True,
                "message": f"EPUB format generated successfully for '{story.title}'"
            }

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error generating EPUB format: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return {
                "success": False,
                "message": "An error occurred while generating EPUB format"
            }

    def generate_html_from_url(self, story_id: int) -> dict:
        """
        Generate HTML/JSON format from Literotica URL.
        Returns needs_url=True if story doesn't have a source URL.
        """
        try:
            story = Story.query.get(story_id)
            if not story:
                return {
                    "success": False,
                    "message": "Story not found"
                }

            json_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='json'
            ).first()

            if json_format:
                return {
                    "success": False,
                    "message": "HTML/JSON format already exists for this story"
                }

            epub_format = StoryFormat.query.filter_by(
                story_id=story_id,
                format_type='epub'
            ).first()

            if not epub_format:
                return {
                    "success": False,
                    "message": "No EPUB format found for this story"
                }

            if not story.literotica_url:
                return {
                    "success": False,
                    "needs_url": True,
                    "message": "Story requires Literotica URL"
                }

            log_action(f"Generating HTML/JSON from Literotica for story: {story.title}")

            story_content, _, _, story_category, story_tags, story_author_url, story_pages, _, story_description = download_story(story.literotica_url)

            if not story_content:
                return {
                    "success": False,
                    "message": "Failed to download story content from Literotica"
                }

            if story_description and story.description != story_description:
                story.description = story_description

            chapter_titles = extract_chapter_titles(story_content)

            json_path = create_html_file(
                story_title=story.title,
                story_author=story.author.name,
                story_content=story_content,
                output_directory=get_html_directory(),
                story_category=story_category,
                story_tags=story_tags,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=story.literotica_url,
                author_url=story_author_url,
                page_count=story_pages,
                filename_base=f"{story.id}_{story.filename_base}",
                story_description=story_description
            )

            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            existing_json = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
            if existing_json:
                existing_json.file_path = json_path
                existing_json.file_size = os.path.getsize(json_path)
                existing_json.json_data = json.dumps(json_data)
            else:
                db.session.add(StoryFormat(
                    story_id=story.id,
                    format_type='json',
                    file_path=json_path,
                    file_size=os.path.getsize(json_path),
                    json_data=json.dumps(json_data)
                ))
            db.session.commit()

            log_action(f"Successfully generated HTML/JSON for story: {story.title}")

            return {
                "success": True,
                "message": f"HTML format generated successfully for '{story.title}'"
            }

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error generating HTML format: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return {
                "success": False,
                "message": "An error occurred while generating HTML format"
            }

    def generate_json_from_epub(self, story_id: int) -> dict:
        """
        Extract story content from an existing local EPUB and write a JSON format file.
        No network access required — all content is embedded in the EPUB.
        """
        import xml.etree.ElementTree as ET
        from html import unescape
        import ebooklib
        from ebooklib import epub as ebooklib_epub
        from app.utils import story_json_path
        from app.services.story_processor import link_story_formats

        _XHTML_NS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        _SKIP_IDS = {'nav', 'cover', 'metadata', 'intro', 'toc'}

        try:
            story = Story.query.get(story_id)
            if not story:
                return {"success": False, "message": "Story not found"}

            epub_fmt = StoryFormat.query.filter_by(story_id=story_id, format_type='epub').first()
            if not epub_fmt or not os.path.exists(epub_fmt.file_path):
                return {"success": False, "message": "No EPUB file found for this story"}

            json_fmt = StoryFormat.query.filter_by(story_id=story_id, format_type='json').first()
            if json_fmt and os.path.exists(json_fmt.file_path):
                return {"success": False, "message": "JSON format already exists for this story"}

            log_action(f"Extracting JSON from EPUB for story: {story.title}")

            book = ebooklib_epub.read_epub(epub_fmt.file_path, options={'ignore_ncx': True})

            # Extract Dublin Core metadata
            raw_title = book.get_metadata('DC', 'title')
            title = raw_title[0][0] if raw_title else story.title

            raw_author = book.get_metadata('DC', 'creator')
            author_name = raw_author[0][0] if raw_author else (story.author.name if story.author else '')

            raw_subjects = book.get_metadata('DC', 'subject')
            subjects = [s[0] for s in raw_subjects] if raw_subjects else []
            category = subjects[0] if subjects else None
            tags = subjects[1:] if len(subjects) > 1 else []

            raw_desc = book.get_metadata('DC', 'description')
            description = raw_desc[0][0] if raw_desc else story.description

            # Extract chapters from spine in order
            chapters = []
            chapter_num = 0

            spine_ids = [item_id for item_id, _ in book.spine]
            for item_id in spine_ids:
                item = book.get_item_with_id(item_id)
                if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue
                # Skip non-content pages by ID or filename
                item_name = (item.get_name() or '').lower()
                if item.id in _SKIP_IDS or any(skip in item_name for skip in _SKIP_IDS):
                    continue

                try:
                    content = item.get_content().decode('utf-8', errors='replace')
                    root = ET.fromstring(content)
                    body = root.find('xhtml:body', _XHTML_NS)
                    if body is None:
                        body = root.find('body')
                    if body is None:
                        continue

                    h1 = body.find('xhtml:h1', _XHTML_NS) or body.find('h1')
                    chapter_title = unescape(h1.text or '').strip() if h1 is not None else f"Chapter {chapter_num + 1}"

                    paragraphs = []
                    for tag in ('xhtml:p', 'p'):
                        found = body.findall(tag, _XHTML_NS) if ':' in tag else body.findall(tag)
                        for p in found:
                            text = unescape(''.join(p.itertext())).strip()
                            if text:
                                paragraphs.append(text)
                        if paragraphs:
                            break

                    if not paragraphs:
                        continue

                    chapter_num += 1
                    chapters.append({
                        'number': chapter_num,
                        'title': chapter_title,
                        'paragraphs': paragraphs,
                    })
                except ET.ParseError:
                    continue

            if not chapters:
                return {"success": False, "message": "Could not extract any chapters from EPUB"}

            word_count = sum(
                len(p.split()) for ch in chapters for p in ch['paragraphs']
            )

            story_data = {
                'title': title,
                'author': author_name,
                'author_url': story.author.literotica_url if story.author else None,
                'source_url': story.literotica_url,
                'category': category,
                'tags': tags,
                'description': description,
                'word_count': word_count,
                'chapter_count': len(chapters),
                'cover': f"{story.id}_{story.filename_base}.jpg",
                'chapters': chapters,
            }

            out_path = story_json_path(story.id, story.filename_base)
            tmp_path = out_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(story_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, out_path)

            link_story_formats(story)

            log_action(f"Successfully extracted JSON from EPUB for story: {story.title}")
            return {"success": True, "message": f"JSON format extracted from EPUB for '{story.title}'"}

        except Exception as e:
            db.session.rollback()
            log_error(f"Error extracting JSON from EPUB: {str(e)}\n{traceback.format_exc()}")
            return {"success": False, "message": "An error occurred while extracting JSON from EPUB"}
