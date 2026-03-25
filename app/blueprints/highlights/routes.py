from __future__ import annotations
from flask import render_template
from . import highlights
from app.models import Highlight, Story
from sqlalchemy.orm import joinedload


@highlights.route('/')
def highlights_page():
    records = (Highlight.query
               .options(joinedload(Highlight.story).joinedload(Story.author))
               .order_by(Highlight.created_at.desc())
               .all())
    return render_template('highlights.html', highlights=records)
