from __future__ import annotations
import os
import json
from datetime import datetime
from app.utils import get_epub_directory, get_html_directory

def get_library_data() -> list[dict]:
    epub_directory = get_epub_directory()
    html_directory = get_html_directory()

    os.makedirs(epub_directory, exist_ok=True)
    os.makedirs(html_directory, exist_ok=True)

    epub_files = {f.replace('.epub', ''): f for f in os.listdir(epub_directory)
                 if f.endswith('.epub') and f != 'cover.jpg'}

    story_files = {}
    for f in os.listdir(html_directory):
        if f.endswith('.json'):
            title = f.replace('.json', '')
            story_files[title] = f
        elif f.endswith('.html'):
            title = f.replace('.html', '')
            if title not in story_files:
                story_files[title] = f

    all_titles = set(epub_files.keys()) | set(story_files.keys())
    stories = []

    for filename_base in sorted(all_titles):
        story = {"formats": [], "filename_base": filename_base}

        display_title = filename_base
        author = None
        category = None
        tags = []
        cover = None
        page_count = None
        word_count = None

        if filename_base in story_files and story_files[filename_base].endswith('.json'):
            try:
                json_path = os.path.join(html_directory, story_files[filename_base])
                with open(json_path, 'r', encoding='utf-8') as f:
                    story_data = json.load(f)
                    display_title = story_data.get('title', filename_base)
                    author = story_data.get('author')
                    category = story_data.get('category')
                    tags = story_data.get('tags', [])
                    cover = story_data.get('cover')
                    source_url = story_data.get('source_url')
                    author_url = story_data.get('author_url')
                    page_count = story_data.get('page_count')
                    word_count = story_data.get('word_count')
            except:
                pass

        story["title"] = display_title
        if author:
            story["author"] = author
        if category:
            story["category"] = category
        if tags:
            story["tags"] = tags
        if cover:
            story["cover"] = cover
        if 'source_url' in locals() and source_url:
            story["source_url"] = source_url
        if 'author_url' in locals() and author_url:
            story["author_url"] = author_url
        if page_count:
            story["page_count"] = page_count
        if word_count:
            story["word_count"] = word_count

        if filename_base in epub_files:
            epub_path = os.path.join(epub_directory, epub_files[filename_base])
            story["formats"].append("epub")
            story["epub_file"] = epub_files[filename_base]
            story["created_at"] = datetime.fromtimestamp(
                os.path.getmtime(epub_path)
            ).isoformat()
            story["size"] = os.path.getsize(epub_path)

        if filename_base in story_files:
            story_path = os.path.join(html_directory, story_files[filename_base])
            story["formats"].append("html")
            story["html_file"] = filename_base + ".html"
            if "created_at" not in story:
                story["created_at"] = datetime.fromtimestamp(
                    os.path.getmtime(story_path)
                ).isoformat()

        stories.append(story)

    stories.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return stories
