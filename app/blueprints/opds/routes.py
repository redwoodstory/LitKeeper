from __future__ import annotations
import os
import xml.etree.ElementTree as ET
from datetime import timezone
from flask import request, url_for, make_response, abort, send_from_directory
from . import opds_bp
from app.models import Story, Category
from app.models.story_format import StoryFormat

PAGE_SIZE = 30

OPDS_NS = 'http://www.w3.org/2005/Atom'
DC_NS = 'http://purl.org/dc/terms/'
OPDS_SPEC = 'http://opds-spec.org/2010/catalog'

ET.register_namespace('', OPDS_NS)
ET.register_namespace('dc', DC_NS)
ET.register_namespace('opds', OPDS_SPEC)


def _xml_response(root: ET.Element) -> object:
    # Re-register before every serialization — other modules (epub_service) overwrite
    # the global ET namespace map, causing Atom to serialize with ns0: prefix.
    ET.register_namespace('', OPDS_NS)
    ET.register_namespace('dc', DC_NS)
    ET.register_namespace('opds', OPDS_SPEC)
    ET.indent(root, space='  ')
    xml_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    resp = make_response(xml_bytes)
    resp.content_type = 'application/atom+xml;profile=opds-catalog;charset=utf-8'
    return resp


def _feed(feed_id: str, title: str, updated: str) -> ET.Element:
    feed = ET.Element(f'{{{OPDS_NS}}}feed')
    _sub(feed, 'id', feed_id)
    _sub(feed, 'title', title)
    _sub(feed, 'updated', updated)
    _link(feed, 'self', request.url, 'application/atom+xml;profile=opds-catalog')
    _link(feed, 'start', url_for('opds.root', _external=True), 'application/atom+xml;profile=opds-catalog')
    _link(feed, 'search', url_for('opds.opensearch', _external=True), 'application/opensearchdescription+xml')
    return feed


def _sub(parent: ET.Element, tag: str, text: str | None, ns: str = OPDS_NS) -> ET.Element:
    el = ET.SubElement(parent, f'{{{ns}}}{tag}')
    if text is not None:
        el.text = text
    return el


def _link(parent: ET.Element, rel: str, href: str, mime: str, title: str | None = None) -> None:
    attrs = {'rel': rel, 'href': href, 'type': mime}
    if title:
        attrs['title'] = title
    ET.SubElement(parent, f'{{{OPDS_NS}}}link', attrs)


def _story_updated(story: Story) -> str:
    dt = story.updated_at or story.created_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _epub_stories_query():
    return (
        Story.query
        .join(StoryFormat, (StoryFormat.story_id == Story.id) & (StoryFormat.format_type == 'epub'))
    )


def _append_story_entry(feed: ET.Element, story: Story) -> None:
    entry = ET.SubElement(feed, f'{{{OPDS_NS}}}entry')
    _sub(entry, 'title', story.title)
    _sub(entry, 'id', f'urn:litkeeper:story:{story.id}')
    _sub(entry, 'updated', _story_updated(story))

    author_el = ET.SubElement(entry, f'{{{OPDS_NS}}}author')
    _sub(author_el, 'name', story.author.name if story.author else 'Unknown')

    summary_parts = []
    if story.rating:
        stars = '★' * story.rating + '☆' * (5 - story.rating)
        summary_parts.append(f'Rating: {stars}')
    else:
        summary_parts.append('Rating: Not rated')
    if story.literotica_page_count:
        summary_parts.append(f'Pages: {story.literotica_page_count}')
    if story.word_count:
        summary_parts.append(f'Words: {story.word_count:,}')
    if story.description:
        summary_parts.append(story.description)

    summary_text = '\n\n'.join(summary_parts)
    summary = ET.SubElement(entry, f'{{{OPDS_NS}}}summary')
    summary.text = summary_text
    summary.set('type', 'text')

    if story.description:
        _sub(entry, 'description', story.description, DC_NS)

    if story.category:
        ET.SubElement(entry, f'{{{OPDS_NS}}}category', {
            'term': story.category.slug,
            'label': story.category.name,
        })

    for tag in story.tags:
        ET.SubElement(entry, f'{{{OPDS_NS}}}category', {
            'term': tag.name,
            'label': tag.name,
        })

    # Cover image
    cover_href = url_for('api.get_story_cover', story_id=story.id, _external=True)
    _link(entry, 'http://opds-spec.org/image', cover_href, 'image/jpeg')
    _link(entry, 'http://opds-spec.org/image/thumbnail', cover_href, 'image/jpeg')

    # EPUB acquisition — served via OPDS route so auth gate applies
    epub_href = url_for('opds.serve_epub', story_id=story.id, _external=True)
    _link(entry, 'http://opds-spec.org/acquisition', epub_href, 'application/epub+zip',
          title=story.title)

    if story.word_count:
        _sub(entry, 'extent', f'{story.word_count} words', DC_NS)


def _nav_entry(feed: ET.Element, title: str, href: str, content: str) -> None:
    entry = ET.SubElement(feed, f'{{{OPDS_NS}}}entry')
    _sub(entry, 'title', title)
    _sub(entry, 'id', f'urn:litkeeper:nav:{href}')
    _sub(entry, 'updated', '2020-01-01T00:00:00Z')
    summary = ET.SubElement(entry, f'{{{OPDS_NS}}}content')
    summary.text = content
    summary.set('type', 'text')
    _link(entry, 'subsection', href, 'application/atom+xml;profile=opds-catalog;kind=navigation')


@opds_bp.route('', methods=['GET'])
@opds_bp.route('/', methods=['GET'])
def root():
    feed = _feed('urn:litkeeper:catalog', 'LitKeeper', '2020-01-01T00:00:00Z')
    feed.find(f'{{{OPDS_NS}}}link[@rel="self"]').set(
        'href', url_for('opds.root', _external=True)
    )

    _nav_entry(feed, 'Recently Added', url_for('opds.new_arrivals', _external=True),
               'Recently added stories')
    _nav_entry(feed, 'All Stories', url_for('opds.catalog', _external=True),
               'Browse the complete library')
    _nav_entry(feed, 'By Category', url_for('opds.categories', _external=True),
               'Browse stories by category')
    _nav_entry(feed, 'Rated 5 Stars', url_for('opds.rated', rating=5, _external=True),
               '5 star stories')
    _nav_entry(feed, 'Rated 4 Stars', url_for('opds.rated', rating=4, _external=True),
               '4 star stories')
    _nav_entry(feed, 'Rated 3 Stars', url_for('opds.rated', rating=3, _external=True),
               '3 star stories')
    _nav_entry(feed, 'Rated 2 Stars', url_for('opds.rated', rating=2, _external=True),
               '2 star stories')
    _nav_entry(feed, 'Rated 1 Star', url_for('opds.rated', rating=1, _external=True),
               '1 star stories')
    _nav_entry(feed, 'No Rating', url_for('opds.rated', rating=0, _external=True),
               'Unrated stories')

    search_href = url_for('opds.search', _external=True) + '?q={searchTerms}'
    ET.SubElement(feed, f'{{{OPDS_NS}}}link', {
        'rel': 'search',
        'href': search_href,
        'type': 'application/atom+xml',
    })

    return _xml_response(feed)


@opds_bp.route('/new')
def new_arrivals():
    stories = (
        _epub_stories_query()
        .order_by(Story.created_at.desc())
        .limit(PAGE_SIZE)
        .all()
    )
    feed = _feed('urn:litkeeper:new', 'Recently Added', '2020-01-01T00:00:00Z')
    for story in stories:
        _append_story_entry(feed, story)
    return _xml_response(feed)


@opds_bp.route('/catalog')
def catalog():
    page = max(1, request.args.get('page', 1, type=int))
    q = _epub_stories_query().order_by(Story.title)
    total = q.count()
    stories = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

    feed = _feed('urn:litkeeper:catalog:all', 'All Stories', '2020-01-01T00:00:00Z')

    if page > 1:
        _link(feed, 'previous',
              url_for('opds.catalog', page=page - 1, _external=True),
              'application/atom+xml;profile=opds-catalog')
    if page * PAGE_SIZE < total:
        _link(feed, 'next',
              url_for('opds.catalog', page=page + 1, _external=True),
              'application/atom+xml;profile=opds-catalog')

    for story in stories:
        _append_story_entry(feed, story)
    return _xml_response(feed)


@opds_bp.route('/categories')
def categories():
    cats = Category.query.order_by(Category.name).all()
    feed = _feed('urn:litkeeper:categories', 'By Category', '2020-01-01T00:00:00Z')
    for cat in cats:
        count = (
            _epub_stories_query()
            .filter(Story.category_id == cat.id)
            .count()
        )
        if count == 0:
            continue
        href = url_for('opds.category', category_id=cat.id, _external=True)
        _nav_entry(feed, cat.name, href, f'{count} {"story" if count == 1 else "stories"}')
    return _xml_response(feed)


@opds_bp.route('/category/<int:category_id>')
def category(category_id: int):
    cat = Category.query.get_or_404(category_id)
    page = max(1, request.args.get('page', 1, type=int))
    q = _epub_stories_query().filter(Story.category_id == category_id).order_by(Story.title)
    total = q.count()
    stories = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

    feed = _feed(f'urn:litkeeper:category:{category_id}', cat.name, '2020-01-01T00:00:00Z')

    if page > 1:
        _link(feed, 'previous',
              url_for('opds.category', category_id=category_id, page=page - 1, _external=True),
              'application/atom+xml;profile=opds-catalog')
    if page * PAGE_SIZE < total:
        _link(feed, 'next',
              url_for('opds.category', category_id=category_id, page=page + 1, _external=True),
              'application/atom+xml;profile=opds-catalog')

    for story in stories:
        _append_story_entry(feed, story)
    return _xml_response(feed)


@opds_bp.route('/search')
def search():
    q_param = request.args.get('q', '').strip()
    feed = _feed('urn:litkeeper:search', f'Search: {q_param}', '2020-01-01T00:00:00Z')

    if q_param:
        from app.models import Author
        term = f'%{q_param}%'
        stories = (
            _epub_stories_query()
            .join(Author, Story.author_id == Author.id)
            .filter(Story.title.ilike(term) | Author.name.ilike(term))
            .order_by(Story.title)
            .limit(PAGE_SIZE)
            .all()
        )
        for story in stories:
            _append_story_entry(feed, story)

    return _xml_response(feed)


@opds_bp.route('/rated/<int:rating>')
def rated(rating: int):
    if rating == 0:
        q = _epub_stories_query().filter(Story.rating.is_(None))
        title = 'No Rating'
        feed_id = 'urn:litkeeper:rated:0'
    else:
        q = _epub_stories_query().filter(Story.rating == rating)
        title = f'Rated {rating} Star{"s" if rating != 1 else ""}'
        feed_id = f'urn:litkeeper:rated:{rating}'

    stories = q.order_by(Story.title).limit(PAGE_SIZE).all()
    feed = _feed(feed_id, title, '2020-01-01T00:00:00Z')
    for story in stories:
        _append_story_entry(feed, story)
    return _xml_response(feed)


@opds_bp.route('/file/<int:story_id>')
def serve_epub(story_id: int):
    story = Story.query.get_or_404(story_id)
    epub_format = StoryFormat.query.filter_by(story_id=story_id, format_type='epub').first()
    if not epub_format or not os.path.exists(epub_format.file_path):
        abort(404)
    directory = os.path.dirname(epub_format.file_path)
    filename = os.path.basename(epub_format.file_path)
    response = send_from_directory(directory, filename, as_attachment=False,
                                   mimetype='application/epub+zip')
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@opds_bp.route('/opensearch.xml')
def opensearch():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">'
        '<ShortName>LitKeeper</ShortName>'
        '<Description>Search LitKeeper stories</Description>'
        f'<Url type="application/atom+xml" template="{url_for("opds.search", _external=True)}?q={{searchTerms}}"/>'
        '</OpenSearchDescription>'
    )
    resp = make_response(xml)
    resp.content_type = 'application/opensearchdescription+xml'
    return resp
