from __future__ import annotations
import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch
from app.services.html_generator import create_html_file


@pytest.mark.unit
class TestCreateHtmlFile:
    """Test create_html_file function."""

    def test_create_html_file_structure(self, temp_dir: Path) -> None:
        """JSON file created with correct structure."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Test Story",
                    story_author="Test Author",
                    story_content="Story content here.",
                    output_directory=str(temp_dir)
                )

                assert os.path.exists(json_path)
                assert json_path.endswith('.json')

                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                assert data['title'] == "Test Story"
                assert data['author'] == "Test Author"

    def test_html_metadata_fields(self, temp_dir: Path) -> None:
        """All metadata fields are present in JSON."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Metadata Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir),
                    story_category="Romance",
                    story_tags=["love", "drama"],
                    source_url="https://example.com/story",
                    author_url="https://example.com/author"
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert data['category'] == "Romance"
                assert data['tags'] == ["love", "drama"]
                assert data['source_url'] == "https://example.com/story"
                assert data['author_url'] == "https://example.com/author"

    def test_html_chapter_parsing(self, temp_dir: Path) -> None:
        """Chapters are extracted correctly."""
        content = "Intro text.\n\nChapter 1\n\nFirst chapter content.\n\nChapter 2\n\nSecond chapter content."

        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Chapter Test",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert 'chapters' in data
                assert len(data['chapters']) == 2
                assert data['chapters'][0]['title'] == "Chapter 1"
                assert data['chapters'][1]['title'] == "Chapter 2"

    def test_html_paragraph_splitting(self, temp_dir: Path) -> None:
        """Paragraphs are split into array."""
        content = "Intro.\n\nChapter 1\n\nFirst paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Paragraph Test",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                paragraphs = data['chapters'][0]['paragraphs']
                assert len(paragraphs) == 3
                assert "First paragraph." in paragraphs
                assert "Second paragraph." in paragraphs
                assert "Third paragraph." in paragraphs

    def test_html_cover_path_set(self, temp_dir: Path) -> None:
        """Cover filename is set in JSON."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Cover Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert 'cover' in data
                assert data['cover'].endswith('.jpg')

    def test_html_unicode_content(self, temp_dir: Path) -> None:
        """Unicode content is preserved."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Unicode 测试 Story",
                    story_author="作者 Author",
                    story_content="Content with unicode: 你好世界\n\nChapter 1\n\nMore unicode: こんにちは",
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                assert "Unicode 测试 Story" in data['title']
                assert "作者 Author" in data['author']

    def test_html_sanitizes_filename(self, temp_dir: Path) -> None:
        """Filename is sanitized."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Test/Story:With<Special>Characters",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                assert os.path.exists(json_path)
                filename = os.path.basename(json_path)
                assert '/' not in filename
                assert ':' not in filename
                assert '<' not in filename

    def test_html_generates_cover(self, temp_dir: Path) -> None:
        """Cover image generation is called."""
        with patch('app.services.html_generator.generate_cover_image') as mock_gen:
            with patch('app.services.html_generator.send_notification'):
                def fake_cover(title, author, path):
                    Path(path).write_bytes(b'\xFF\xD8\xFF\xE0')

                mock_gen.side_effect = fake_cover

                json_path = create_html_file(
                    story_title="Cover Gen Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                mock_gen.assert_called_once()

    def test_html_sends_notification(self, temp_dir: Path) -> None:
        """Notification sent on success."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification') as mock_notify:
                create_html_file(
                    story_title="Notify Test",
                    story_author="Test Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                mock_notify.assert_called_once()
                call_args = mock_notify.call_args[0][0]
                assert 'Notify Test' in call_args
                assert 'Test Author' in call_args

    def test_html_error_notification_on_failure(self, temp_dir: Path) -> None:
        """Error notification sent on failure."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification') as mock_notify:
                with patch('builtins.open', side_effect=Exception("Write failed")):
                    with pytest.raises(Exception):
                        create_html_file(
                            story_title="Fail Test",
                            story_author="Author",
                            story_content="Content",
                            output_directory=str(temp_dir)
                        )

                    error_calls = [call for call in mock_notify.call_args_list if len(call[1]) > 0 and call[1].get('is_error')]
                    assert len(error_calls) > 0

    def test_html_tags_as_string_converted_to_list(self, temp_dir: Path) -> None:
        """Single tag string converted to list."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Tag String Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir),
                    story_tags="single-tag"
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert isinstance(data['tags'], list)
                assert "single-tag" in data['tags']

    def test_html_empty_tags_becomes_empty_list(self, temp_dir: Path) -> None:
        """None tags becomes empty list."""
        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="No Tags Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert data['tags'] == []

    def test_html_chapter_number_set(self, temp_dir: Path) -> None:
        """Chapter numbers are set correctly."""
        content = "Intro.\n\nChapter One\n\nContent 1.\n\nChapter Two\n\nContent 2."

        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Chapter Numbers",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                assert data['chapters'][0]['number'] == 1
                assert data['chapters'][1]['number'] == 2

    def test_html_whitespace_stripped_from_paragraphs(self, temp_dir: Path) -> None:
        """Whitespace is stripped from paragraphs."""
        content = "Intro.\n\nChapter 1\n\n  Paragraph with leading space.  \n\n  Another paragraph.  "

        with patch('app.services.html_generator.generate_cover_image'):
            with patch('app.services.html_generator.send_notification'):
                json_path = create_html_file(
                    story_title="Whitespace Test",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                with open(json_path, 'r') as f:
                    data = json.load(f)

                paragraphs = data['chapters'][0]['paragraphs']
                assert "Paragraph with leading space." in paragraphs
                assert "Another paragraph." in paragraphs
                for para in paragraphs:
                    assert para == para.strip()
