"""Full-text search index over story body text, backed by SQLite FTS5.

The story text already lives in each story's ``format_type='json'`` StoryFormat
row (mirrored from an on-disk ``{id}_{filename_base}.json`` file). This module
keeps a separate ``story_content_fts`` virtual table in sync with that text so
the library search box can match story *content*, not just metadata.

Sync model is lazy: ``reindex_stale()`` (run periodically by SearchIndexWorker
and on demand via ``flask search reindex``) re-indexes any story whose
``content_indexed_at`` is older than its ``updated_at`` or its JSON file mtime.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import text

_FTS5_AVAILABLE: Optional[bool] = None

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS story_content_fts USING fts5(
    story_id UNINDEXED,
    title,
    author,
    tags,
    body,
    tokenize = 'porter unicode61 remove_diacritics 2'
)
"""

# 0=story_id, 1=title, 2=author, 3=tags, 4=body
_BODY_COLUMN = 4
_SNIPPET_OPEN = "\x02"
_SNIPPET_CLOSE = "\x03"
_FTS_OPERATOR_CHARS = str.maketrans({c: " " for c in '"*:^()-+~'})


def fts5_available() -> bool:
    """Whether this SQLite build has the FTS5 extension. Cached after first check."""
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is None:
        from app.models.base import db
        try:
            db.session.execute(text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"
            ))
            db.session.execute(text("DROP TABLE IF EXISTS _fts5_probe"))
            db.session.commit()
            _FTS5_AVAILABLE = True
        except Exception:
            db.session.rollback()
            _FTS5_AVAILABLE = False
    return _FTS5_AVAILABLE


def ensure_fts_schema() -> bool:
    """Create the FTS table if missing. Safe to call on every startup.

    Migrations are authoritative for real deployments; this also covers fresh
    databases created via ``db.create_all()`` (e.g. the test suite), where the
    virtual table would otherwise never be built.
    """
    if not fts5_available():
        return False
    from app.models.base import db
    try:
        db.session.execute(text(_FTS_SCHEMA))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def _flatten_story_text(story) -> str:
    """Concatenate every chapter title and paragraph for a story.

    Priority: on-disk JSON file (source of truth; the json_data column can lag) →
    json_data column → ebooklib extraction from the EPUB.
    """
    import json

    from app.models import StoryFormat
    from app.utils.paths import story_json_path

    data = None

    json_path = story_json_path(story.id, story.filename_base)
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = None

    if data is None:
        json_fmt = StoryFormat.query.filter_by(story_id=story.id, format_type='json').first()
        if json_fmt and json_fmt.json_data:
            try:
                data = json.loads(json_fmt.json_data)
            except Exception:
                data = None

    if data is None:
        return _extract_text_from_epub(story.id)

    parts: list[str] = []
    for chapter in data.get('chapters', []) or []:
        title = (chapter.get('title') or '').strip()
        if title:
            parts.append(title)
        for para in chapter.get('paragraphs', []) or []:
            if para:
                parts.append(para)
    return "\n".join(parts)


def _extract_text_from_epub(story_id: int) -> str:
    """Last-resort body extraction straight from the EPUB spine."""
    import xml.etree.ElementTree as ET
    from html import unescape

    import ebooklib
    from ebooklib import epub as ebooklib_epub

    from app.models import StoryFormat

    _XHTML_NS = {'xhtml': 'http://www.w3.org/1999/xhtml'}
    _SKIP_IDS = {'nav', 'cover', 'metadata', 'intro', 'toc'}

    epub_fmt = StoryFormat.query.filter_by(story_id=story_id, format_type='epub').first()
    if not epub_fmt or not os.path.exists(epub_fmt.file_path):
        return ""

    try:
        book = ebooklib_epub.read_epub(epub_fmt.file_path, options={'ignore_ncx': True})
    except Exception:
        return ""

    parts: list[str] = []
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        item_name = (item.get_name() or '').lower()
        if item.id in _SKIP_IDS or any(skip in item_name for skip in _SKIP_IDS):
            continue
        try:
            root = ET.fromstring(item.get_content().decode('utf-8', errors='replace'))
        except ET.ParseError:
            continue
        body = root.find('xhtml:body', _XHTML_NS) or root.find('body')
        if body is None:
            continue
        for tag in ('xhtml:h1', 'h1', 'xhtml:p', 'p'):
            for el in body.findall(tag, _XHTML_NS) if ':' in tag else body.findall(tag):
                txt = unescape(''.join(el.itertext())).strip()
                if txt:
                    parts.append(txt)
    return "\n".join(parts)


def index_story(story_id: int) -> bool:
    """(Re)build the FTS row for one story. Never raises."""
    if not fts5_available():
        return False

    from datetime import datetime

    from app.models import Story
    from app.models.base import db
    from app.services.logger import log_error

    try:
        story = db.session.get(Story, story_id)
        if not story:
            remove_story(story_id)
            return False

        body = _flatten_story_text(story)
        tags = " ".join(t.name for t in story.tags)
        author = story.author.name if story.author else ""

        db.session.execute(
            text("DELETE FROM story_content_fts WHERE story_id = :sid"),
            {"sid": story_id},
        )
        db.session.execute(
            text(
                "INSERT INTO story_content_fts (story_id, title, author, tags, body) "
                "VALUES (:sid, :title, :author, :tags, :body)"
            ),
            {"sid": story_id, "title": story.title or "", "author": author,
             "tags": tags, "body": body},
        )
        # Direct UPDATE (not via the ORM) so the mixin's ``updated_at`` onupdate
        # doesn't fire — indexing must not look like a content change to clients.
        db.session.execute(
            text("UPDATE stories SET content_indexed_at = :ts WHERE id = :sid"),
            {"ts": datetime.utcnow(), "sid": story_id},
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        log_error(f"search_index.index_story({story_id}) failed: {e}")
        return False


def remove_story(story_id: int) -> None:
    """Drop a story's FTS row (called from the deletion path)."""
    if not fts5_available():
        return
    from app.models.base import db
    from app.services.logger import log_error
    try:
        db.session.execute(
            text("DELETE FROM story_content_fts WHERE story_id = :sid"),
            {"sid": story_id},
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log_error(f"search_index.remove_story({story_id}) failed: {e}")


def _needs_reindex(story_id: int, filename_base: str, indexed_at, updated_at) -> bool:
    if indexed_at is None:
        return True
    if updated_at is not None and indexed_at < updated_at:
        return True
    from app.utils.paths import story_json_path
    json_path = story_json_path(story_id, filename_base)
    try:
        mtime = os.path.getmtime(json_path)
    except OSError:
        return False
    from datetime import datetime
    return indexed_at < datetime.utcfromtimestamp(mtime)


def reindex_stale(limit: Optional[int] = None) -> dict:
    """Re-index stories whose FTS row is missing or out of date, and prune orphans."""
    if not fts5_available():
        return {"indexed": 0, "pruned": 0, "failed": 0, "skipped": "fts5 unavailable"}

    from app.models.base import db

    rows = db.session.execute(
        text("SELECT id, filename_base, content_indexed_at, updated_at FROM stories")
    ).all()

    stale_ids = [
        r[0] for r in rows
        if _needs_reindex(r[0], r[1], _as_dt(r[2]), _as_dt(r[3]))
    ]
    if limit is not None:
        stale_ids = stale_ids[:limit]

    indexed = failed = 0
    for sid in stale_ids:
        if index_story(sid):
            indexed += 1
        else:
            failed += 1

    pruned = db.session.execute(
        text("DELETE FROM story_content_fts "
             "WHERE story_id NOT IN (SELECT id FROM stories)")
    ).rowcount or 0
    db.session.commit()

    return {"indexed": indexed, "pruned": pruned, "failed": failed}


def rebuild_all() -> dict:
    """Wipe and rebuild the entire index."""
    if not fts5_available():
        return {"indexed": 0, "skipped": "fts5 unavailable"}
    from app.models.base import db

    db.session.execute(text("DELETE FROM story_content_fts"))
    db.session.execute(text("UPDATE stories SET content_indexed_at = NULL"))
    db.session.commit()
    return reindex_stale()


def _as_dt(value):
    if value is None or hasattr(value, 'year'):
        return value
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _sanitize_fts_query(raw: str) -> Optional[str]:
    """Turn free-form user input into a safe FTS5 MATCH string.

    Each whitespace-separated token is stripped of FTS operator characters and
    double-quoted; the final token gets a ``*`` for prefix matching. Returns
    ``None`` when nothing searchable survives.
    """
    if not raw:
        return None
    tokens = [t for t in raw.translate(_FTS_OPERATOR_CHARS).split() if t]
    if not tokens:
        return None
    quoted = [f'"{t}"' for t in tokens]
    quoted[-1] = f'{quoted[-1]}*'
    return " ".join(quoted)


def search(raw_query: str, limit: int = 500, offset: int = 0) -> list[dict]:
    """Return ``[{story_id, rank, snippet}]`` ordered by relevance.

    ``snippet`` is HTML-escaped with ``<mark>`` wrapping the matched terms, safe
    to render with ``| safe``.
    """
    if not fts5_available():
        return []

    from markupsafe import escape

    from app.models.base import db
    from app.services.logger import log_error

    match = _sanitize_fts_query(raw_query)
    if not match:
        return []

    try:
        rows = db.session.execute(
            text(
                "SELECT story_id, "
                "bm25(story_content_fts) AS rank, "
                f"snippet(story_content_fts, {_BODY_COLUMN}, :o, :c, '…', 16) AS snip "
                "FROM story_content_fts "
                "WHERE story_content_fts MATCH :q "
                "ORDER BY rank LIMIT :lim OFFSET :off"
            ),
            {"q": match, "o": _SNIPPET_OPEN, "c": _SNIPPET_CLOSE,
             "lim": limit, "off": offset},
        ).all()
    except Exception as e:
        log_error(f"search_index.search({raw_query!r}) failed: {e}")
        return []

    results = []
    for story_id, rank, snip in rows:
        marked = (
            str(escape(snip or ""))
            .replace(_SNIPPET_OPEN, "<mark>")
            .replace(_SNIPPET_CLOSE, "</mark>")
        )
        results.append({"story_id": story_id, "rank": rank, "snippet": marked})
    return results


def status() -> dict:
    """Counts for ``flask search status``."""
    from app.models.base import db
    total = db.session.execute(text("SELECT COUNT(*) FROM stories")).scalar() or 0
    if not fts5_available():
        return {"total": total, "indexed": 0, "stale": total,
                "orphans": 0, "fts5": False}
    indexed = db.session.execute(
        text("SELECT COUNT(*) FROM story_content_fts")
    ).scalar() or 0
    orphans = db.session.execute(
        text("SELECT COUNT(*) FROM story_content_fts "
             "WHERE story_id NOT IN (SELECT id FROM stories)")
    ).scalar() or 0
    rows = db.session.execute(
        text("SELECT id, filename_base, content_indexed_at, updated_at FROM stories")
    ).all()
    stale = sum(
        1 for r in rows
        if _needs_reindex(r[0], r[1], _as_dt(r[2]), _as_dt(r[3]))
    )
    return {"total": total, "indexed": indexed, "stale": stale,
            "orphans": orphans, "fts5": True}
