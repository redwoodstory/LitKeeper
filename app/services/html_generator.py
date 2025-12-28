from __future__ import annotations
import os
import json
import traceback
from typing import Optional
from app.utils import sanitize_filename, get_cover_directory
from .logger import log_error
from .notifier import send_notification
from .cover_generator import generate_cover_image

def create_html_file(
    story_title: str,
    story_author: str,
    story_content: str,
    output_directory: str,
    story_category: Optional[str] = None,
    story_tags: Optional[list[str]] = None,
    chapter_titles: Optional[list[str]] = None,
    source_url: Optional[str] = None,
    author_url: Optional[str] = None
) -> str:
    """
    Save story data as JSON for dynamic rendering via template.

    Args:
        story_title: Title of the story
        story_author: Author of the story
        story_content: Full story content with chapters
        output_directory: Directory to save the JSON file
        story_category: Story category (optional)
        story_tags: List of story tags (optional)
        chapter_titles: List of chapter titles (optional)
        source_url: Original story URL (optional)
        author_url: Author's stories page URL (optional)

    Returns:
        Path to the created JSON file
    """
    try:
        cover_directory = get_cover_directory()
        os.makedirs(cover_directory, exist_ok=True)

        cover_filename = f"{sanitize_filename(story_title)}.jpg"
        cover_path = os.path.join(cover_directory, cover_filename)

        generate_cover_image(story_title, story_author, cover_path)

        chapter_texts = story_content.split("\n\nChapter ")
        chapters = []

        for i, chapter_text in enumerate(chapter_texts[1:], 1):
            title_end = chapter_text.find("\n\n")
            if title_end != -1:
                chapter_title = f"Chapter {chapter_text[:title_end]}"
                chapter_content = chapter_text[title_end+2:]
            else:
                chapter_title = f"Chapter {i}"
                chapter_content = chapter_text

            paragraphs = [para.strip() for para in chapter_content.split("\n\n") if para.strip()]

            chapters.append({
                'number': i,
                'title': chapter_title,
                'paragraphs': paragraphs
            })

        story_data = {
            'title': story_title,
            'author': story_author,
            'category': story_category,
            'tags': story_tags if isinstance(story_tags, list) else [story_tags] if story_tags else [],
            'cover': cover_filename,
            'chapters': chapters,
            'source_url': source_url,
            'author_url': author_url
        }

        json_path = os.path.join(output_directory, f"{sanitize_filename(story_title)}.json")

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        send_notification(f"Story data created: {story_title} by {story_author}")

        return json_path

    except Exception as e:
        error_msg = f"Error creating story data for '{story_title}' by {story_author}: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        send_notification(f"Story data creation failed: {story_title} by {story_author}", is_error=True)
        raise
