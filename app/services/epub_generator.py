from __future__ import annotations
import os
import re
import uuid
import traceback
import warnings
from html import escape
import ebooklib.epub as epub
from typing import Optional
from app.utils import sanitize_filename, get_cover_directory
from .logger import log_error
from .notifier import send_notification
from .cover_generator import generate_cover_image

warnings.filterwarnings('ignore', category=UserWarning, module='ebooklib')
warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

_EPUB_CSS = """\
body { margin: 1em; padding: 0 1em; }
p { margin: 1.5em 0; line-height: 1.7; font-size: 1.1em; }
h1 { margin: 2em 0 1em 0; text-align: center; }
p.description { text-align: center; font-style: italic; font-size: 1.05em; line-height: 1.8; margin: 1.5em 0 2em 0; }
"""

def _make_css_item() -> epub.EpubItem:
    return epub.EpubItem(
        uid='style_main',
        file_name='style/main.css',
        media_type='text/css',
        content=_EPUB_CSS
    )

def _xhtml(title: str, body: str) -> bytes:
    """Return a complete, valid XHTML document as UTF-8 bytes.

    Two deliberate choices:
    - String concatenation instead of str.format(): story content may contain
      {word} patterns that str.format() misinterprets as named placeholders,
      raising KeyError and silently dropping the chapter via except/continue.
    - Returns bytes, not str: ebooklib's EpubHtml.get_content() re-parses
      self.content via lxml.html.document_fromstring(). lxml rejects Python
      str values that carry an XML encoding declaration ("Unicode strings with
      encoding declaration are not supported") and the silent except block then
      returns \'\' -- producing 0-byte chapter files in the epub.
      Passing bytes bypasses that restriction.
    """
    html = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
        ' lang="en" xml:lang="en">\n'
        f'<head><title>{escape(title)}</title>'
        '<link href="../style/main.css" rel="stylesheet" type="text/css"/></head>\n'
        '<body>\n'
        + body + '\n'
        '</body>\n</html>'
    )
    return html.encode('utf-8')

def format_story_content(content: str) -> str:
    """Return body HTML for story content with all text properly XML-escaped."""
    paragraphs = content.split('\n\n')
    parts = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
    return '\n'.join(parts)

def format_metadata_content(category: Optional[str] = None, tags: Optional[list[str]] = None, description: Optional[str] = None) -> str:
    """Return body HTML for the Story Information page with all text properly XML-escaped."""
    body = '<h1>Story Information</h1>\n'
    if description:
        body += f'<p class="description">{escape(description)}</p>\n'
    if category:
        body += f'<p><strong>CATEGORY:</strong> {escape(category)}</p>\n'
    if tags:
        body += f'<p><strong>TAGS:</strong> {escape(", ".join(tags))}</p>\n'
    return body

def create_epub_file(
    story_title: str,
    story_author: str,
    story_content: str,
    output_directory: str,
    cover_image_path: Optional[str] = None,
    story_category: Optional[str] = None,
    story_tags: Optional[list[str]] = None,
    story_description: Optional[str] = None,
    filename_base: Optional[str] = None,
) -> str:
    """Create an EPUB file from the story content."""
    try:
        os.makedirs(output_directory, exist_ok=True)

        if cover_image_path is None:
            cover_directory = get_cover_directory()
            os.makedirs(cover_directory, exist_ok=True)

            output_base = filename_base if filename_base is not None else sanitize_filename(story_title)
            cover_filename = f"{output_base}.jpg"
            cover_image_path = os.path.join(cover_directory, cover_filename)

            if not os.path.exists(cover_image_path):
                generate_cover_image(story_title, story_author, cover_image_path)

        book = epub.EpubBook()

        book.set_identifier(str(uuid.uuid4()))
        book.set_title(story_title)
        book.set_language('en')
        book.add_author(story_author)

        if story_category:
            book.add_metadata('DC', 'subject', story_category)
        if story_tags:
            for tag in story_tags:
                book.add_metadata('DC', 'subject', tag)

        try:
            if os.path.exists(cover_image_path):
                with open(cover_image_path, 'rb') as cover_file:
                    book.set_cover("cover.jpg", cover_file.read())
        except Exception as e:
            error_msg = f"Error adding cover image: {str(e)}"
            log_error(error_msg)

        css_item = _make_css_item()
        book.add_item(css_item)

        chapters = []
        toc = []

        if story_category or story_tags or story_description:
            try:
                metadata_body = format_metadata_content(story_category, story_tags, story_description)
                metadata_chapter = epub.EpubHtml(title='Story Information',
                                               file_name='metadata.xhtml',
                                               content=_xhtml('Story Information', metadata_body))
                book.add_item(metadata_chapter)
                chapters.append(metadata_chapter)
                toc.append(metadata_chapter)
            except Exception as e:
                error_msg = f"Error adding metadata chapter: {str(e)}"
                log_error(error_msg)

        from .story_downloader import split_story_chapters
        chapter_texts = split_story_chapters(story_content)

        if chapter_texts[0].strip():
            try:
                intro_body = f'<h1>Introduction</h1>\n{format_story_content(chapter_texts[0])}'
                intro_chapter = epub.EpubHtml(title='Introduction',
                                            file_name='intro.xhtml',
                                            content=_xhtml('Introduction', intro_body))
                book.add_item(intro_chapter)
                chapters.append(intro_chapter)
                toc.append(intro_chapter)
            except Exception as e:
                error_msg = f"Error adding introduction chapter: {str(e)}"
                log_error(error_msg)

        for i, chapter_text in enumerate(chapter_texts[1:], 1):
            try:
                title_end = chapter_text.find("\n\n")
                if title_end == -1:
                    chapter_title = f"Chapter {i}"
                    chapter_content = chapter_text
                else:
                    chapter_title = f"Chapter {i}: {chapter_text[:title_end]}"
                    chapter_content = chapter_text[title_end:].strip()

                chapter_body = f'<h1>{escape(chapter_title)}</h1>\n{format_story_content(chapter_content)}'
                chapter = epub.EpubHtml(title=chapter_title,
                                      file_name=f'chapter_{i}.xhtml',
                                      content=_xhtml(chapter_title, chapter_body))
                book.add_item(chapter)
                chapters.append(chapter)
                toc.append(chapter)
            except Exception as e:
                error_msg = f"Error processing chapter {i}: {str(e)}"
                log_error(error_msg)
                continue

        if not chapters:
            error_msg = "No valid chapters found to create EPUB"
            log_error(error_msg)
            raise ValueError(error_msg)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        book.toc = toc
        book.spine = ['nav'] + chapters

        output_base = filename_base if filename_base is not None else sanitize_filename(story_title)
        epub_path = os.path.join(output_directory, f"{output_base}.epub")
        epub.write_epub(epub_path, book, {
            'epub3_pages': False,
            'ignore_ncx': True
        })
        
        send_notification(f"EPUB created: {story_title} by {story_author}")
        
        return epub_path

    except Exception as e:
        error_msg = f"Error creating EPUB file for '{story_title}' by {story_author}: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        send_notification(f"EPUB creation failed: {story_title} by {story_author}", is_error=True)
        raise
