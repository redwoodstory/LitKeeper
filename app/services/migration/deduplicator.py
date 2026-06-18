from __future__ import annotations
from typing import Optional, Dict
from app.models import Story

class Deduplicator:
    """Detects duplicate stories in the database"""

    def check_duplicate(self, metadata: Dict, filename_base: str) -> Optional[Story]:
        """
        Returns an existing Story if source_url matches, None otherwise.
        """
        source_url = metadata.get('source_url')
        if source_url:
            story = Story.query.filter_by(literotica_url=source_url).first()
            if story:
                return story

        return None
