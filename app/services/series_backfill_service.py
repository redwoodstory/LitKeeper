from __future__ import annotations
from typing import Optional, Dict
from bs4 import BeautifulSoup
import time
from app.models import Story, db
from .story_downloader import get_session
from .logger import log_action, log_error

class SeriesBackfillService:
    """Backfill series URLs for existing stories."""

    def backfill_all_stories(self) -> Dict:
        """Process all stories missing series URLs."""
        stories = Story.query.filter(
            Story.literotica_url.isnot(None),
            Story.literotica_series_url.is_(None)
        ).all()

        results = {
            'total': len(stories),
            'updated': 0,
            'no_series': 0,
            'errors': 0
        }

        log_action(f"Starting series backfill for {results['total']} stories")

        for story in stories:
            try:
                series_url = self.extract_series_url(story.literotica_url)

                if series_url:
                    story.literotica_series_url = series_url
                    db.session.commit()
                    results['updated'] += 1
                    log_action(f"Added series URL for '{story.title}'")
                else:
                    results['no_series'] += 1

                time.sleep(3)

            except Exception as e:
                results['errors'] += 1
                log_error(f"Error backfilling '{story.title}': {str(e)}")
                db.session.rollback()

        log_action(f"Backfill complete: {results['updated']} updated, {results['no_series']} not in series, {results['errors']} errors")
        return results

    def extract_series_url(self, story_url: str) -> Optional[str]:
        """Fetch story page and extract series URL if exists."""
        try:
            session = get_session()
            response = session.get(story_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for section in soup.find_all("section", class_=lambda c: c and "_panel_" in str(c)):
                heading = section.find("h3", class_=lambda c: c and "_heading_" in str(c))
                if heading and "READ MORE OF THIS SERIES" in heading.get_text(strip=True):
                    series_link = section.find("a", href=lambda h: h and "/series/se/" in h)
                    if series_link:
                        url = series_link.get("href", "")
                        if not url.startswith("http"):
                            url = "https://www.literotica.com" + url
                        return url

            return None

        except Exception as e:
            log_error(f"Error extracting series URL from {story_url}: {str(e)}")
            return None
