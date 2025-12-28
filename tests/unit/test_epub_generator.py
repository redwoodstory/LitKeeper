from __future__ import annotations
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from ebooklib import epub
from app.services.epub_generator import (
    format_story_content,
    format_metadata_content,
    create_epub_file
)


@pytest.mark.unit
class TestFormatStoryContent:
    """Test format_story_content function."""

    def test_format_single_paragraph(self) -> None:
        """Single paragraph is wrapped in <p> tags."""
        content = "This is a single paragraph."
        result = format_story_content(content)

        assert '<p>This is a single paragraph.</p>' in result
        assert '<style>' in result

    def test_format_multiple_paragraphs(self) -> None:
        """Multiple paragraphs separated by double newlines."""
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = format_story_content(content)

        assert '<p>First paragraph.</p>' in result
        assert '<p>Second paragraph.</p>' in result
        assert '<p>Third paragraph.</p>' in result

    def test_format_strips_whitespace(self) -> None:
        """Whitespace is stripped from paragraphs."""
        content = "  First paragraph.  \n\n  Second paragraph.  "
        result = format_story_content(content)

        assert '<p>First paragraph.</p>' in result
        assert '<p>Second paragraph.</p>' in result

    def test_format_empty_paragraphs_ignored(self) -> None:
        """Empty paragraphs are not included."""
        content = "Paragraph one.\n\n\n\nParagraph two."
        result = format_story_content(content)

        assert result.count('<p>') == 2

    def test_format_includes_css(self) -> None:
        """CSS styles are included in output."""
        content = "Test content"
        result = format_story_content(content)

        assert '<style>' in result
        assert 'line-height' in result
        assert 'font-size' in result


@pytest.mark.unit
class TestFormatMetadataContent:
    """Test format_metadata_content function."""

    def test_format_with_category(self) -> None:
        """Metadata includes category."""
        result = format_metadata_content(category="Romance")

        assert 'Romance' in result
        assert 'Category:' in result

    def test_format_with_tags(self) -> None:
        """Metadata includes tags."""
        result = format_metadata_content(tags=["love", "drama", "comedy"])

        assert 'love, drama, comedy' in result
        assert 'Tags:' in result

    def test_format_with_both(self) -> None:
        """Metadata includes both category and tags."""
        result = format_metadata_content(category="Romance", tags=["love", "passion"])

        assert 'Romance' in result
        assert 'love, passion' in result

    def test_format_with_neither(self) -> None:
        """Metadata page created even without category or tags."""
        result = format_metadata_content()

        assert 'Story Information' in result
        assert '<style>' in result


@pytest.mark.unit
class TestCreateEpubFile:
    """Test create_epub_file function."""

    def test_create_simple_epub(self, temp_dir: Path) -> None:
        """Create basic EPUB file."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Test Story",
                    story_author="Test Author",
                    story_content="This is a test story content.",
                    output_directory=str(temp_dir)
                )

                assert os.path.exists(epub_path)
                assert epub_path.endswith('.epub')
                assert 'TestStory' in epub_path or 'Test Story' in epub_path

    def test_epub_valid_structure(self, temp_dir: Path) -> None:
        """Created EPUB has valid structure."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Valid Structure Test",
                    story_author="Author",
                    story_content="Content here.",
                    output_directory=str(temp_dir)
                )

                book = epub.read_epub(epub_path)
                assert book.title == "Valid Structure Test"
                assert len(book.get_metadata('DC', 'creator')) > 0

    def test_epub_with_metadata(self, temp_dir: Path) -> None:
        """EPUB includes category and tags metadata."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Metadata Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir),
                    story_category="Romance",
                    story_tags=["love", "drama"]
                )

                book = epub.read_epub(epub_path)
                subjects = book.get_metadata('DC', 'subject')
                subject_values = [s[0] for s in subjects]

                assert 'Romance' in subject_values
                assert 'love' in subject_values
                assert 'drama' in subject_values

    def test_epub_multi_chapter(self, temp_dir: Path) -> None:
        """EPUB with multiple chapters."""
        content = "Introduction text.\n\nChapter 1\n\nFirst chapter content.\n\nChapter 2\n\nSecond chapter content."

        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Multi Chapter",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                book = epub.read_epub(epub_path)
                items = list(book.get_items())
                html_items = [item for item in items if isinstance(item, epub.EpubHtml)]

                assert len(html_items) >= 3

    def test_epub_with_cover_image(self, temp_dir: Path) -> None:
        """EPUB includes cover image."""
        cover_path = temp_dir / "cover.jpg"
        cover_path.write_bytes(b'\xFF\xD8\xFF\xE0')

        with patch('app.services.epub_generator.send_notification'):
            epub_path = create_epub_file(
                story_title="Cover Test",
                story_author="Author",
                story_content="Content",
                output_directory=str(temp_dir),
                cover_image_path=str(cover_path)
            )

            book = epub.read_epub(epub_path)
            cover_item = None
            for item in book.get_items():
                if item.get_name() == 'cover.jpg':
                    cover_item = item
                    break

            assert cover_item is not None

    def test_epub_generates_cover_if_not_provided(self, temp_dir: Path) -> None:
        """Cover is generated if not provided."""
        with patch('app.services.epub_generator.generate_cover_image') as mock_gen:
            with patch('app.services.epub_generator.send_notification'):
                with patch('app.services.epub_generator.get_cover_directory', return_value=str(temp_dir)):
                    def fake_cover(title, author, path):
                        Path(path).write_bytes(b'\xFF\xD8\xFF\xE0')

                    mock_gen.side_effect = fake_cover

                    epub_path = create_epub_file(
                        story_title="Auto Cover",
                        story_author="Author",
                        story_content="Content",
                        output_directory=str(temp_dir)
                    )

                    mock_gen.assert_called_once()
                    assert os.path.exists(epub_path)

    def test_epub_sanitizes_filename(self, temp_dir: Path) -> None:
        """Filename is sanitized for filesystem safety."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Test/Story:With<Special>Characters",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                assert os.path.exists(epub_path)
                assert '/' not in os.path.basename(epub_path)
                assert ':' not in os.path.basename(epub_path)
                assert '<' not in os.path.basename(epub_path)

    def test_epub_unicode_title(self, temp_dir: Path) -> None:
        """Unicode characters in title are handled."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Histoire d'Amour 爱情故事",
                    story_author="Author",
                    story_content="Content with unicode: 你好世界",
                    output_directory=str(temp_dir)
                )

                book = epub.read_epub(epub_path)
                assert "Histoire d'Amour 爱情故事" in book.title

    def test_epub_empty_content_raises(self, temp_dir: Path) -> None:
        """Empty content raises error."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                with pytest.raises(ValueError, match="No valid chapters"):
                    create_epub_file(
                        story_title="Empty",
                        story_author="Author",
                        story_content="",
                        output_directory=str(temp_dir)
                    )

    def test_epub_chapter_title_extraction(self, temp_dir: Path) -> None:
        """Chapter titles are extracted correctly."""
        content = "Intro\n\nChapter One: The Beginning\n\nChapter one content."

        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Chapter Titles",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                book = epub.read_epub(epub_path)
                assert len(book.toc) >= 2

    def test_epub_creates_output_directory(self, temp_dir: Path) -> None:
        """Output directory is created if it doesn't exist."""
        nested_dir = temp_dir / "nested" / "output"

        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Nested Dir Test",
                    story_author="Author",
                    story_content="Content",
                    output_directory=str(nested_dir)
                )

                assert os.path.exists(epub_path)
                assert os.path.exists(nested_dir)

    def test_epub_sends_notification_on_success(self, temp_dir: Path) -> None:
        """Notification sent on successful creation."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification') as mock_notify:
                create_epub_file(
                    story_title="Notify Test",
                    story_author="Test Author",
                    story_content="Content",
                    output_directory=str(temp_dir)
                )

                mock_notify.assert_called_once()
                call_args = mock_notify.call_args[0][0]
                assert 'Notify Test' in call_args
                assert 'Test Author' in call_args

    def test_epub_sends_error_notification_on_failure(self, temp_dir: Path) -> None:
        """Error notification sent on failure."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification') as mock_notify:
                with patch('app.services.epub_generator.epub.write_epub', side_effect=Exception("Write failed")):
                    with pytest.raises(Exception):
                        create_epub_file(
                            story_title="Fail Test",
                            story_author="Author",
                            story_content="Content",
                            output_directory=str(temp_dir)
                        )

                    error_calls = [call for call in mock_notify.call_args_list if len(call[1]) > 0 and call[1].get('is_error')]
                    assert len(error_calls) > 0

    def test_epub_metadata_chapter_included(self, temp_dir: Path) -> None:
        """Metadata chapter is included when category/tags provided."""
        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Metadata Chapter",
                    story_author="Author",
                    story_content="Story content",
                    output_directory=str(temp_dir),
                    story_category="Fantasy",
                    story_tags=["magic"]
                )

                book = epub.read_epub(epub_path)
                items = list(book.get_items())

                metadata_found = False
                for item in items:
                    if isinstance(item, epub.EpubHtml) and 'metadata' in item.get_name():
                        metadata_found = True
                        content = item.get_content().decode('utf-8')
                        assert 'Fantasy' in content
                        assert 'magic' in content
                        break

                assert metadata_found

    def test_epub_handles_missing_cover_gracefully(self, temp_dir: Path) -> None:
        """EPUB creation continues if cover image is missing."""
        fake_cover_path = str(temp_dir / "nonexistent-cover.jpg")

        with patch('app.services.epub_generator.send_notification'):
            epub_path = create_epub_file(
                story_title="Missing Cover",
                story_author="Author",
                story_content="Content",
                output_directory=str(temp_dir),
                cover_image_path=fake_cover_path
            )

            assert os.path.exists(epub_path)

    def test_epub_introduction_chapter_created(self, temp_dir: Path) -> None:
        """Introduction chapter created for pre-chapter content."""
        content = "This is introduction text before chapters.\n\nChapter 1\n\nFirst chapter."

        with patch('app.services.epub_generator.generate_cover_image'):
            with patch('app.services.epub_generator.send_notification'):
                epub_path = create_epub_file(
                    story_title="Intro Chapter",
                    story_author="Author",
                    story_content=content,
                    output_directory=str(temp_dir)
                )

                book = epub.read_epub(epub_path)
                items = list(book.get_items())
                intro_found = False

                for item in items:
                    if isinstance(item, epub.EpubHtml) and 'intro' in item.get_name():
                        intro_found = True
                        break

                assert intro_found
