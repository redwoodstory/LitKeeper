from __future__ import annotations
import os
import zipfile
import xml.etree.ElementTree as ET
import warnings
from typing import Optional, Dict, List, Any
from ebooklib import epub
from flask import current_app
from app.models import Story, ReadingProgress
from app.models.base import db
from datetime import datetime

warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

class EpubService:
    
    @staticmethod
    def get_epub_path(story: Story) -> Optional[str]:
        """Get the full path to the EPUB file for a story."""
        from app.utils import get_epub_directory
        
        epub_format = next((f for f in story.formats if f.format_type == 'epub'), None)
        if not epub_format:
            return None
        
        epub_dir = get_epub_directory()
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
            book = epub.read_epub(epub_path, options={'ignore_ncx': True})
            
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
        cfi: str = None,
        percentage: float = None
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
        if percentage is not None:
            progress.percentage = percentage

        progress.last_read_at = datetime.utcnow()

        db.session.commit()
        return progress
