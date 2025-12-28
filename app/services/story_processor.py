from __future__ import annotations
from typing import Optional
import traceback
from app.utils import get_epub_directory, get_html_directory
from .story_downloader import download_story, extract_chapter_titles
from .epub_generator import create_epub_file
from .html_generator import create_html_file
from .file_operations import copy_to_secondary_output
from .logger import log_action, log_error
from .notifier import send_notification


class StoryProcessingResult:
    def __init__(
        self,
        success: bool,
        message: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        formats: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.title = title
        self.author = author
        self.formats = formats or []
        self.files = files or []
        self.error = error

    def to_dict(self) -> dict:
        result = {
            "success": "true" if self.success else "false",
            "message": self.message
        }
        if self.title:
            result["title"] = self.title
        if self.author:
            result["author"] = self.author
        if self.formats:
            result["formats"] = self.formats
        if self.files:
            result["files"] = self.files
        return result


def download_story_and_create_files(
    url: str,
    formats: Optional[list[str]] = None,
    send_notifications: bool = True
) -> StoryProcessingResult:
    if formats is None:
        formats = ["epub"]

    try:
        log_action(f"Starting download: {url}")
        story_content, story_title, story_author, story_category, story_tags, story_author_url = download_story(url)

        if not story_content:
            error_msg = f"Failed to download story from: {url}"
            log_error(error_msg, url)
            if send_notifications:
                send_notification(f"Story download failed: {url}", is_error=True)
            return StoryProcessingResult(
                success=False,
                message=error_msg,
                error=error_msg
            )

        log_action(f"Downloaded: '{story_title}' by {story_author}")
        created_files = []

        if "epub" in formats:
            epub_file_name = create_epub_file(
                story_title,
                story_author,
                story_content,
                get_epub_directory(),
                story_category=story_category,
                story_tags=story_tags
            )
            created_files.append(f"EPUB: {epub_file_name.split('/')[-1]}")
            log_action(f"Created EPUB: {epub_file_name}")

            secondary_epub = copy_to_secondary_output(epub_file_name, 'epub')
            if secondary_epub:
                log_action(f"Copied EPUB to secondary output: {secondary_epub}")

        if "html" in formats:
            chapter_titles = extract_chapter_titles(story_content)

            html_file_name = create_html_file(
                story_title,
                story_author,
                story_content,
                get_html_directory(),
                story_category=story_category,
                story_tags=story_tags,
                chapter_titles=chapter_titles if chapter_titles else None,
                source_url=url,
                author_url=story_author_url
            )
            created_files.append(f"HTML: {html_file_name.split('/')[-1]}")
            log_action(f"Created HTML: {html_file_name}")

        formats_str = " and ".join(created_files)
        success_msg = f"Successfully downloaded '{story_title}' by {story_author}"

        if send_notifications:
            send_notification(f"Story downloaded: '{story_title}' ({formats_str})")

        return StoryProcessingResult(
            success=True,
            message=success_msg,
            title=story_title,
            author=story_author,
            formats=formats,
            files=created_files
        )

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        if send_notifications:
            send_notification(f"Error processing story: {str(e)}", is_error=True)
        return StoryProcessingResult(
            success=False,
            message=str(e),
            error=error_msg
        )
