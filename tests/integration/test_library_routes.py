from __future__ import annotations
import pytest
import json
from pathlib import Path
from flask.testing import FlaskClient
from flask import Flask
from unittest.mock import patch, MagicMock
from app.services.story_processor import StoryProcessingResult


@pytest.mark.integration
class TestIndexRoute:
    """Test / (index) route with GET and POST requests."""

    def test_index_get_renders(self, client: FlaskClient) -> None:
        """GET / renders index page successfully."""
        response = client.get('/')

        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data

    def test_index_shows_stories(self, client: FlaskClient, app: Flask) -> None:
        """Index page displays available stories."""
        with app.app_context():
            from app.utils import get_html_directory

            json_path = Path(get_html_directory()) / "test-story.json"
            json_path.write_text(json.dumps({
                'title': 'Test Story',
                'author': 'Test Author'
            }))

            response = client.get('/')

            assert response.status_code == 200
            assert b'Test Story' in response.data

    def test_index_post_download(self, client: FlaskClient) -> None:
        """POST / triggers story download."""
        with patch('app.blueprints.library.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Downloaded successfully",
                title="New Story",
                formats=["epub"]
            )

            response = client.post(
                '/',
                data={
                    'url': 'https://www.literotica.com/s/test-story',
                    'format': 'epub'
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'
            mock_download.assert_called_once()

    def test_index_validation_error_shown(self, client: FlaskClient) -> None:
        """Validation errors are displayed on index page."""
        response = client.post(
            '/',
            data={'url': ''}
        )

        assert response.status_code == 200
        assert b'url' in response.data.lower()

    def test_index_invalid_url_error(self, client: FlaskClient) -> None:
        """Invalid URL shows error message."""
        response = client.post(
            '/',
            data={'url': 'https://www.example.com/story'}
        )

        assert response.status_code == 200
        assert b'error' in response.data.lower() or b'literotica' in response.data.lower()

    def test_index_multiple_formats(self, client: FlaskClient) -> None:
        """POST / with multiple formats."""
        with patch('app.blueprints.library.routes.download_story_and_create_files') as mock_download:
            mock_download.return_value = StoryProcessingResult(
                success=True,
                message="Downloaded",
                formats=["epub", "html"]
            )

            response = client.post(
                '/',
                data={
                    'url': 'https://www.literotica.com/s/test',
                    'format': ['epub', 'html']
                }
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] == 'true'


@pytest.mark.integration
class TestLibraryFilter:
    """Test /library/filter endpoint."""

    def test_filter_search_by_title(self, client: FlaskClient, app: Flask) -> None:
        """Filter stories by title search term."""
        with app.app_context():
            from app.utils import get_html_directory

            story1 = Path(get_html_directory()) / "romance-story.json"
            story1.write_text(json.dumps({
                'title': 'Romance Story',
                'author': 'Author One'
            }))

            story2 = Path(get_html_directory()) / "scifi-story.json"
            story2.write_text(json.dumps({
                'title': 'Sci-Fi Adventure',
                'author': 'Author Two'
            }))

            response = client.get('/library/filter?search=romance')

            assert response.status_code == 200
            assert b'Romance Story' in response.data
            assert b'Sci-Fi Adventure' not in response.data

    def test_filter_search_by_author(self, client: FlaskClient, app: Flask) -> None:
        """Filter stories by author name."""
        with app.app_context():
            from app.utils import get_html_directory

            story1 = Path(get_html_directory()) / "story1.json"
            story1.write_text(json.dumps({
                'title': 'Story One',
                'author': 'John Doe'
            }))

            story2 = Path(get_html_directory()) / "story2.json"
            story2.write_text(json.dumps({
                'title': 'Story Two',
                'author': 'Jane Smith'
            }))

            response = client.get('/library/filter?search=john')

            assert response.status_code == 200
            assert b'Story One' in response.data
            assert b'Story Two' not in response.data

    def test_filter_by_category(self, client: FlaskClient, app: Flask) -> None:
        """Filter stories by category."""
        with app.app_context():
            from app.utils import get_html_directory

            romance = Path(get_html_directory()) / "romance.json"
            romance.write_text(json.dumps({
                'title': 'Romance',
                'category': 'Romance'
            }))

            scifi = Path(get_html_directory()) / "scifi.json"
            scifi.write_text(json.dumps({
                'title': 'SciFi',
                'category': 'Sci-Fi'
            }))

            response = client.get('/library/filter?category=Romance')

            assert response.status_code == 200
            assert b'Romance' in response.data

    def test_filter_uncategorized(self, client: FlaskClient, app: Flask) -> None:
        """Filter for uncategorized stories."""
        with app.app_context():
            from app.utils import get_html_directory

            categorized = Path(get_html_directory()) / "categorized.json"
            categorized.write_text(json.dumps({
                'title': 'Categorized Story',
                'category': 'Romance'
            }))

            uncategorized = Path(get_html_directory()) / "uncategorized.json"
            uncategorized.write_text(json.dumps({
                'title': 'Uncategorized Story'
            }))

            response = client.get('/library/filter?category=uncategorized')

            assert response.status_code == 200
            assert b'Uncategorized Story' in response.data
            assert b'Categorized Story' not in response.data

    def test_filter_view_mode(self, client: FlaskClient, app: Flask) -> None:
        """Filter respects view mode parameter."""
        with app.app_context():
            from app.utils import get_html_directory

            story = Path(get_html_directory()) / "story.json"
            story.write_text(json.dumps({'title': 'Test Story'}))

            response = client.get('/library/filter?view=grid')

            assert response.status_code == 200

    def test_filter_combined(self, client: FlaskClient, app: Flask) -> None:
        """Filter with multiple parameters."""
        with app.app_context():
            from app.utils import get_html_directory

            match = Path(get_html_directory()) / "match.json"
            match.write_text(json.dumps({
                'title': 'Romance Story',
                'author': 'Author',
                'category': 'Romance'
            }))

            no_match = Path(get_html_directory()) / "nomatch.json"
            no_match.write_text(json.dumps({
                'title': 'SciFi Story',
                'author': 'Other',
                'category': 'Sci-Fi'
            }))

            response = client.get('/library/filter?search=romance&category=Romance')

            assert response.status_code == 200
            assert b'Romance Story' in response.data
            assert b'SciFi Story' not in response.data

    def test_filter_case_insensitive_search(self, client: FlaskClient, app: Flask) -> None:
        """Search is case-insensitive."""
        with app.app_context():
            from app.utils import get_html_directory

            story = Path(get_html_directory()) / "story.json"
            story.write_text(json.dumps({
                'title': 'Test Story TITLE',
                'author': 'Author'
            }))

            response = client.get('/library/filter?search=TEST')

            assert response.status_code == 200
            assert b'Test Story' in response.data


@pytest.mark.integration
class TestReadStory:
    """Test /read/<filename> endpoint."""

    def test_read_story_json(self, client: FlaskClient, app: Flask) -> None:
        """Read story from JSON file."""
        with app.app_context():
            from app.utils import get_html_directory

            json_path = Path(get_html_directory()) / "test-story.json"
            json_path.write_text(json.dumps({
                'title': 'Test Story',
                'author': 'Test Author',
                'content': [
                    {'chapter': 'Chapter 1', 'paragraphs': ['Paragraph 1', 'Paragraph 2']}
                ]
            }))

            response = client.get('/read/test-story.json')

            assert response.status_code == 200
            assert b'Test Story' in response.data
            assert b'Test Author' in response.data

    def test_read_story_html_extension(self, client: FlaskClient, app: Flask) -> None:
        """Read story with .html extension loads corresponding JSON."""
        with app.app_context():
            from app.utils import get_html_directory

            json_path = Path(get_html_directory()) / "story.json"
            json_path.write_text(json.dumps({
                'title': 'HTML Story',
                'author': 'Author',
                'content': []
            }))

            response = client.get('/read/story.html')

            assert response.status_code == 200
            assert b'HTML Story' in response.data

    def test_read_story_html_fallback(self, client: FlaskClient, app: Flask) -> None:
        """Falls back to HTML file if JSON doesn't exist."""
        with app.app_context():
            from app.utils import get_html_directory

            html_path = Path(get_html_directory()) / "legacy-story.html"
            html_path.write_text('<html><body>Legacy HTML Story</body></html>')

            response = client.get('/read/legacy-story.html')

            assert response.status_code == 200
            assert b'Legacy HTML Story' in response.data

    def test_read_story_path_traversal_blocked(self, client: FlaskClient) -> None:
        """Path traversal attempts are blocked."""
        response = client.get('/read/../../../etc/passwd')

        assert response.status_code == 404

    def test_read_story_absolute_path_blocked(self, client: FlaskClient) -> None:
        """Absolute paths are blocked."""
        response = client.get('/read//etc/passwd')

        assert response.status_code == 404

    def test_read_story_missing_file(self, client: FlaskClient) -> None:
        """Missing story file returns 404."""
        response = client.get('/read/nonexistent-story.json')

        assert response.status_code == 404

    def test_read_story_invalid_extension(self, client: FlaskClient) -> None:
        """Invalid file extension returns 404."""
        response = client.get('/read/story.txt')

        assert response.status_code == 404

    def test_read_story_malformed_json_error(self, client: FlaskClient, app: Flask) -> None:
        """Malformed JSON file returns 500."""
        with app.app_context():
            from app.utils import get_html_directory

            json_path = Path(get_html_directory()) / "bad-story.json"
            json_path.write_text("{ this is not valid json }")

            response = client.get('/read/bad-story.json')

            assert response.status_code == 500


@pytest.mark.integration
class TestServiceWorker:
    """Test /sw.js service worker endpoint."""

    def test_service_worker_returns_js(self, client: FlaskClient) -> None:
        """Service worker returns JavaScript file."""
        response = client.get('/sw.js')

        assert 'javascript' in response.content_type.lower()
