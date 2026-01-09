from __future__ import annotations
import os
import zipfile
import xml.etree.ElementTree as ET
import warnings
import traceback
from typing import Optional, Dict, List, Any
from ebooklib import epub
from flask import current_app
from app.models import Story, ReadingProgress
from app.models.base import db
from datetime import datetime
from .logger import log_error

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
    
    @staticmethod
    def update_epub_cover(epub_path: str, cover_image_path: str) -> bool:
        """Update the cover image in an existing EPUB file.
        
        Args:
            epub_path: Path to the EPUB file
            cover_image_path: Path to the new cover image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(epub_path):
                log_error(f"EPUB file not found: {epub_path}")
                return False
            
            if not os.path.exists(cover_image_path):
                log_error(f"Cover image not found: {cover_image_path}")
                return False
            
            book = epub.read_epub(epub_path, options={'ignore_ncx': True, 'ignore_missing_toc': True})
            
            with open(cover_image_path, 'rb') as cover_file:
                cover_data = cover_file.read()
            
            items_to_remove = []
            for item in book.get_items():
                if hasattr(item, 'get_name'):
                    item_name = item.get_name()
                    if item_name and 'cover' in item_name.lower():
                        items_to_remove.append(item)
            
            for item in items_to_remove:
                book.items.remove(item)
            
            cover_item = epub.EpubItem(
                uid="cover-img",
                file_name="cover.jpg",
                media_type="image/jpeg",
                content=cover_data
            )
            book.add_item(cover_item)
            
            metadata = book.metadata.get('http://www.idpf.org/2007/opf', [])
            metadata_to_remove = []
            for item in metadata:
                if item and len(item) >= 2 and item[0] == 'meta':
                    attrs = item[1] if len(item) > 1 else {}
                    if attrs and attrs.get('name') == 'cover':
                        metadata_to_remove.append(item)
            
            for item in metadata_to_remove:
                metadata.remove(item)
            
            book.metadata['http://www.idpf.org/2007/opf'] = metadata
            book.add_metadata('http://www.idpf.org/2007/opf', 'meta', '', {'name': 'cover', 'content': 'cover-img'})
            
            ncx_item = None
            for item in book.get_items():
                if isinstance(item, epub.EpubNcx):
                    ncx_item = item
                    break
            
            if ncx_item:
                book.items.remove(ncx_item)
            
            epub.write_epub(epub_path, book, {
                'epub3_pages': False,
                'epub3_landmark': None,
                'epub2_guide': None,
                'spine_direction': True
            })
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating EPUB cover: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return False
