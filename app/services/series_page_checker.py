from __future__ import annotations
import re
from typing import Optional, Dict
from .story_downloader import get_session
from .logger import log_action, log_error


class SeriesPageChecker:
    """Fetches series metadata via the Literotica internal API."""

    def check_series_parts(self, series_url: str) -> Optional[Dict]:
        series_id = self._extract_series_id(series_url)
        if not series_id:
            log_error(f"Could not extract series ID from URL: {series_url}")
            return None

        try:
            session = get_session()
            api_url = f"https://literotica.com/api/3/series/{series_id}/works"
            response = session.get(
                api_url,
                timeout=10,
                headers={"Accept": "application/json", "Referer": "https://www.literotica.com/"},
            )
            response.raise_for_status()
            works = response.json()

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

            log_action(f"Series API: found {len(parts)} parts for series {series_id}")
            return {
                "total_parts": len(parts),
                "parts": parts,
                "series_title": series_title,
                "description": description,
            }

        except Exception as e:
            log_error(f"Error fetching series {series_url}: {str(e)}")
            return None

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

    def _extract_series_id(self, url: str) -> str | None:
        m = re.search(r"/series/se/(\d+)", url)
        return m.group(1) if m else None
