from __future__ import annotations
from typing import Optional, Dict
from difflib import SequenceMatcher
from app.models import Story

class Deduplicator:
    """Detects duplicate stories in the database"""

    def check_duplicate(self, metadata: Dict, filename_base: str) -> Optional[Story]:
        """
        Check if a story already exists in the database.

        Checks in order:
        1. literotica_url (exact match)
        2. filename_base (exact match)
        3. title + author (fuzzy match, 95% threshold)

        Returns:
            Existing Story object if duplicate found, None otherwise
        """
        if metadata.get('source_url'):
            story = Story.query.filter_by(literotica_url=metadata['source_url']).first()
            if story:
                return story

        story = Story.query.filter_by(filename_base=filename_base).first()
        if story:
            return story

        title = metadata.get('title', '').lower()
        author = metadata.get('author', '').lower()

        if not title or not author:
            return None

        potential_duplicates = Story.query.filter(
            Story.title.ilike(f'%{title[:20]}%')
        ).all()

        for candidate in potential_duplicates:
            title_similarity = SequenceMatcher(None, title, candidate.title.lower()).ratio()
            author_similarity = SequenceMatcher(None, author, candidate.author.name.lower()).ratio()

            combined_similarity = (title_similarity * 0.6) + (author_similarity * 0.4)

            if combined_similarity >= 0.95:
                return candidate

        return None
