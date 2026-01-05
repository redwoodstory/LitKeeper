from __future__ import annotations
from typing import Dict, Optional
import warnings
import ebooklib
from ebooklib import epub

warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

class MetadataExtractor:
    """Extracts metadata from JSON and EPUB files"""

    def extract_metadata(self, file_group: Dict) -> Dict:
        """
        Extract metadata from file group (prioritize JSON over EPUB).

        Returns metadata dict with keys:
            title, author, category, tags, cover, source_url, author_url,
            page_count, word_count, chapter_count
        """
        json_format = next((f for f in file_group['formats'] if f['type'] == 'json'), None)
        if json_format and json_format.get('json_data'):
            return self._extract_from_json(json_format['json_data'])

        epub_format = next((f for f in file_group['formats'] if f['type'] == 'epub'), None)
        if epub_format:
            return self._extract_from_epub(epub_format['path'])

        raise ValueError(f"No valid metadata source for {file_group['filename_base']}")

    def _extract_from_json(self, json_data: Dict) -> Dict:
        """Extract metadata from JSON file"""
        return {
            'title': json_data.get('title', 'Unknown'),
            'author': json_data.get('author', 'Unknown Author'),
            'category': json_data.get('category'),
            'tags': json_data.get('tags', []),
            'cover': json_data.get('cover'),
            'source_url': json_data.get('source_url'),
            'author_url': json_data.get('author_url'),
            'page_count': json_data.get('page_count'),
            'word_count': json_data.get('word_count'),
            'chapter_count': len(json_data.get('chapters', []))
        }

    def _extract_from_epub(self, epub_path: str) -> Dict:
        """Extract metadata from EPUB file using ebooklib"""
        try:
            book = epub.read_epub(epub_path, options={'ignore_ncx': True})

            title = book.get_metadata('DC', 'title')
            title = title[0][0] if title else 'Unknown'

            author = book.get_metadata('DC', 'creator')
            author = author[0][0] if author else 'Unknown Author'

            subjects = book.get_metadata('DC', 'subject')
            tags = [s[0] for s in subjects] if subjects else []

            category = tags[0] if tags else None

            chapter_count = len([item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)])

            return {
                'title': title,
                'author': author,
                'category': category,
                'tags': tags,
                'cover': None,
                'source_url': None,
                'author_url': None,
                'page_count': None,
                'word_count': None,
                'chapter_count': chapter_count
            }
        except Exception as e:
            raise ValueError(f"Failed to extract EPUB metadata: {str(e)}")
