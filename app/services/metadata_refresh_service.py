from __future__ import annotations
from typing import Optional
from datetime import datetime
from app.models import db, Story, Category, Tag, MetadataRefreshLog, Author
from app.services.metadata_refresh import LiteroticaSearcher, StoryMatcher, LiteroticaSearchResult
import json


class MetadataRefreshService:
    def __init__(self):
        self.searcher = LiteroticaSearcher()
        self.matcher = StoryMatcher()
    
    def search_for_story(self, story_id: int) -> dict:
        story = db.session.get(Story, story_id)
        if not story:
            return {"success": False, "message": "Story not found"}
        
        if story.literotica_url:
            return {"success": False, "message": "Story already has a Literotica URL"}
        
        search_results = self.searcher.search_story(story.title, story.author.name)
        
        if not search_results:
            self._log_refresh(story.id, "no_match", None, None, "No search results found")
            return {
                "success": False,
                "message": "No matches found on Literotica",
                "results": []
            }
        
        best_match = self.matcher.find_best_match(story.title, story.author.name, search_results)
        ranked_results = self.matcher.rank_results(story.title, story.author.name, search_results)
        
        return {
            "success": True,
            "story_id": story.id,
            "story_title": story.title,
            "story_author": story.author.name,
            "auto_match": best_match is not None,
            "best_match": {
                "title": best_match.title,
                "author": best_match.author,
                "url": best_match.url,
                "category": best_match.category,
                "confidence": ranked_results[0][1] if ranked_results else 0.0
            } if best_match else None,
            "results": [
                {
                    "title": result.title,
                    "author": result.author,
                    "url": result.url,
                    "category": result.category,
                    "confidence": confidence
                }
                for result, confidence in ranked_results
            ]
        }
    
    def refresh_metadata_from_url(self, story_id: int, url: str, method: str = "manual") -> dict:
        story = db.session.get(Story, story_id)
        if not story:
            return {"success": False, "message": "Story not found"}
        
        metadata = self.searcher.fetch_metadata_from_url(url)
        
        if not metadata:
            self._log_refresh(story.id, "failed", url, None, "Failed to fetch metadata from URL")
            return {"success": False, "message": "Failed to fetch metadata from URL"}
        
        # Extract story content before using metadata (not stored in DB)
        story_content = metadata.pop("_story_content", None)
        
        fields_changed = []
        previous_data = {}
        
        existing_story = Story.query.filter_by(literotica_url=url).first()
        if existing_story and existing_story.id != story.id:
            error_msg = f"Duplicate story detected: URL already assigned to '{existing_story.title}'"
            
            story.auto_refresh_excluded = True
            story.auto_refresh_exclusion_reason = error_msg
            story.auto_refresh_exclusion_type = 'duplicate'
            db.session.commit()
            
            self._log_refresh(story.id, "failed", url, None, error_msg)
            return {"success": False, "message": error_msg, "duplicate_detected": True}
        
        if story.literotica_url != url:
            previous_data['literotica_url'] = story.literotica_url
            story.literotica_url = url
            fields_changed.append('literotica_url')
        
        if metadata.get('page_count') and story.literotica_page_count != metadata['page_count']:
            previous_data['page_count'] = story.literotica_page_count
            story.literotica_page_count = metadata['page_count']
            fields_changed.append('page_count')
        
        if metadata.get('category'):
            category = Category.query.filter_by(name=metadata['category']).first()
            if not category:
                slug = Category.create_slug(metadata['category'])
                category = Category.query.filter_by(slug=slug).first()
                if not category:
                    category = Category(name=metadata['category'])
                    db.session.add(category)
                    db.session.flush()
            
            if story.category_id != category.id:
                previous_data['category'] = story.category.name if story.category else None
                story.category_id = category.id
                fields_changed.append('category')
        
        if metadata.get('tags'):
            existing_tag_names = {tag.name for tag in story.tags}
            new_tag_names = set(metadata['tags'])
            
            if existing_tag_names != new_tag_names:
                previous_data['tags'] = list(existing_tag_names)
                
                tags_to_remove = [tag for tag in story.tags if tag.name not in new_tag_names]
                for tag in tags_to_remove:
                    if tag in story.tags:
                        story.tags.remove(tag)
                
                tags_to_add_names = new_tag_names - existing_tag_names
                for tag_name in tags_to_add_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        slug = Tag.create_slug(tag_name)
                        tag = Tag.query.filter_by(slug=slug).first()
                        if not tag:
                            tag = Tag(name=tag_name)
                            db.session.add(tag)
                            db.session.flush()
                    if tag not in story.tags:
                        story.tags.append(tag)
                
                fields_changed.append('tags')
        
        if metadata.get('author_url') and story.author:
            if story.author.literotica_url != metadata['author_url']:
                story.author.literotica_url = metadata['author_url']
                fields_changed.append('author_url')

        if metadata.get('series_url') and story.literotica_series_url != metadata['series_url']:
            previous_data['series_url'] = story.literotica_series_url
            story.literotica_series_url = metadata['series_url']
            fields_changed.append('series_url')

        story.last_metadata_refresh = datetime.utcnow()
        story.metadata_refresh_status = 'success'
        
        if story.auto_refresh_excluded:
            story.auto_refresh_excluded = False
            story.auto_refresh_exclusion_reason = None
            story.auto_refresh_exclusion_type = None
        
        confidence = None
        if method == "auto":
            search_results = self.searcher.search_story(story.title, story.author.name)
            for result in search_results:
                if result.url == url:
                    confidence = self.matcher.calculate_match_confidence(
                        story.title, story.author.name, result
                    )
                    break
        
        self._log_refresh(
            story.id,
            "success",
            url,
            confidence,
            None,
            fields_changed,
            previous_data
        )

        # Generate HTML/JSON file from the already-downloaded content (no extra network cost)
        if story_content and story.filename_base:
            from app.models import StoryFormat
            from app.utils import get_html_directory
            from .html_generator import create_html_file
            from .story_downloader import extract_chapter_titles
            import os, json as _json

            existing_json = StoryFormat.query.filter_by(
                story_id=story.id, format_type='json'
            ).first()

            if not existing_json:
                try:
                    from app.services.logger import log_action as _log_action, log_error as _log_error
                    _log_action(f"Generating HTML/JSON for story: {story.title}")
                    chapter_titles = extract_chapter_titles(story_content)
                    json_path = create_html_file(
                        story_title=story.title,
                        story_author=story.author.name,
                        story_content=story_content,
                        output_directory=get_html_directory(),
                        story_category=metadata.get('category'),
                        story_tags=metadata.get('tags'),
                        chapter_titles=chapter_titles if chapter_titles else None,
                        source_url=url,
                        author_url=metadata.get('author_url'),
                        page_count=metadata.get('page_count'),
                        filename_base=story.filename_base,
                    )
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_data = _json.load(f)
                    json_format = StoryFormat(
                        story_id=story.id,
                        format_type='json',
                        file_path=json_path,
                        file_size=os.path.getsize(json_path),
                        json_data=_json.dumps(json_data),
                    )
                    db.session.add(json_format)
                    fields_changed.append('html_generated')
                    _log_action(f"Successfully generated HTML/JSON for story: {story.title}")
                except Exception as html_err:
                    from app.services.logger import log_error as _log_error
                    _log_error(f"HTML generation failed for story {story.id}: {html_err}")

        db.session.commit()
        
        return {
            "success": True,
            "message": "Metadata refreshed successfully",
            "fields_changed": fields_changed,
            "story": story.to_library_dict()
        }
    
    def _log_refresh(
        self,
        story_id: int,
        status: str,
        matched_url: Optional[str],
        confidence: Optional[float],
        error_message: Optional[str],
        fields_changed: Optional[list] = None,
        previous_data: Optional[dict] = None
    ) -> None:
        story = db.session.get(Story, story_id)
        search_query = f"{story.title} {story.author.name}" if story else None
        
        log_entry = MetadataRefreshLog(
            story_id=story_id,
            search_query=search_query,
            status=status,
            matched_url=matched_url,
            match_confidence=confidence,
            metadata_updated=status == "success",
            fields_changed=json.dumps({"changed": fields_changed or [], "previous": previous_data or {}}),
            error_message=error_message
        )
        
        db.session.add(log_entry)
        db.session.commit()
