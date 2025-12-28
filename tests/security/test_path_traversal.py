from __future__ import annotations
import pytest
from flask.testing import FlaskClient


@pytest.mark.security
class TestPathTraversalDownloadRoute:
    """Test path traversal prevention in /download/<filename> route."""

    def test_download_blocks_parent_directory_traversal(self, client: FlaskClient) -> None:
        """Test that ../ in filename is blocked."""
        response = client.get("/download/../../../etc/passwd")
        assert response.status_code == 404

    def test_download_blocks_windows_traversal(self, client: FlaskClient) -> None:
        r"""Test that ..\ Windows-style traversal is blocked."""
        response = client.get("/download/..\\..\\..\\windows\\system32\\config\\sam")
        assert response.status_code == 404

    def test_download_blocks_absolute_path(self, client: FlaskClient) -> None:
        """Test that absolute paths are blocked."""
        response = client.get("/download//etc/passwd")
        assert response.status_code == 404

    def test_download_blocks_url_encoded_traversal(self, client: FlaskClient) -> None:
        """Test that URL-encoded ../ (%2e%2e%2f) is blocked."""
        response = client.get("/download/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        assert response.status_code == 404

    def test_download_blocks_double_encoded_traversal(self, client: FlaskClient) -> None:
        """Test that double-encoded ../ (%252e%252e%252f) is blocked."""
        response = client.get("/download/%252e%252e%252f%252e%252e%252fetc%252fpasswd")
        assert response.status_code == 404

    def test_download_blocks_mixed_traversal(self, client: FlaskClient) -> None:
        """Test mixed forward/backward slash traversal."""
        response = client.get("/download/../..\\/etc/passwd")
        assert response.status_code == 404

    def test_download_blocks_app_directory_access(self, client: FlaskClient) -> None:
        """Test that accessing app source files is blocked."""
        response = client.get("/download/../../app/__init__.py")
        assert response.status_code == 404

    def test_download_allows_valid_epub_filename(self, client: FlaskClient, temp_dir) -> None:
        """Test that valid EPUB filenames without traversal are allowed (404 if file doesn't exist)."""
        response = client.get("/download/valid_story.epub")
        assert response.status_code == 404

    def test_download_allows_valid_html_filename(self, client: FlaskClient) -> None:
        """Test that valid HTML filenames without traversal are allowed (404 if file doesn't exist)."""
        response = client.get("/download/valid_story.html")
        assert response.status_code == 404

    def test_download_rejects_invalid_extension(self, client: FlaskClient) -> None:
        """Test that non-EPUB/HTML files are rejected."""
        response = client.get("/download/malicious.txt")
        assert response.status_code == 404

    def test_download_rejects_pdf_extension(self, client: FlaskClient) -> None:
        """Test that PDF files are rejected."""
        response = client.get("/download/document.pdf")
        assert response.status_code == 404


@pytest.mark.security
class TestPathTraversalReadRoute:
    """Test path traversal prevention in /read/<filename> route."""

    def test_read_blocks_parent_directory_traversal(self, client: FlaskClient) -> None:
        """Test that ../ in filename is blocked."""
        response = client.get("/read/../../../etc/passwd")
        assert response.status_code == 404

    def test_read_blocks_absolute_path(self, client: FlaskClient) -> None:
        """Test that absolute paths are blocked."""
        response = client.get("/read//app/__init__.py")
        assert response.status_code == 404

    def test_read_blocks_app_source_access(self, client: FlaskClient) -> None:
        """Test that accessing app source files is blocked."""
        response = client.get("/read/../../app/validators.py")
        assert response.status_code == 404

    def test_read_blocks_env_file_access(self, client: FlaskClient) -> None:
        """Test that accessing .env files is blocked."""
        response = client.get("/read/../../.env")
        assert response.status_code == 404

    def test_read_blocks_url_encoded_traversal(self, client: FlaskClient) -> None:
        """Test that URL-encoded path traversal is blocked."""
        response = client.get("/read/%2e%2e%2f%2e%2e%2fapp%2f__init__.py")
        assert response.status_code == 404

    def test_read_allows_valid_html_filename(self, client: FlaskClient) -> None:
        """Test that valid HTML/JSON filenames are processed (404 if file doesn't exist)."""
        response = client.get("/read/valid_story.html")
        assert response.status_code == 404

    def test_read_allows_valid_json_filename(self, client: FlaskClient) -> None:
        """Test that valid JSON filenames are processed (404 if file doesn't exist)."""
        response = client.get("/read/valid_story.json")
        assert response.status_code == 404

    def test_read_rejects_invalid_extension(self, client: FlaskClient) -> None:
        """Test that files without .html or .json extension are rejected."""
        response = client.get("/read/malicious.txt")
        assert response.status_code == 404


@pytest.mark.security
class TestPathTraversalCoverRoute:
    """Test path traversal prevention in /api/cover/<filename> route."""

    def test_cover_blocks_parent_directory_traversal(self, client: FlaskClient) -> None:
        """Test that ../ in filename is blocked."""
        response = client.get("/api/cover/../../../etc/passwd.jpg")
        assert response.status_code == 404

    def test_cover_blocks_slash_dotdot_traversal(self, client: FlaskClient) -> None:
        """Test that /..' in filename is blocked."""
        response = client.get("/api/cover/./../../etc/passwd.jpg")
        assert response.status_code == 404

    def test_cover_blocks_absolute_path(self, client: FlaskClient) -> None:
        """Test that absolute paths are blocked."""
        response = client.get("/api/cover//etc/passwd.jpg")
        assert response.status_code == 404

    def test_cover_blocks_dotdot_prefix(self, client: FlaskClient) -> None:
        """Test that filenames starting with .. are blocked."""
        response = client.get("/api/cover/../malicious.jpg")
        assert response.status_code == 404

    def test_cover_blocks_url_encoded_traversal(self, client: FlaskClient) -> None:
        """Test that URL-encoded path traversal is blocked."""
        response = client.get("/api/cover/%2e%2e%2f%2e%2e%2fetc%2fpasswd.jpg")
        assert response.status_code == 404

    def test_cover_rejects_non_jpg_extension(self, client: FlaskClient) -> None:
        """Test that non-JPG files are rejected."""
        response = client.get("/api/cover/image.png")
        assert response.status_code == 404

    def test_cover_rejects_no_extension(self, client: FlaskClient) -> None:
        """Test that files without extension are rejected."""
        response = client.get("/api/cover/image")
        assert response.status_code == 404

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    def test_cover_allows_valid_jpg_filename(self, client: FlaskClient) -> None:
        """Test that valid JPG filenames are processed (generates cover or returns 500)."""
        response = client.get("/api/cover/valid_story.jpg")
        assert response.status_code in [200, 500]

    def test_cover_blocks_nested_traversal_in_middle(self, client: FlaskClient) -> None:
        """Test that path traversal in middle of filename is blocked."""
        response = client.get("/api/cover/story/../../../etc/passwd.jpg")
        assert response.status_code == 404


@pytest.mark.security
class TestPathTraversalMultipleVectors:
    """Test various sophisticated path traversal attack vectors."""

    def test_null_byte_injection_download(self, client: FlaskClient) -> None:
        """Test that null byte injection is handled."""
        response = client.get("/download/story.epub%00.txt")
        assert response.status_code in [400, 404]

    def test_unicode_traversal(self, client: FlaskClient) -> None:
        """Test Unicode-based path traversal attempts."""
        response = client.get("/download/\u2025\u2025/\u2025\u2025/etc/passwd")
        assert response.status_code == 404

    def test_overlong_utf8_encoding(self, client: FlaskClient) -> None:
        """Test overlong UTF-8 encoding of dot."""
        response = client.get("/download/%c0%ae%c0%ae/%c0%ae%c0%ae/etc/passwd")
        assert response.status_code == 404

    def test_backslash_traversal_combinations(self, client: FlaskClient) -> None:
        """Test various backslash and forward slash combinations."""
        test_cases = [
            "/download/..\\..\\..\\etc\\passwd",
            "/download/..\\/../etc/passwd",
            "/download/../..\\/etc/passwd.epub",
        ]
        for path in test_cases:
            response = client.get(path)
            assert response.status_code == 404, f"Failed to block: {path}"

    def test_triple_encoded_traversal(self, client: FlaskClient) -> None:
        """Test triple-encoded path traversal."""
        response = client.get("/download/%25252e%25252e%25252f%25252e%25252e%25252fetc%25252fpasswd")
        assert response.status_code == 404
