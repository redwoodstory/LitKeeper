from __future__ import annotations
import pytest
from pathlib import Path
from flask.testing import FlaskClient
from flask import Flask


@pytest.mark.integration
class TestDownloadFile:
    """Test /download/<filename> endpoint."""

    def test_download_epub_sends_file(self, client: FlaskClient, app: Flask) -> None:
        """EPUB file download works."""
        with app.app_context():
            from app.utils import get_epub_directory

            epub_path = Path(get_epub_directory()) / "test-story.epub"
            epub_content = b'PK\x03\x04fake epub content'
            epub_path.write_bytes(epub_content)

            response = client.get('/download/test-story.epub')

            assert response.status_code == 200
            assert response.data == epub_content

    def test_download_html_sends_file(self, client: FlaskClient, app: Flask) -> None:
        """HTML file download works."""
        with app.app_context():
            from app.utils import get_html_directory

            html_path = Path(get_html_directory()) / "test-story.html"
            html_content = b'<html><body>Test Story Content</body></html>'
            html_path.write_bytes(html_content)

            response = client.get('/download/test-story.html')

            assert response.status_code == 200
            assert response.data == html_content

    def test_download_correct_mimetype_epub(self, client: FlaskClient, app: Flask) -> None:
        """EPUB download has correct content type."""
        with app.app_context():
            from app.utils import get_epub_directory

            epub_path = Path(get_epub_directory()) / "story.epub"
            epub_path.write_bytes(b'fake epub')

            response = client.get('/download/story.epub')

            assert response.status_code == 200
            assert 'application' in response.content_type.lower() or 'octet-stream' in response.content_type.lower()

    def test_download_correct_mimetype_html(self, client: FlaskClient, app: Flask) -> None:
        """HTML download has correct content type."""
        with app.app_context():
            from app.utils import get_html_directory

            html_path = Path(get_html_directory()) / "story.html"
            html_path.write_bytes(b'<html></html>')

            response = client.get('/download/story.html')

            assert response.status_code == 200
            assert 'html' in response.content_type.lower() or 'octet-stream' in response.content_type.lower()

    def test_download_as_attachment(self, client: FlaskClient, app: Flask) -> None:
        """Downloads use attachment disposition."""
        with app.app_context():
            from app.utils import get_epub_directory

            epub_path = Path(get_epub_directory()) / "attachment-test.epub"
            epub_path.write_bytes(b'test')

            response = client.get('/download/attachment-test.epub')

            assert response.status_code == 200
            assert 'attachment' in response.headers.get('Content-Disposition', '').lower()

    def test_download_path_traversal_blocked(self, client: FlaskClient) -> None:
        """Path traversal with .. is blocked."""
        response = client.get('/download/../../../etc/passwd')

        assert response.status_code == 404

    def test_download_relative_path_blocked(self, client: FlaskClient) -> None:
        """Relative path traversal blocked."""
        response = client.get('/download/../../app/__init__.py')

        assert response.status_code == 404

    def test_download_absolute_path_blocked(self, client: FlaskClient) -> None:
        """Absolute paths are blocked."""
        response = client.get('/download//etc/passwd')

        assert response.status_code == 404

    def test_download_invalid_extension_rejected(self, client: FlaskClient) -> None:
        """Invalid file extensions return 404."""
        response = client.get('/download/story.txt')

        assert response.status_code == 404

    def test_download_pdf_extension_rejected(self, client: FlaskClient) -> None:
        """PDF files are not allowed."""
        response = client.get('/download/story.pdf')

        assert response.status_code == 404

    def test_download_missing_epub_file(self, client: FlaskClient) -> None:
        """Missing EPUB file returns 404."""
        response = client.get('/download/nonexistent-story.epub')

        assert response.status_code == 404

    def test_download_missing_html_file(self, client: FlaskClient) -> None:
        """Missing HTML file returns 404."""
        response = client.get('/download/nonexistent-story.html')

        assert response.status_code == 404
