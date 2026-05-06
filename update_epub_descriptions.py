#!/usr/bin/env python3
"""One-off script: inject DC:description metadata into all existing EPUBs.

Directly patches the OPF XML inside the ZIP instead of using ebooklib's
read/write round-trip, which is known to corrupt the container.xml and
mimetype structure.
"""
from __future__ import annotations
import os
import sys
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import Story, StoryFormat, db

DC_NS = 'http://purl.org/dc/elements/1.1/'
ET.register_namespace('dc', DC_NS)
ET.register_namespace('', 'http://www.idpf.org/2007/opf')


def _find_opf_path(zf: zipfile.ZipFile) -> str | None:
    try:
        container = zf.read('META-INF/container.xml')
        root = ET.fromstring(container)
        for el in root.iter():
            if el.get('media-type') == 'application/oebps-package+xml':
                return el.get('full-path')
    except Exception:
        pass
    return None


def _update_opf_description(opf_bytes: bytes, description: str) -> bytes:
    root = ET.fromstring(opf_bytes)
    ns = {'dc': DC_NS, 'opf': 'http://www.idpf.org/2007/opf'}

    metadata = root.find('{http://www.idpf.org/2007/opf}metadata')
    if metadata is None:
        return opf_bytes

    # Remove any existing dc:description
    for desc_el in metadata.findall('dc:description', ns):
        metadata.remove(desc_el)

    # Add new dc:description
    desc_el = ET.SubElement(metadata, f'{{{DC_NS}}}description')
    desc_el.text = description

    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def patch_epub(epub_path: str, description: str) -> None:
    tmp_path = epub_path + '.tmp'
    with zipfile.ZipFile(epub_path, 'r') as src:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as dst:
            # Preserve mimetype as first uncompressed entry if present
            if 'mimetype' in src.namelist():
                dst.writestr('mimetype', src.read('mimetype'), compress_type=zipfile.ZIP_STORED)

            opf_path = _find_opf_path(src)

            for item in src.namelist():
                if item == 'mimetype':
                    continue
                if item == opf_path:
                    data = _update_opf_description(src.read(item), description)
                    dst.writestr(item, data)
                else:
                    dst.writestr(item, src.read(item))

    shutil.move(tmp_path, epub_path)


def update_epub_descriptions() -> None:
    app = create_app()
    with app.app_context():
        formats = (
            StoryFormat.query
            .filter_by(format_type='epub')
            .join(Story, StoryFormat.story_id == Story.id)
            .filter(Story.description.isnot(None))
            .all()
        )

        updated = 0
        skipped = 0
        errors = 0

        for fmt in formats:
            path = fmt.file_path
            if not os.path.exists(path):
                skipped += 1
                continue

            try:
                patch_epub(path, fmt.story.description)
                updated += 1
                print(f"Updated: {os.path.basename(path)}")
            except Exception as e:
                errors += 1
                print(f"ERROR: {os.path.basename(path)} — {e}")

        print(f"\nDone. Updated: {updated}, Skipped: {skipped}, Errors: {errors}")


if __name__ == '__main__':
    update_epub_descriptions()
