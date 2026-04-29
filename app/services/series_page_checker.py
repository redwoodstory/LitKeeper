from __future__ import annotations
import json
import re
from typing import Optional, Dict
from .story_downloader import get_session
from .logger import log_action, log_error


class SeriesPageChecker:
    """Fetches series metadata via the Literotica internal API."""

    def check_series_parts(self, series_url: str) -> Optional[Dict]:
        session = get_session()

        series_id = self._extract_series_id(series_url)
        if not series_id:
            # Slug-based URL — try the API with the slug directly first
            # (Literotica API may accept slugs), then fall back to page scraping
            slug = series_url.rstrip('/').rsplit('/', 1)[-1]
            log_action(f"Slug-based series URL detected, slug='{slug}'")
            slug_works = self._try_api_with_id(session, slug)
            if slug_works is not None:
                log_action(f"API accepted slug directly: {slug}")
                return self._build_result(session, series_url, slug, slug_works)

            series_id = self._resolve_series_id_from_page(session, series_url)
        if not series_id:
            log_error(f"Could not extract series ID from URL: {series_url}")
            return None

        works = self._try_api_with_id(session, series_id)
        if works is None:
            log_error(f"API returned no data for series ID: {series_id}")
            return None
        return self._build_result(session, series_url, series_id, works)

    def _try_api_with_id(self, session, series_id: str) -> Optional[list]:
        """Call the Literotica works API with series_id (numeric or slug).
        Returns the works list on success, empty list if the response is empty,
        or None if the request fails."""
        try:
            api_url = f"https://literotica.com/api/3/series/{series_id}/works"
            response = session.get(
                api_url,
                timeout=10,
                headers={"Accept": "application/json", "Referer": "https://www.literotica.com/"},
            )
            if response.status_code == 404:
                log_action(f"API 404 for series ID '{series_id}'")
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_error(f"API request failed for series '{series_id}': {str(e)}")
            return None

    def _build_result(self, session, series_url: str, series_id: str, works: list) -> Optional[Dict]:
        """Build the standard result dict from a works list."""
        if not works:
            log_error(f"API returned empty works list for series {series_id}")
            return {"total_parts": 0, "parts": [], "series_title": "", "description": ""}

        parts = [
            {
                "part_number": i,
                "title": work.get("title", f"Part {i}"),
                "url": f"https://www.literotica.com/s/{work['url']}",
            }
            for i, work in enumerate(works, 1)
        ]
        series_title = self._fetch_series_title(session, series_url)
        description = works[0].get("description", "")
        log_action(f"Series API: found {len(parts)} parts for series '{series_id}'")
        return {
            "total_parts": len(parts),
            "parts": parts,
            "series_title": series_title,
            "description": description,
        }

    def _fetch_series_title(self, session, series_url: str) -> str:
        try:
            resp = session.get(series_url, timeout=10)
            resp.raise_for_status()
            m = re.search(r"<h1[^>]*>(.*?)</h1>", resp.text, re.DOTALL)
            if m:
                return re.sub(r"<[^>]+>", "", m.group(1)).strip()
        except Exception as e:
            log_error(f"Could not fetch series title from {series_url}: {str(e)}")
        return ""

    def _resolve_series_id_from_page(self, session, series_url: str) -> str | None:
        """Fetch the series page and extract the numeric ID from the embedded page data.

        Literotica embeds a __NEXT_DATA__ JSON blob that contains the series ID,
        and also has a canonical link or og:url that may use the numeric form.
        """
        try:
            resp = session.get(series_url, timeout=10)
            resp.raise_for_status()
            html = resp.text
            log_action(f"Fetched series page: status={resp.status_code}, length={len(html)}, final_url={resp.url}")

            # Try canonical / og:url first — Literotica sometimes uses numeric IDs there
            for pattern in (
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
            ):
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    log_action(f"Meta URL found: {m.group(1)}")
                    found = self._extract_series_id(m.group(1))
                    if found:
                        log_action(f"Resolved slug series ID from meta tag: {found}")
                        return found

            # Try __NEXT_DATA__ JSON blob
            m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
            if m:
                log_action("Found __NEXT_DATA__ blob, parsing")
                try:
                    data = json.loads(m.group(1))
                    page_props = data.get("props", {}).get("pageProps", {})
                    log_action(f"__NEXT_DATA__ pageProps keys: {list(page_props.keys())}")
                    for key in ("series", "data", "seriesData"):
                        node = page_props.get(key, {})
                        if isinstance(node, dict):
                            log_action(f"__NEXT_DATA__ pageProps.{key} keys: {list(node.keys())[:10]}")
                            sid = node.get("id") or node.get("series_id")
                            if sid:
                                log_action(f"Resolved slug series ID from __NEXT_DATA__: {sid}")
                                return str(sid)
                except (json.JSONDecodeError, AttributeError) as e:
                    log_action(f"__NEXT_DATA__ parse failed: {e}")
            else:
                log_action("No __NEXT_DATA__ blob found in page")

            # Last resort: any numeric ID following /series/se/ anywhere in the page
            m = re.search(r'/series/se/(\d+)', html)
            if m:
                log_action(f"Resolved slug series ID from page HTML: {m.group(1)}")
                return m.group(1)

            log_action("Could not find numeric series ID anywhere in page")

        except Exception as e:
            log_error(f"Error resolving series ID from page {series_url}: {str(e)}")
        return None

    def _extract_series_id(self, url: str) -> str | None:
        m = re.search(r"/series/se/(\d+)", url)
        return m.group(1) if m else None
