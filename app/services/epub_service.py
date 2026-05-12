from __future__ import annotations
import os
import re
import zipfile
import xml.etree.ElementTree as ET
import warnings
import traceback
from typing import Optional
from app.models import Story, ReadingProgress
from app.models.base import db
from datetime import datetime
from .logger import log_error

warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

class EpubService:
    
    @staticmethod
    def get_epub_path(story: Story) -> Optional[str]:
        """Get the full path to the EPUB file for a story."""
        epub_format = next((f for f in story.formats if f.format_type == 'epub'), None)
        if not epub_format:
            return None
        if os.path.exists(epub_format.file_path):
            return epub_format.file_path
        return None
    
    @staticmethod
    def get_reading_progress(story_id: int) -> Optional[ReadingProgress]:
        """Get reading progress for a story."""
        return ReadingProgress.query.filter_by(story_id=story_id).first()
    
    @staticmethod
    def update_reading_progress(
        story_id: int,
        current_chapter: int = None,
        current_paragraph: int = None,
        scroll_position: int = None,
        is_completed: bool = None,
        cfi: str = None,
        paragraph_id: str = None,
        percentage: float = None
    ) -> ReadingProgress:
        """Update or create reading progress for a story."""

        def _apply_fields(progress: ReadingProgress) -> None:
            if current_chapter is not None:
                progress.current_chapter = current_chapter
            if current_paragraph is not None:
                progress.current_paragraph = current_paragraph
            if scroll_position is not None:
                progress.scroll_position = scroll_position
            if is_completed is not None:
                progress.is_completed = is_completed
            if cfi is not None:
                progress.cfi = cfi
            if paragraph_id is not None:
                progress.paragraph_id = paragraph_id
            if percentage is not None:
                progress.percentage = percentage
            progress.last_read_at = datetime.utcnow()

        progress = ReadingProgress.query.filter_by(story_id=story_id).first()

        if not progress:
            progress = ReadingProgress(story_id=story_id)
            db.session.add(progress)

        _apply_fields(progress)

        try:
            db.session.commit()
        except Exception as e:
            # Handle concurrent INSERT race: two requests both saw no existing row
            # and both tried to INSERT, causing a UNIQUE constraint violation.
            if 'UNIQUE constraint failed' in str(e):
                db.session.rollback()
                progress = ReadingProgress.query.filter_by(story_id=story_id).first()
                if progress:
                    _apply_fields(progress)
                    db.session.commit()
                else:
                    raise
            else:
                raise

        return progress
    
    @staticmethod
    def update_epub_metadata(
        epub_path: str,
        title: str,
        author: str,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None,
        all_authors: Optional[list[str]] = None,
    ) -> bool:
        """Patch title, author, category, tags, and description inside an existing EPUB in-place."""
        try:
            if not os.path.exists(epub_path):
                log_error(f"EPUB file not found: {epub_path}")
                return False

            import tempfile
            import shutil
            from .epub_generator import format_metadata_content

            DC = 'http://purl.org/dc/elements/1.1/'
            OPF = 'http://www.idpf.org/2007/opf'

            new_metadata_content = format_metadata_content(category, tags, description, all_authors)
            new_metadata_xhtml = EpubService._XHTML_WRAPPER.format(
                title='Story Information',
                body=new_metadata_content,
            ).encode('utf-8')

            temp_dir = tempfile.mkdtemp()
            temp_epub = os.path.join(temp_dir, 'temp.epub')

            try:
                with zipfile.ZipFile(epub_path, 'r') as zip_in:
                    with zipfile.ZipFile(temp_epub, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                        for item in zip_in.infolist():
                            data = zip_in.read(item.filename)
                            name = item.filename.lower()

                            if name.endswith('content.opf') or name.endswith('package.opf'):
                                try:
                                    from html import escape as _he
                                    text = data.decode('utf-8')
                                    et = _he(title)
                                    ea = _he(author)
                                    text = re.sub(
                                        r'(<dc:title[^>]*>)[^<]*(</dc:title>)',
                                        lambda m: f'{m.group(1)}{et}{m.group(2)}',
                                        text, count=1,
                                    )
                                    text = re.sub(
                                        r'(<dc:creator[^>]*>)[^<]*(</dc:creator>)',
                                        lambda m: f'{m.group(1)}{ea}{m.group(2)}',
                                        text, count=1,
                                    )
                                    data = text.encode('utf-8')
                                except Exception as opf_err:
                                    log_error(f"OPF patch failed: {opf_err}")

                            elif name.endswith('nav.xhtml'):
                                try:
                                    from html import escape as _he
                                    et = _he(title)
                                    text = data.decode('utf-8')
                                    text = re.sub(
                                        r'(<title>)[^<]*(</title>)',
                                        lambda m: f'{m.group(1)}{et}{m.group(2)}',
                                        text, count=1,
                                    )
                                    text = re.sub(
                                        r'(<h2[^>]*>)[^<]*(</h2>)',
                                        lambda m: f'{m.group(1)}{et}{m.group(2)}',
                                        text, count=1,
                                    )
                                    data = text.encode('utf-8')
                                except Exception as nav_err:
                                    log_error(f"nav.xhtml patch failed: {nav_err}")

                            elif name.endswith('toc.ncx'):
                                try:
                                    NCX_NS = 'http://www.daisy.org/z3986/2005/ncx/'
                                    ET.register_namespace('', NCX_NS)
                                    root = ET.fromstring(data.decode('utf-8'))
                                    doc_title = root.find(f'{{{NCX_NS}}}docTitle')
                                    if doc_title is not None:
                                        text_el = doc_title.find(f'{{{NCX_NS}}}text')
                                        if text_el is not None:
                                            text_el.text = title
                                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                                except Exception as ncx_err:
                                    log_error(f"toc.ncx patch failed: {ncx_err}")

                            elif 'metadata.xhtml' in name:
                                data = new_metadata_xhtml

                            zip_out.writestr(item, data)

                shutil.move(temp_epub, epub_path)
                return True

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        except Exception as e:
            log_error(f"Error updating EPUB metadata: {str(e)}\n{traceback.format_exc()}")
            return False

    @staticmethod
    def update_epub_cover(epub_path: str, cover_image_path: str) -> bool:
        """Update the cover image in an existing EPUB file using direct ZIP manipulation.

        Args:
            epub_path: Path to the EPUB file
            cover_image_path: Path to the new cover image

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(epub_path):
                log_error(f"EPUB file not found: {epub_path}")
                return False

            if not os.path.exists(cover_image_path):
                log_error(f"Cover image not found: {cover_image_path}")
                return False

            import tempfile
            import shutil

            with open(cover_image_path, 'rb') as cover_file:
                new_cover_data = cover_file.read()

            temp_dir = tempfile.mkdtemp()
            temp_epub = os.path.join(temp_dir, 'temp.epub')

            try:
                with zipfile.ZipFile(epub_path, 'r') as zip_in:
                    with zipfile.ZipFile(temp_epub, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                        for item in zip_in.infolist():
                            data = zip_in.read(item.filename)

                            if 'cover.jpg' in item.filename.lower():
                                zip_out.writestr(item.filename, new_cover_data)
                            else:
                                zip_out.writestr(item, data)

                shutil.move(temp_epub, epub_path)
                return True

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        except Exception as e:
            error_msg = f"Error updating EPUB cover: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return False

    _XHTML_WRAPPER = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">\n'
        "<head><title>{title}</title>"
        '<link href="../style/main.css" rel="stylesheet" type="text/css"/>'
        "</head>\n<body>\n{body}\n</body>\n</html>"
    )

    @staticmethod
    def _repair_xhtml(content: str, fallback_title: str) -> tuple[str, bool]:
        """Return (repaired_content, was_changed).

        Fixes two classes of defect that cause Readium's strict XML parser to fail:
        1. Bare fragment (no root element) — wraps in a complete XHTML document.
        2. <style> block inside <body> — strips it out.
        """
        changed = False

        # Strip <style> blocks wherever they appear
        stripped = re.sub(r'<style[\s\S]*?</style>', '', content, flags=re.IGNORECASE)
        if stripped != content:
            content = stripped
            changed = True

        # If there is no XML/HTML root, the file is a bare fragment — wrap it
        if not content.lstrip().startswith('<'):
            # empty after stripping — nothing useful
            return content, changed

        first_tag = content.lstrip()[:5].lower()
        if not (first_tag.startswith('<?xml') or first_tag.startswith('<html')):
            # Extract title from first <h1> if present, else use fallback
            h1 = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'<[^>]+>', '', h1.group(1)).strip() if h1 else fallback_title
            content = EpubService._XHTML_WRAPPER.format(title=title, body=content.strip())
            changed = True

        return content, changed

    @staticmethod
    def repair_metadata_chapter(epub_path: str) -> bool:
        """Repair all XHTML chapters in an existing EPUB so Readium can parse them.

        Returns True if any file was modified, False if already clean or on error.
        """
        try:
            if not os.path.exists(epub_path):
                return False

            import tempfile
            import shutil

            replacements: dict[str, bytes] = {}
            with zipfile.ZipFile(epub_path, 'r') as zf:
                for name in zf.namelist():
                    if not name.endswith('.xhtml'):
                        continue
                    original = zf.read(name).decode('utf-8')
                    fallback = name.rsplit('/', 1)[-1].replace('.xhtml', '').replace('_', ' ').title()
                    repaired, changed = EpubService._repair_xhtml(original, fallback)
                    if changed:
                        replacements[name] = repaired.encode('utf-8')

            if not replacements:
                return False

            temp_dir = tempfile.mkdtemp()
            temp_epub = os.path.join(temp_dir, 'temp.epub')
            try:
                with zipfile.ZipFile(epub_path, 'r') as zip_in:
                    with zipfile.ZipFile(temp_epub, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                        for item in zip_in.infolist():
                            if item.filename in replacements:
                                zip_out.writestr(item.filename, replacements[item.filename])
                            else:
                                zip_out.writestr(item, zip_in.read(item.filename))
                shutil.move(temp_epub, epub_path)
                return True
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        except Exception as e:
            error_msg = f"Error repairing EPUB chapters: {str(e)}\n{traceback.format_exc()}"
            log_error(error_msg)
            return False
