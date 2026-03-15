#!/usr/bin/env python3
import sys
sys.path.insert(0, '/litkeeper')

from app.services.series_page_checker import SeriesPageChecker

series_url = "https://www.literotica.com/series/se/494452386"
checker = SeriesPageChecker()
result = checker.check_series_parts(series_url)

if result:
    print(f"\n✓ Successfully parsed series!")
    print(f"Title: {result.get('series_title')}")
    print(f"Total parts: {result.get('total_parts')}")
    print(f"Parts found:")
    for part in result.get('parts', []):
        print(f"  {part['part_number']}. {part['title']}")
        print(f"     URL: {part['url']}")
else:
    print("\n✗ Failed to parse series page")
