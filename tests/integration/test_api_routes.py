from __future__ import annotations
import pytest
import json
import os
from pathlib import Path
from flask.testing import FlaskClient
from flask import Flask
from unittest.mock import patch, MagicMock
from app.services.story_processor import StoryProcessingResult


@pytest.mark.integration
class TestDownloadEndpoint:
    """Test /api/download endpoint with GET and POST requests."""

    def test_download_get_with_url(self, client: FlaskClient) -> None:
        """GET /api/download with URL parameter."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Story downloaded successfully",
                title="Test Story",
                author="Test Author",
                formats=["epub"],
                files=["test-story.epub"]
            )

            response = client.get('/api/download?url=https://www.literotica.com/s/test-story')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'
            assert data['title'] == 'Test Story'
            mock_download.assert_called_once()

    def test_download_get_with_format_param(self, client: FlaskClient) -> None:
        """GET /api/download with format parameter (comma-separated)."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Story downloaded",
                formats=["epub", "html"],
                files=["test.epub", "test.html"]
            )

            response = client.get('/api/download?url=https://www.literotica.com/s/test&format=epub,html')

            assert response.status_code == 200
            args, kwargs = mock_download.call_args
            assert 'epub' in args[1]
            assert 'html' in args[1]

    def test_download_post_json(self, client: FlaskClient) -> None:
        """POST /api/download with JSON body."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Downloaded",
                formats=["epub"],
                files=["story.epub"]
            )

            response = client.post(
                '/api/download',
                json={
                    'url': 'https://www.literotica.com/s/test-story',
                    'format': ['epub']
                },
                content_type='application/json'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'

    def test_download_post_form_data(self, client: FlaskClient) -> None:
        """POST /api/download with form data."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Downloaded"
            )

            response = client.post(
                '/api/download',
                data={
                    'url': 'https://www.literotica.com/s/test-story',
                    'format': 'epub'
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'

    def test_download_post_multiple_formats(self, client: FlaskClient) -> None:
        """POST /api/download with multiple formats."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Both formats created",
                formats=["epub", "html"],
                files=["test.epub", "test.html"]
            )

            response = client.post(
                '/api/download',
                json={
                    'url': 'https://www.literotica.com/s/test',
                    'format': ['epub', 'html']
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'
            assert 'formats' in data
            assert 'files' in data

    def test_download_validation_error_empty_url(self, client: FlaskClient) -> None:
        """Empty URL returns 400 validation error."""
        response = client.post('/api/download', json={'url': ''})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] == 'false'
        assert 'url' in data['message'].lower()

    def test_download_validation_error_invalid_domain(self, client: FlaskClient) -> None:
        """Non-Literotica URL returns 400 validation error."""
        response = client.post(
            '/api/download',
            json={'url': 'https://www.example.com/story'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] == 'false'

    def test_download_validation_error_invalid_format(self, client: FlaskClient) -> None:
        """Invalid format returns 400 validation error."""
        response = client.post(
            '/api/download',
            json={
                'url': 'https://www.literotica.com/s/test',
                'format': ['pdf']
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] == 'false'

    def test_download_wait_false_async(self, client: FlaskClient) -> None:
        """wait=false triggers background processing."""
        with patch('app.blueprints.api.routes.threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            response = client.post(
                '/api/download',
                json={
                    'url': 'https://www.literotica.com/s/test',
                    'wait': False
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'
            assert 'background' in data['message'].lower()
            mock_thread_instance.start.assert_called_once()

    def test_download_wait_string_parsing(self, client: FlaskClient) -> None:
        """wait parameter as string 'false' is parsed correctly."""
        with patch('app.blueprints.api.routes.threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            response = client.post(
                '/api/download',
                json={
                    'url': 'https://www.literotica.com/s/test',
                    'wait': 'false'
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert 'background' in data['message'].lower()

    def test_download_get_method_with_params(self, client: FlaskClient) -> None:
        """GET method parses query parameters correctly."""
        with patch('app.blueprints.api.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(success=True, message="OK")

            response = client.get(
                '/api/download?url=https://www.literotica.com/s/test&wait=true&format=epub'
            )

            assert response.status_code == 200
            args = mock_download.call_args[0]
            assert args[0] == 'https://www.literotica.com/s/test'
            assert 'epub' in args[1]


@pytest.mark.integration
class TestLibraryEndpoint:
    """Test /api/library endpoint."""

    def test_library_get_empty(self, client: FlaskClient) -> None:
        """Empty library returns empty array."""
        response = client.get('/api/library')

        assert response.status_code == 200
        data = response.get_json()
        assert 'stories' in data
        assert isinstance(data['stories'], list)
        assert len(data['stories']) == 0

    def test_library_get_with_epub_only(self, client: FlaskClient, app: Flask, temp_dir: Path) -> None:
        """Library with EPUB file only."""
        with app.app_context():
            from app.utils import get_epub_directory
            epub_dir = get_epub_directory()

            test_epub = Path(epub_dir) / "test-story.epub"
            test_epub.write_text("fake epub content")

            response = client.get('/api/library')

            assert response.status_code == 200
            data = response.get_json()
            assert len(data['stories']) == 1
            assert data['stories'][0]['filename_base'] == 'test-story'
            assert 'epub' in data['stories'][0]['formats']

    def test_library_get_with_json_metadata(self, client: FlaskClient, app: Flask) -> None:
        """Library reads JSON metadata for display info."""
        with app.app_context():
            from app.utils import get_html_directory
            html_dir = get_html_directory()

            json_path = Path(html_dir) / "test-story.json"
            json_path.write_text(json.dumps({
                'title': 'Test Story Title',
                'author': 'Test Author',
                'category': 'Romance',
                'tags': ['love', 'drama'],
                'cover': 'test-story.jpg'
            }))

            response = client.get('/api/library')

            assert response.status_code == 200
            data = response.get_json()
            assert len(data['stories']) == 1
            story = data['stories'][0]
            assert story['title'] == 'Test Story Title'
            assert story['author'] == 'Test Author'
            assert story['category'] == 'Romance'
            assert story['tags'] == ['love', 'drama']
            assert story['cover'] == 'test-story.jpg'

    def test_library_json_structure(self, client: FlaskClient, app: Flask) -> None:
        """Library JSON has correct structure."""
        with app.app_context():
            from app.utils import get_epub_directory, get_html_directory

            epub_path = Path(get_epub_directory()) / "story.epub"
            epub_path.write_text("epub")

            json_path = Path(get_html_directory()) / "story.json"
            json_path.write_text(json.dumps({
                'title': 'Story',
                'author': 'Author'
            }))

            response = client.get('/api/library')

            assert response.status_code == 200
            data = response.get_json()
            assert 'stories' in data
            story = data['stories'][0]
            assert 'filename_base' in story
            assert 'title' in story
            assert 'formats' in story
            assert 'created_at' in story
            assert isinstance(story['formats'], list)

    def test_library_sorts_by_date_descending(self, client: FlaskClient, app: Flask) -> None:
        """Library returns stories sorted by creation date (newest first)."""
        import time
        with app.app_context():
            from app.utils import get_epub_directory
            epub_dir = Path(get_epub_directory())

            old_story = epub_dir / "old-story.epub"
            old_story.write_text("old")

            time.sleep(0.1)

            new_story = epub_dir / "new-story.epub"
            new_story.write_text("new")

            response = client.get('/api/library')

            data = response.get_json()
            assert len(data['stories']) == 2
            assert data['stories'][0]['filename_base'] == 'new-story'
            assert data['stories'][1]['filename_base'] == 'old-story'

    def test_library_handles_both_formats(self, client: FlaskClient, app: Flask) -> None:
        """Library shows story with both EPUB and HTML formats."""
        with app.app_context():
            from app.utils import get_epub_directory, get_html_directory

            epub_path = Path(get_epub_directory()) / "dual-format.epub"
            epub_path.write_text("epub")

            json_path = Path(get_html_directory()) / "dual-format.json"
            json_path.write_text(json.dumps({'title': 'Dual Format Story'}))

            response = client.get('/api/library')

            data = response.get_json()
            assert len(data['stories']) == 1
            story = data['stories'][0]
            assert 'epub' in story['formats']
            assert 'html' in story['formats']
            assert 'epub_file' in story
            assert 'html_file' in story


@pytest.mark.integration
class TestCoverEndpoint:
    """Test /api/cover/<filename> endpoint."""

    def test_cover_path_traversal_blocked(self, client: FlaskClient) -> None:
        """Path traversal attempts are blocked."""
        response = client.get('/api/cover/../../../etc/passwd')
        assert response.status_code == 404

    def test_cover_double_dot_blocked(self, client: FlaskClient) -> None:
        """Double-dot path traversal blocked."""
        response = client.get('/api/cover/..%2F..%2Fetc%2Fpasswd')
        assert response.status_code == 404

    def test_cover_absolute_path_blocked(self, client: FlaskClient) -> None:
        """Absolute path blocked."""
        response = client.get('/api/cover//etc/passwd')
        assert response.status_code == 404

    def test_cover_non_jpg_extension_rejected(self, client: FlaskClient) -> None:
        """Non-.jpg files are rejected."""
        response = client.get('/api/cover/test-story.png')
        assert response.status_code == 404

    def test_cover_returns_existing_file(self, client: FlaskClient, app: Flask) -> None:
        """Existing cover image is returned."""
        with app.app_context():
            from app.utils import get_cover_directory
            cover_dir = Path(get_cover_directory())

            cover_path = cover_dir / "test-story.jpg"
            fake_jpg = b'\xFF\xD8\xFF\xE0\x00\x10\x4A\x46\x49\x46'
            cover_path.write_bytes(fake_jpg)

            response = client.get('/api/cover/test-story.jpg')

            assert response.status_code == 200
            assert 'image/jpeg' in response.content_type

    def test_cover_generates_if_missing(self, client: FlaskClient, app: Flask) -> None:
        """Cover is generated if not found."""
        with app.app_context():
            from app.utils import get_html_directory, get_cover_directory

            json_path = Path(get_html_directory()) / "new-story.json"
            json_path.write_text(json.dumps({
                'title': 'New Story',
                'author': 'Author Name'
            }))

            with patch('app.services.generate_cover_image') as mock_generate:
                def create_fake_cover(title, author, output_path):
                    Path(output_path).write_bytes(b'\xFF\xD8\xFF\xE0')

                mock_generate.side_effect = create_fake_cover

                response = client.get('/api/cover/new-story.jpg')

                assert response.status_code == 200
                mock_generate.assert_called_once()
                args = mock_generate.call_args[0]
                assert args[0] == 'New Story'
                assert args[1] == 'Author Name'

    def test_cover_extracts_from_epub_if_available(self, client: FlaskClient, app: Flask) -> None:
        """Cover is extracted from EPUB if available."""
        with app.app_context():
            from app.utils import get_epub_directory, get_cover_directory

            epub_path = Path(get_epub_directory()) / "with-cover.epub"
            epub_path.write_text("fake epub with embedded cover")

            with patch('app.services.extract_cover_from_epub') as mock_extract:
                def extract_and_create(epub_path, cover_path):
                    Path(cover_path).write_bytes(b'\xFF\xD8\xFF\xE0')
                    return True

                mock_extract.side_effect = extract_and_create

                response = client.get('/api/cover/with-cover.jpg')

                assert response.status_code == 200
                mock_extract.assert_called_once()

    def test_cover_uses_metadata_from_json(self, client: FlaskClient, app: Flask) -> None:
        """Cover generation uses title/author from JSON metadata."""
        with app.app_context():
            from app.utils import get_html_directory

            json_path = Path(get_html_directory()) / "metadata-story.json"
            json_path.write_text(json.dumps({
                'title': 'Metadata Story Title',
                'author': 'Metadata Author'
            }))

            with patch('app.services.generate_cover_image') as mock_gen:
                def create_fake_cover(title, author, output_path):
                    Path(output_path).write_bytes(b'\xFF\xD8\xFF\xE0')

                mock_gen.side_effect = create_fake_cover

                response = client.get('/api/cover/metadata-story.jpg')

                assert response.status_code == 200
                mock_gen.assert_called_once()
                assert mock_gen.call_args[0][0] == 'Metadata Story Title'
                assert mock_gen.call_args[0][1] == 'Metadata Author'

    def test_cover_fallback_to_filename_if_no_metadata(self, client: FlaskClient, app: Flask) -> None:
        """Cover uses filename as title if no metadata available."""
        with patch('app.services.generate_cover_image') as mock_gen:
            def create_fake_cover(title, author, output_path):
                Path(output_path).write_bytes(b'\xFF\xD8\xFF\xE0')

            mock_gen.side_effect = create_fake_cover

            response = client.get('/api/cover/no-metadata.jpg')

            assert response.status_code == 200
            mock_gen.assert_called_once()
            assert mock_gen.call_args[0][0] == 'no-metadata'
            assert mock_gen.call_args[0][1] == 'Unknown Author'

    def test_cover_error_handling(self, client: FlaskClient) -> None:
        """Cover generation error returns 500."""
        with patch('app.services.generate_cover_image') as mock_gen:
            mock_gen.side_effect = Exception("Cover generation failed")

            response = client.get('/api/cover/error-story.jpg')

            assert response.status_code == 500
