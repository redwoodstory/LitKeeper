from __future__ import annotations
import pytest
from pydantic import ValidationError
from app.validators import StoryDownloadRequest, LibraryFilterRequest


@pytest.mark.unit
class TestStoryDownloadRequest:
    """Test StoryDownloadRequest Pydantic validator."""

    def test_valid_literotica_url(self) -> None:
        """Test that valid Literotica URLs are accepted."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story-title-1")
        assert request.url == "https://www.literotica.com/s/story-title-1"

    def test_valid_url_with_query_params(self) -> None:
        """Test URLs with query parameters are accepted."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story?page=2")
        assert request.url == "https://www.literotica.com/s/story?page=2"

    def test_url_whitespace_trimmed(self) -> None:
        """Test that whitespace is trimmed from URL."""
        request = StoryDownloadRequest(url="  https://www.literotica.com/s/story  ")
        assert request.url == "https://www.literotica.com/s/story"

    def test_url_with_trailing_text_split(self) -> None:
        """Test that URL is split on whitespace (takes first part)."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story extra text")
        assert request.url == "https://www.literotica.com/s/story"

    def test_empty_url_raises_error(self) -> None:
        """Test that empty URL raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="")
        assert "URL cannot be empty" in str(exc_info.value)

    def test_whitespace_only_url_raises_error(self) -> None:
        """Test that whitespace-only URL raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="   ")
        assert "URL cannot be empty" in str(exc_info.value)

    def test_wrong_domain_raises_error(self) -> None:
        """Test that non-Literotica domain raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://www.example.com/story")
        assert "Only Literotica URLs are allowed" in str(exc_info.value)

    def test_http_instead_of_https_raises_error(self) -> None:
        """Test that HTTP (not HTTPS) raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="http://www.literotica.com/s/story")
        assert "Only Literotica URLs are allowed" in str(exc_info.value)

    def test_subdomain_mismatch_raises_error(self) -> None:
        """Test that wrong subdomain raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://api.literotica.com/s/story")
        assert "Only Literotica URLs are allowed" in str(exc_info.value)

    def test_literotica_substring_not_sufficient(self) -> None:
        """Test that domain containing 'literotica' is not sufficient."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://www.fakeliterotica.com/s/story")
        assert "Only Literotica URLs are allowed" in str(exc_info.value)

    def test_format_epub_default(self) -> None:
        """Test that format defaults to ['epub']."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story")
        assert request.format == ["epub"]

    def test_format_html_valid(self) -> None:
        """Test that HTML format is valid."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story", format=["html"])
        assert request.format == ["html"]

    def test_format_both_epub_and_html(self) -> None:
        """Test that both formats can be specified."""
        request = StoryDownloadRequest(
            url="https://www.literotica.com/s/story",
            format=["epub", "html"]
        )
        assert "epub" in request.format
        assert "html" in request.format

    def test_format_invalid_pdf_raises_error(self) -> None:
        """Test that invalid format 'pdf' raises error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://www.literotica.com/s/story", format=["pdf"])
        error_msg = str(exc_info.value)
        assert "epub" in error_msg or "html" in error_msg

    def test_format_invalid_mobi_raises_error(self) -> None:
        """Test that invalid format 'mobi' raises error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://www.literotica.com/s/story", format=["mobi"])
        error_msg = str(exc_info.value)
        assert "epub" in error_msg or "html" in error_msg

    def test_format_empty_list_raises_error(self) -> None:
        """Test that empty format list raises error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(url="https://www.literotica.com/s/story", format=[])
        error_msg = str(exc_info.value)
        assert "at least 1 item" in error_msg.lower()

    def test_format_mixed_valid_and_invalid(self) -> None:
        """Test that mixed valid and invalid formats raises error."""
        with pytest.raises(ValidationError) as exc_info:
            StoryDownloadRequest(
                url="https://www.literotica.com/s/story",
                format=["epub", "pdf"]
            )
        error_msg = str(exc_info.value)
        assert "epub" in error_msg or "html" in error_msg

    def test_wait_default_true(self) -> None:
        """Test that wait defaults to True."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story")
        assert request.wait is True

    def test_wait_explicit_false(self) -> None:
        """Test that wait can be set to False."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story", wait=False)
        assert request.wait is False

    def test_wait_explicit_true(self) -> None:
        """Test that wait can be explicitly set to True."""
        request = StoryDownloadRequest(url="https://www.literotica.com/s/story", wait=True)
        assert request.wait is True


@pytest.mark.unit
class TestLibraryFilterRequest:
    """Test LibraryFilterRequest Pydantic validator."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        request = LibraryFilterRequest()
        assert request.search == ""
        assert request.category == "all"

    def test_search_normalization_lowercase(self) -> None:
        """Test that search is converted to lowercase."""
        request = LibraryFilterRequest(search="SEARCH TERM")
        assert request.search == "search term"

    def test_search_whitespace_trimmed(self) -> None:
        """Test that search whitespace is trimmed."""
        request = LibraryFilterRequest(search="  search term  ")
        assert request.search == "search term"

    def test_search_empty_string(self) -> None:
        """Test that empty search string is accepted."""
        request = LibraryFilterRequest(search="")
        assert request.search == ""

    def test_search_whitespace_only_becomes_empty(self) -> None:
        """Test that whitespace-only search becomes empty string."""
        request = LibraryFilterRequest(search="   ")
        assert request.search == ""

    def test_category_all(self) -> None:
        """Test that category 'all' is valid."""
        request = LibraryFilterRequest(category="all")
        assert request.category == "all"

    def test_category_specific(self) -> None:
        """Test that specific category is valid."""
        request = LibraryFilterRequest(category="Romance")
        assert request.category == "Romance"

    def test_category_whitespace_trimmed(self) -> None:
        """Test that category whitespace is trimmed."""
        request = LibraryFilterRequest(category="  Romance  ")
        assert request.category == "Romance"

    def test_category_uncategorized(self) -> None:
        """Test that 'uncategorized' category is valid."""
        request = LibraryFilterRequest(category="uncategorized")
        assert request.category == "uncategorized"

    def test_combined_filters(self) -> None:
        """Test that all filters can be combined."""
        request = LibraryFilterRequest(
            search="Love Story",
            category="Romance"
        )
        assert request.search == "love story"
        assert request.category == "Romance"

    def test_special_characters_in_search(self) -> None:
        """Test that special characters in search are preserved."""
        request = LibraryFilterRequest(search="Story: Part 1")
        assert request.search == "story: part 1"

    def test_unicode_in_search(self) -> None:
        """Test that Unicode characters in search are preserved."""
        request = LibraryFilterRequest(search="Café Story")
        assert request.search == "café story"
