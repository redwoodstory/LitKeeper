#!/usr/bin/env python3
"""
One-off fix: prepend story IDs to JSON files in stories/html/ by matching against
EPUB filenames in stories/epubs/ (which already carry the correct {id}_{base} prefix).

Usage:
    python fix_json_names.py [--dry-run] [stories_dir]

    stories_dir defaults to ./stories (the Docker bind-mount path).
    --dry-run   Print what would be renamed without touching anything.
"""
import os
import re
import sys

DRY_RUN = '--dry-run' in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith('--')]

stories_dir = args[0] if args else os.path.join(os.path.dirname(__file__), 'stories')
epubs_dir = os.path.join(stories_dir, 'epubs')
html_dir = os.path.join(stories_dir, 'html')

if not os.path.isdir(epubs_dir):
    sys.exit(f"ERROR: epubs dir not found: {epubs_dir}")
if not os.path.isdir(html_dir):
    sys.exit(f"ERROR: html dir not found: {html_dir}")

# Build filename_base -> id map from EPUB files (e.g. "42_some_story.epub" -> {42: "some_story"})
id_re = re.compile(r'^(\d+)_(.+)\.epub$')
epub_map = {}
for fname in os.listdir(epubs_dir):
    m = id_re.match(fname)
    if m:
        epub_map[m.group(2)] = m.group(1)

print(f"Indexed {len(epub_map)} EPUB file(s) with ID prefix.")

renamed = 0
already_ok = 0
no_match = []

for fname in sorted(os.listdir(html_dir)):
    if not fname.endswith('.json'):
        continue
    if re.match(r'^\d+_', fname):
        already_ok += 1
        continue

    base = fname[:-5]  # strip .json

    if base not in epub_map:
        no_match.append(fname)
        continue

    story_id = epub_map[base]
    new_name = f"{story_id}_{base}.json"
    src = os.path.join(html_dir, fname)
    dst = os.path.join(html_dir, new_name)

    if os.path.exists(dst):
        print(f"  SKIP  (target exists): {fname} -> {new_name}")
        continue

    if DRY_RUN:
        print(f"  [DRY RUN] {fname}  ->  {new_name}")
    else:
        os.rename(src, dst)
        print(f"  Renamed: {fname}  ->  {new_name}")
    renamed += 1

print(f"\nDone. Renamed: {renamed}, Already correct: {already_ok}")

if no_match:
    print(f"\nNo matching EPUB found for {len(no_match)} JSON file(s) — check these manually:")
    for f in no_match:
        print(f"  {f}")
