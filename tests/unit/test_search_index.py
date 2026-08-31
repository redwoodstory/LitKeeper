from __future__ import annotations

import pytest

from app.services import search_index


@pytest.mark.unit
class TestSanitizeFtsQuery:
    def test_plain_terms_are_quoted_with_trailing_prefix(self):
        assert search_index._sanitize_fts_query("dragon rider") == '"dragon" "rider"*'

    def test_single_term(self):
        assert search_index._sanitize_fts_query("whispered") == '"whispered"*'

    def test_operator_chars_are_neutralised(self):
        # quotes / stars / parens / NOT would otherwise be fts5 syntax
        assert search_index._sanitize_fts_query('cat AND "dog* (x') == '"cat" "AND" "dog" "x"*'

    def test_blank_returns_none(self):
        assert search_index._sanitize_fts_query("   ") is None
        assert search_index._sanitize_fts_query("") is None
        assert search_index._sanitize_fts_query('"*()-') is None

    def test_unicode_is_preserved(self):
        assert search_index._sanitize_fts_query("café señor") == '"café" "señor"*'


@pytest.mark.unit
class TestFlattenStoryText:
    def test_joins_chapter_titles_and_paragraphs(self, tmp_path, monkeypatch):
        import json

        class _Author:
            name = "A"

        class _Story:
            id = 1
            filename_base = "x"
            author = _Author()
            tags = []
            title = "T"

        payload = {
            "chapters": [
                {"title": "Chapter 1", "paragraphs": ["hello world", "second para"]},
                {"title": "Chapter 2", "paragraphs": ["the end"]},
            ]
        }
        json_file = tmp_path / "1_x.json"
        json_file.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(
            "app.utils.paths.story_json_path", lambda sid, fb: str(json_file)
        )

        text = search_index._flatten_story_text(_Story())
        assert text == "Chapter 1\nhello world\nsecond para\nChapter 2\nthe end"
