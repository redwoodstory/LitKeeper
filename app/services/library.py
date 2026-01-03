from __future__ import annotations
from typing import List, Dict

def get_library_data() -> List[Dict]:
    """
    Get library data from database.
    Library now requires database mode.
    """
    from app.models import Story

    stories = Story.query.order_by(Story.created_at.desc()).all()
    return [story.to_library_dict() for story in stories]
