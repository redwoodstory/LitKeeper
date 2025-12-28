from __future__ import annotations
import pytest
from app.utils.filename import sanitize_filename


@pytest.mark.unit
@pytest.mark.security
class TestFilenameSanitizer:
    """Test security-critical filename sanitization function."""

    def test_sanitize_alphanumeric_filename(self) -> None:
        """Test that normal alphanumeric filenames pass through unchanged."""
        assert sanitize_filename("MyStory123") == "MyStory123"

    def test_sanitize_filename_with_hyphens(self) -> None:
        """Test that hyphens are preserved."""
        assert sanitize_filename("my-story-title") == "my-story-title"

    def test_sanitize_filename_with_underscores(self) -> None:
        """Test that underscores are preserved."""
        assert sanitize_filename("my_story_title") == "my_story_title"

    def test_sanitize_filename_with_dots(self) -> None:
        """Test that dots are preserved (for extensions)."""
        assert sanitize_filename("story.epub") == "story.epub"

    def test_sanitize_removes_spaces(self) -> None:
        """Test that spaces are removed."""
        assert sanitize_filename("My Story Title") == "MyStoryTitle"

    def test_sanitize_removes_special_characters(self) -> None:
        """Test that special characters are removed."""
        assert sanitize_filename("story!@#$%^&*()+=[]{}") == "story"

    def test_sanitize_path_traversal_parent_directory(self) -> None:
        """Test that ../ path traversal is prevented."""
        assert sanitize_filename("../../../etc/passwd") == "etcpasswd"

    def test_sanitize_path_traversal_windows(self) -> None:
        """Test that Windows-style path traversal is prevented."""
        assert sanitize_filename("..\\..\\..\\windows\\system32") == "windowssystem32"

    def test_sanitize_absolute_path_unix(self) -> None:
        """Test that Unix absolute paths are sanitized."""
        assert sanitize_filename("/etc/passwd") == "etcpasswd"

    def test_sanitize_absolute_path_windows(self) -> None:
        """Test that Windows absolute paths are sanitized."""
        assert sanitize_filename("C:\\Windows\\System32") == "CWindowsSystem32"

    def test_sanitize_removes_slashes(self) -> None:
        """Test that forward and backward slashes are removed."""
        assert sanitize_filename("path/to/file") == "pathtofile"
        assert sanitize_filename("path\\to\\file") == "pathtofile"

    def test_sanitize_removes_colon(self) -> None:
        """Test that colons are removed (Windows drive letters)."""
        assert sanitize_filename("C:file.txt") == "Cfile.txt"

    def test_sanitize_removes_angle_brackets(self) -> None:
        """Test that angle brackets are removed (HTML/XSS)."""
        assert sanitize_filename("<script>alert('xss')</script>") == "scriptalertxssscript"

    def test_sanitize_removes_quotes(self) -> None:
        """Test that quotes are removed."""
        assert sanitize_filename('story"with\'quotes') == "storywithquotes"

    def test_sanitize_removes_pipes(self) -> None:
        """Test that pipe characters are removed (shell injection)."""
        assert sanitize_filename("file|rm -rf /") == "filerm-rf"

    def test_sanitize_removes_ampersand(self) -> None:
        """Test that ampersands are removed (shell commands)."""
        assert sanitize_filename("file&command") == "filecommand"

    def test_sanitize_removes_semicolon(self) -> None:
        """Test that semicolons are removed (shell commands)."""
        assert sanitize_filename("file;rm -rf /") == "filerm-rf"

    def test_sanitize_null_byte_injection(self) -> None:
        """Test that null bytes are removed."""
        assert sanitize_filename("file.epub\x00.txt") == "file.epub.txt"

    def test_sanitize_leading_dots_removed(self) -> None:
        """Test that leading dots are removed (hidden files)."""
        assert sanitize_filename(".htaccess") == "htaccess"
        assert sanitize_filename("..hidden") == "hidden"

    def test_sanitize_trailing_dots_removed(self) -> None:
        """Test that trailing dots are removed (Windows compatibility)."""
        assert sanitize_filename("file.txt.") == "file.txt"
        assert sanitize_filename("file...") == "file"

    def test_sanitize_unicode_characters(self) -> None:
        """Test that Unicode characters are removed."""
        assert sanitize_filename("story_你好_test") == "story__test"
        assert sanitize_filename("café") == "caf"

    def test_sanitize_emoji(self) -> None:
        """Test that emoji are removed."""
        assert sanitize_filename("story_🔥_title") == "story__title"

    def test_sanitize_rtl_characters(self) -> None:
        """Test that right-to-left Unicode characters are removed."""
        assert sanitize_filename("story_\u202e_test") == "story__test"

    def test_sanitize_zero_width_characters(self) -> None:
        """Test that zero-width characters are removed."""
        assert sanitize_filename("sto\u200bry") == "story"

    def test_sanitize_newlines_and_tabs(self) -> None:
        """Test that newlines and tabs are removed."""
        assert sanitize_filename("story\n\t\rfile") == "storyfile"

    def test_sanitize_empty_string(self) -> None:
        """Test that empty string is handled."""
        assert sanitize_filename("") == ""

    def test_sanitize_only_special_characters(self) -> None:
        """Test that filenames with only special characters become empty."""
        assert sanitize_filename("@#$%^&*()") == ""

    def test_sanitize_only_spaces(self) -> None:
        """Test that filenames with only spaces become empty."""
        assert sanitize_filename("    ") == ""

    def test_sanitize_only_dots(self) -> None:
        """Test that filenames with only dots become empty."""
        assert sanitize_filename("....") == ""

    def test_sanitize_realistic_story_title(self) -> None:
        """Test realistic story title sanitization."""
        title = "A Love Story: Part 1 (Chapter One)"
        expected = "ALoveStoryPart1ChapterOne"
        assert sanitize_filename(title) == expected

    def test_sanitize_preserves_extension(self) -> None:
        """Test that file extensions are preserved correctly."""
        assert sanitize_filename("My Story Title.epub") == "MyStoryTitle.epub"
        assert sanitize_filename("story_data.json") == "story_data.json"

    def test_sanitize_mixed_attack_vector(self) -> None:
        """Test complex attack combining multiple vectors."""
        malicious = "../../../etc/passwd|rm -rf /;echo 'hacked'"
        result = sanitize_filename(malicious)
        assert ".." not in result
        assert "/" not in result
        assert "|" not in result
        assert ";" not in result
        assert result == "etcpasswdrm-rfechohacked"

    def test_sanitize_command_injection_attempt(self) -> None:
        """Test command injection prevention."""
        assert sanitize_filename("file; rm -rf /") == "filerm-rf"
        assert sanitize_filename("file && malicious") == "filemalicious"
        assert sanitize_filename("file $(dangerous)") == "filedangerous"

    def test_sanitize_preserves_valid_complex_filename(self) -> None:
        """Test that valid complex filenames are preserved."""
        valid = "Story_Title-Part-1.Chapter_2.epub"
        assert sanitize_filename(valid) == valid
