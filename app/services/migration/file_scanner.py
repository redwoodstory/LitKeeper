from __future__ import annotations
import os
import json
from typing import List, Dict
from app.utils import get_epub_directory, get_html_directory

class FileScanner:
    """Scans EPUB and JSON directories and groups files by filename_base"""

    def scan_story_files(self) -> List[Dict]:
        """
        Scan EPUB and JSON directories and group by filename_base.

        Returns:
            List of dicts with structure:
            {
                'filename_base': 'StoryTitle',
                'formats': [
                    {'type': 'epub', 'path': '/path/to/file.epub', 'size': 12345},
                    {'type': 'json', 'path': '/path/to/file.json', 'size': 6789, 'json_data': {...}}
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
                    base = filename.replace('.epub', '')
                    full_path = os.path.join(epub_dir, filename)
                    try:
                        epub_files[base] = {
                            'type': 'epub',
                            'path': full_path,
                            'size': os.path.getsize(full_path)
                        }
                    except OSError:
                        continue

        json_files = {}
        if os.path.exists(html_dir):
            for filename in os.listdir(html_dir):
                if filename.endswith('.json'):
                    base = filename.replace('.json', '')
                    full_path = os.path.join(html_dir, filename)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)

                        json_files[base] = {
                            'type': 'json',
                            'path': full_path,
                            'size': os.path.getsize(full_path),
                            'json_data': json_data
                        }
                    except (OSError, json.JSONDecodeError):
                        continue

        all_bases = set(epub_files.keys()) | set(json_files.keys())
        story_groups = []

        for base in sorted(all_bases):
            group = {
                'filename_base': base,
                'formats': []
            }

            if base in epub_files:
                group['formats'].append(epub_files[base])
                group['primary_file'] = epub_files[base]['path']
                group['primary_type'] = 'epub'

            if base in json_files:
                group['formats'].append(json_files[base])
                if 'primary_file' not in group:
                    group['primary_file'] = json_files[base]['path']
                    group['primary_type'] = 'json'

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
