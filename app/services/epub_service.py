from __future__ import annotations
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Any
from ebooklib import epub
from flask import current_app
from app.models import Story, ReadingProgress, Bookmark, Highlight
from app.models.base import db
from datetime import datetime

class EpubService:
    
    @staticmethod
    def get_epub_path(story: Story) -> Optional[str]:
        """Get the full path to the EPUB file for a story."""
        epub_format = next((f for f in story.formats if f.format_type == 'epub'), None)
        if not epub_format:
            return None
        
        epub_dir = os.path.join(current_app.root_path, 'data', 'epubs')
        epub_path = os.path.join(epub_dir, f"{story.filename_base}.epub")
        
        if os.path.exists(epub_path):
            return epub_path
        return None
    
    @staticmethod
    def parse_epub_metadata(story: Story) -> Optional[Dict[str, Any]]:
        """Parse EPUB file and extract metadata for the reader."""
        epub_path = EpubService.get_epub_path(story)
        if not epub_path:
            return None
        
        try:
            book = epub.read_epub(epub_path)
            
            metadata = {
                'title': story.title,
                'author': story.author.name if story.author else 'Unknown',
                'identifier': book.get_metadata('DC', 'identifier'),
                'language': book.get_metadata('DC', 'language'),
                'spine': [],
                'toc': []
            }
            
            for item_id, linear in book.spine:
                item = book.get_item_with_id(item_id)
                if item and isinstance(item, epub.EpubHtml):
                    metadata['spine'].append({
                        'id': item_id,
                        'href': item.get_name(),
                        'title': item.get_title() or item_id
                    })
            
            def parse_toc_item(toc_item):
                if isinstance(toc_item, tuple):
                    section, children = toc_item
                    return {
                        'title': section.title,
                        'href': section.href,
                        'children': [parse_toc_item(child) for child in children]
                    }
                else:
                    return {
                        'title': toc_item.title,
                        'href': toc_item.href,
                        'children': []
                    }
            
            if book.toc:
                metadata['toc'] = [parse_toc_item(item) for item in book.toc]
            
            return metadata
            
        except Exception as e:
            current_app.logger.error(f"Error parsing EPUB metadata for story {story.id}: {str(e)}")
            return None
    
    @staticmethod
    def get_reading_progress(story_id: int) -> Optional[ReadingProgress]:
        """Get reading progress for a story."""
        return ReadingProgress.query.filter_by(story_id=story_id).first()
    
    @staticmethod
    def update_reading_progress(
        story_id: int,
        current_chapter: int = None,
        current_paragraph: int = None,
        scroll_position: int = None,
        is_completed: bool = None,
        cfi: str = None
    ) -> ReadingProgress:
        """Update or create reading progress for a story."""
        progress = ReadingProgress.query.filter_by(story_id=story_id).first()

        if not progress:
            progress = ReadingProgress(story_id=story_id)
            db.session.add(progress)

        if current_chapter is not None:
            progress.current_chapter = current_chapter
        if current_paragraph is not None:
            progress.current_paragraph = current_paragraph
        if scroll_position is not None:
            progress.scroll_position = scroll_position
        if is_completed is not None:
            progress.is_completed = is_completed
        if cfi is not None:
            progress.cfi = cfi

        progress.last_read_at = datetime.utcnow()

        db.session.commit()
        return progress
    
    @staticmethod
    def get_bookmarks(story_id: int) -> List[Bookmark]:
        """Get all bookmarks for a story."""
        return Bookmark.query.filter_by(story_id=story_id).order_by(Bookmark.chapter_number, Bookmark.paragraph_number).all()
    
    @staticmethod
    def create_bookmark(
        story_id: int,
        chapter_number: int,
        paragraph_number: int = None,
        note: str = None
    ) -> Bookmark:
        """Create a new bookmark."""
        bookmark = Bookmark(
            story_id=story_id,
            chapter_number=chapter_number,
            paragraph_number=paragraph_number,
            note=note
        )
        db.session.add(bookmark)
        db.session.commit()
        return bookmark
    
    @staticmethod
    def delete_bookmark(bookmark_id: int) -> bool:
        """Delete a bookmark."""
        bookmark = Bookmark.query.get(bookmark_id)
        if bookmark:
            db.session.delete(bookmark)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def get_highlights(story_id: int) -> List[Highlight]:
        """Get all highlights for a story."""
        return Highlight.query.filter_by(story_id=story_id).order_by(Highlight.chapter_number, Highlight.paragraph_number).all()
    
    @staticmethod
    def create_highlight(
        story_id: int,
        chapter_number: int,
        paragraph_number: int,
        highlighted_text: str,
        start_offset: int = None,
        end_offset: int = None,
        note: str = None,
        color: str = '#FFFF00'
    ) -> Highlight:
        """Create a new highlight."""
        highlight = Highlight(
            story_id=story_id,
            chapter_number=chapter_number,
            paragraph_number=paragraph_number,
            highlighted_text=highlighted_text,
            start_offset=start_offset,
            end_offset=end_offset,
            note=note,
            color=color
        )
        db.session.add(highlight)
        db.session.commit()
        return highlight
    
    @staticmethod
    def delete_highlight(highlight_id: int) -> bool:
        """Delete a highlight."""
        highlight = Highlight.query.get(highlight_id)
        if highlight:
            db.session.delete(highlight)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def update_highlight(highlight_id: int, note: str = None, color: str = None) -> Optional[Highlight]:
        """Update a highlight's note or color."""
        highlight = Highlight.query.get(highlight_id)
        if highlight:
            if note is not None:
                highlight.note = note
            if color is not None:
                highlight.color = color
            db.session.commit()
            return highlight
        return None
