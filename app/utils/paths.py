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
