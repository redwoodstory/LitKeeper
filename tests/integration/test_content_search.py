from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient


UNIQUE_PHRASE = "zqxwphrase moonlit gramophone"


def _make_story(app: Flask, *, body_phrase: str) -> int:
    from app.models import Author, Story, StoryFormat, db
    from app.utils.paths import story_json_path

    uid = str(int(time.time() * 1_000_000))
    author = Author(name=f"Author {uid}")
    db.session.add(author)
    db.session.flush()

    story = Story(
        title=f"Story {uid}",
        author_id=author.id,
        filename_base=f"story-{uid}",
    )
    db.session.add(story)
    db.session.commit()

    payload = {
        "title": story.title,
        "author": author.name,
        "chapters": [
            {"title": "Chapter 1", "paragraphs": [
                "An ordinary opening line.",
                f"Then {body_phrase} appeared without warning.",
            ]},
        ],
    }
    json_path = Path(story_json_path(story.id, story.filename_base))
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    db.session.add(StoryFormat(
        story_id=story.id,
        format_type="json",
        file_path=str(json_path),
        json_data=json.dumps(payload),
    ))
    db.session.commit()
    return story.id


@pytest.mark.integration
class TestContentSearch:
    def test_body_phrase_is_found_with_snippet(self, client: FlaskClient, app: Flask):
        with app.app_context():
            from app.services import search_index

            story_id = _make_story(app, body_phrase=UNIQUE_PHRASE)
            assert search_index.index_story(story_id) is True

        resp = client.get("/library/filter", query_string={"search": "moonlit gramophone"})
        assert resp.status_code == 200
        assert f'data-story-id="{story_id}"'.encode() in resp.data
        assert b"<mark>" in resp.data

    def test_api_search_endpoint(self, client: FlaskClient, app: Flask):
        with app.app_context():
            from app.services import search_index

            story_id = _make_story(app, body_phrase=UNIQUE_PHRASE)
            search_index.index_story(story_id)

        resp = client.get("/api/library/search", query_string={"q": "gramophone"})
        assert resp.status_code == 200
        data = resp.get_json()
        ids = {s["id"] for s in data["stories"]}
        assert story_id in ids
        hit = next(s for s in data["stories"] if s["id"] == story_id)
        assert "<mark>" in (hit.get("content_snippet") or "")
        assert data["total_count"] >= 1
        assert data["total_pages"] >= 1

    def test_api_search_requires_query(self, client: FlaskClient):
        assert client.get("/api/library/search").status_code == 400

    def test_reindex_stale_picks_up_content_change(self, client: FlaskClient, app: Flask):
        with app.app_context():
            from datetime import datetime, timedelta

            from app.models import Story, db
            from app.services import search_index
            from app.utils.paths import story_json_path

            story_id = _make_story(app, body_phrase="original filler text")
            search_index.index_story(story_id)

            story = db.session.get(Story, story_id)
            json_file = Path(story_json_path(story_id, story.filename_base))
            payload = json.loads(json_file.read_text())
            payload["chapters"][0]["paragraphs"].append(f"Now with {UNIQUE_PHRASE}.")
            json_file.write_text(json.dumps(payload), encoding="utf-8")
            # make the story look changed
            story.updated_at = datetime.utcnow() + timedelta(seconds=1)
            db.session.commit()

            result = search_index.reindex_stale()
            assert result["indexed"] >= 1
            assert any(h["story_id"] == story_id for h in search_index.search("gramophone"))

    def test_delete_removes_fts_row(self, client: FlaskClient, app: Flask):
        with app.app_context():
            from app.models.base import db
            from app.services import search_index
            from app.services.story_deletion import StoryDeletionService
            from sqlalchemy import text

            story_id = _make_story(app, body_phrase=UNIQUE_PHRASE)
            search_index.index_story(story_id)

            StoryDeletionService().delete_story(story_id)

            remaining = db.session.execute(
                text("SELECT COUNT(*) FROM story_content_fts WHERE story_id = :s"),
                {"s": story_id},
            ).scalar()
            assert remaining == 0
