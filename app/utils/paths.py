from __future__ import annotations
import os


def get_data_directory() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def get_stories_directory() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "stories")


def get_cover_directory() -> str:
    return os.path.join(get_stories_directory(), "covers")


def get_epub_directory() -> str:
    return os.path.join(get_stories_directory(), "epubs")


def get_html_directory() -> str:
    return os.path.join(get_stories_directory(), "html")


def get_archive_directory() -> str:
    return os.path.join(get_stories_directory(), "archive")


def story_epub_path(story_id: int, filename_base: str) -> str:
    return os.path.join(get_epub_directory(), f"{story_id}_{filename_base}.epub")


def story_json_path(story_id: int, filename_base: str) -> str:
    return os.path.join(get_html_directory(), f"{story_id}_{filename_base}.json")


def story_cover_path(story_id: int, filename_base: str) -> str:
    return os.path.join(get_cover_directory(), f"{story_id}_{filename_base}.jpg")
