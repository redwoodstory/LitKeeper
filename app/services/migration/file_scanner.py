from __future__ import annotations
import os
import re
import json
from typing import List, Dict, Optional, Tuple
from app.utils import get_epub_directory, get_html_directory

_ID_PREFIX_RE = re.compile(r'^(\d+)_(.+)$')


def _strip_id_prefix(base: str) -> Tuple[str, Optional[int]]:
    """Return (clean_filename_base, story_id) or (base, None) if no numeric prefix."""
    m = _ID_PREFIX_RE.match(base)
    if m:
        try:
            return m.group(2), int(m.group(1))
        except ValueError:
            pass
    return base, None


class FileScanner:
    """Scans EPUB and JSON directories and groups files by filename_base"""

    def scan_story_files(self) -> List[Dict]:
        """
        Scan EPUB and JSON directories and group by filename_base.

        Files named {id}_{filename_base}.ext have the ID prefix stripped so the
        returned filename_base matches the Story.filename_base column. The embedded
        story_id is included in each format entry when present.

        Returns:
            List of dicts with structure:
            {
                'filename_base': 'StoryTitle',
                'story_id': 42 | None,
                'formats': [
                    {'type': 'epub', 'path': '/path/to/file.epub', 'size': 12345, 'story_id': 42},
                    {'type': 'json', 'path': '/path/to/file.json', 'size': 6789, 'json_data': {...}, 'story_id': 42}
                ],
                'primary_file': '/path/to/primary.epub',
                'primary_type': 'epub'
            }
        """
        epub_dir = get_epub_directory()
        html_dir = get_html_directory()

        epub_files = {}
        if os.path.exists(epub_dir):
            for filename in os.listdir(epub_dir):
                if filename.endswith('.epub'):
                    raw_base = filename[:-5]  # strip .epub
                    base, story_id = _strip_id_prefix(raw_base)
                    full_path = os.path.join(epub_dir, filename)
                    try:
                        epub_files[base] = {
                            'type': 'epub',
                            'path': full_path,
                            'size': os.path.getsize(full_path),
                            'story_id': story_id,
                        }
                    except OSError:
                        continue

        json_files = {}
        if os.path.exists(html_dir):
            for filename in os.listdir(html_dir):
                if filename.endswith('.json'):
                    raw_base = filename[:-5]  # strip .json
                    base, story_id = _strip_id_prefix(raw_base)
                    full_path = os.path.join(html_dir, filename)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)

                        json_files[base] = {
                            'type': 'json',
                            'path': full_path,
                            'size': os.path.getsize(full_path),
                            'json_data': json_data,
                            'story_id': story_id,
                        }
                    except (OSError, json.JSONDecodeError):
                        continue

        all_bases = set(epub_files.keys()) | set(json_files.keys())
        story_groups = []

        for base in sorted(all_bases):
            formats = []
            group_story_id = None

            if base in epub_files:
                entry = epub_files[base]
                formats.append(entry)
                group_story_id = group_story_id or entry.get('story_id')

            if base in json_files:
                entry = json_files[base]
                formats.append(entry)
                group_story_id = group_story_id or entry.get('story_id')

            group: Dict = {
                'filename_base': base,
                'story_id': group_story_id,
                'formats': formats,
            }

            if formats:
                primary = next((f for f in formats if f['type'] == 'epub'), formats[0])
                group['primary_file'] = primary['path']
                group['primary_type'] = primary['type']

            story_groups.append(group)

        return story_groups

    def get_file_count(self) -> Dict[str, int]:
        """Get counts of EPUB and JSON files"""
        epub_dir = get_epub_directory()
        html_dir = get_html_directory()

        epub_count = 0
        json_count = 0

        if os.path.exists(epub_dir):
            epub_count = len([f for f in os.listdir(epub_dir) if f.endswith('.epub')])

        if os.path.exists(html_dir):
            json_count = len([f for f in os.listdir(html_dir) if f.endswith('.json')])

        return {
            'epub_count': epub_count,
            'json_count': json_count,
            'total': max(epub_count, json_count)
        }
