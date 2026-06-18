from __future__ import annotations
from flask import render_template, request
from sqlalchemy import func
from . import highlights
from app.models import Highlight, Story
from sqlalchemy.orm import joinedload

_VALID_SORTS = {'date_desc', 'date_asc', 'story', 'random'}


@highlights.route('/')
def highlights_page():
    sort = request.args.get('sort', 'date_desc')
    if sort not in _VALID_SORTS:
        sort = 'date_desc'

    q = Highlight.query.options(joinedload(Highlight.story).joinedload(Story.author))

    if sort == 'date_asc':
        q = q.order_by(Highlight.created_at.asc())
    elif sort == 'story':
        q = (q.join(Highlight.story)
               .order_by(Story.title.asc(), Highlight.chapter_index.asc(), Highlight.paragraph_index.asc()))
    elif sort == 'random':
        q = q.order_by(func.random())
    else:
        q = q.order_by(Highlight.created_at.desc())

    records = q.all()
    return render_template('highlights.html', highlights=records, current_sort=sort)
