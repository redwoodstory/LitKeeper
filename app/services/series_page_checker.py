from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from .story_downloader import get_session
from .logger import log_action, log_error

class SeriesPageChecker:
    """Lightweight checker for Literotica series pages."""

    def check_series_parts(self, series_url: str) -> Optional[Dict]:
        """
        Parse series page to count total parts.

        Returns:
            {
                'total_parts': int,
                'parts': [{'part_number': int, 'title': str, 'url': str}, ...],
                'series_title': str
            }
        """
        try:
            session = get_session()
            response = session.get(series_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            items = soup.find_all("div", class_=lambda c: c and "_item_" in str(c))

            parts = []
            for idx, item in enumerate(items, 1):
                link = item.find("a", href=lambda h: h and "/s/" in h)
                if link:
                    title_elem = link.find(class_=lambda c: c and "_title_" in str(c))
                    title = title_elem.get_text(strip=True) if title_elem else f"Part {idx}"

                    url = link.get('href', '')
                    if not url.startswith('http'):
                        url = 'https://www.literotica.com' + url

                    parts.append({
                        'part_number': idx,
                        'title': title,
                        'url': url
                    })

            series_title_elem = soup.find("h1", class_=lambda c: c and "_title_" in str(c))
            series_title = series_title_elem.get_text(strip=True) if series_title_elem else None

            log_action(f"Series page check: found {len(parts)} parts")

            return {
                'total_parts': len(parts),
                'parts': parts,
                'series_title': series_title
            }

        except Exception as e:
            log_error(f"Error checking series page {series_url}: {str(e)}")
            return None
