from __future__ import annotations
import re
import time
import random
import html as html_module
from typing import Optional
from bs4 import BeautifulSoup
from .story_downloader import get_session
from .logger import log_action, log_error

_STORY_SLUG_RE = re.compile(r"""url:["']([a-z0-9][a-z0-9-]{4,80})["']""")


def normalize_author_url(url: str) -> Optional[str]:
    """
    Normalize an author URL to the canonical /authors/<username> form.

    Accepts formats like:
      https://www.literotica.com/authors/jphalpert
      https://www.literotica.com/authors/jphalpert/works
      https://www.literotica.com/stories/memberpage.php?uid=...&page=submissions
    Returns the base /authors/<username> URL, or None if unrecognised.
    """
    url = url.strip()

    m = re.match(r'https?://(?:www\.)?literotica\.com/authors/([^/?#]+)', url)
    if m:
        return f'https://www.literotica.com/authors/{m.group(1)}'

    m = re.match(r'https?://(?:www\.)?literotica\.com/stories/memberpage\.php\?uid=(\d+)', url)
    if m:
        return f'https://www.literotica.com/stories/memberpage.php?uid={m.group(1)}&page=submissions'

    return None


def is_author_url(url: str) -> bool:
    """Return True if the URL looks like a Literotica author page."""
    return bool(
        re.search(r'literotica\.com/authors/', url) or
        re.search(r'literotica\.com/stories/memberpage\.php\?uid=', url)
    )


class AuthorScraper:
    """Scrape an author's Literotica profile to discover their stories/series."""

    def scrape_story_urls(self, author_url: str) -> list[dict]:
        """
        Fetch the author's profile page and return a deduplicated list of
        story/series dicts.

        Each dict has:
            url (str): story chapter URL (for standalone stories) or series URL
            title (str): story title
            is_series (bool): True when this entry represents a series

        Stories that share a series are collapsed to a single series entry.
        """
        canonical = normalize_author_url(author_url)
        if not canonical:
            log_error(f"Cannot normalise author URL: {author_url}")
            return []

        log_action(f"[AuthorScraper] Starting scrape for: {canonical}")

        jitter = random.randint(5, 15)
        log_action(f"[AuthorScraper] Waiting {jitter}s before fetching author page")
        time.sleep(jitter)

        session = get_session()
        stories = self._fetch_works_page(session, canonical)

        if not stories:
            log_action(f"[AuthorScraper] No stories found via works page, trying legacy memberpage")
            stories = self._fetch_memberpage(session, canonical)

        log_action(f"[AuthorScraper] Found {len(stories)} distinct story/series entries")
        return stories

    def _fetch_works_page(self, session, author_url: str) -> list[dict]:
        """Fetch the /authors/<username>/works page (modern Literotica)."""
        works_url = author_url.rstrip('/') + '/works'
        try:
            resp = session.get(works_url, timeout=15)
            if resp.status_code == 404:
                log_action(f"[AuthorScraper] works page 404, will try memberpage")
                return []
            resp.raise_for_status()
            return self._parse_works_html(resp.text, author_url)
        except Exception as e:
            log_error(f"[AuthorScraper] Error fetching works page {works_url}: {e}")
            return []

    def _parse_works_html(self, html: str, author_url: str) -> list[dict]:
        """
        Parse the author's works/submissions page.

        Phase 0: Extract story slugs from the SolidJS $R hydration data embedded
        in the largest inline <script> tag.  This gives us the full list of
        individual stories regardless of how many the SPA renders as <a> tags.

        Phase 1+2: Walk <a> tags to capture /series/se/ links (series are not
        included in the hydration slug list) and any /s/ links not already found
        in Phase 0.
        """
        soup = BeautifulSoup(html, 'html.parser')
        results: list[dict] = []
        seen_series: set[str] = set()
        seen_story: set[str] = set()

        # Phase 0 — hydration data (SolidJS $R inline script)
        # Literotica embeds all story objects as `url:'slug'` properties inside
        # the largest inline <script> tag.  We extract every slug and build the
        # canonical /s/ URL so that stories only rendered client-side are included.
        scripts = soup.find_all('script', src=False)
        if scripts:
            biggest = max(scripts, key=lambda s: len(s.get_text()))
            script_text = biggest.get_text()
            for slug in _STORY_SLUG_RE.findall(script_text):
                clean = f'https://www.literotica.com/s/{slug}'
                if clean not in seen_story:
                    seen_story.add(clean)
                    results.append({'url': clean, 'title': slug.replace('-', ' ').title(), 'is_series': False})
            log_action(f"[AuthorScraper] Phase 0 hydration: found {len(seen_story)} story slugs")

        # Phase 1: find the grouping container for each series link and collect
        # the /s/ chapter URLs within it.  Also build a mapping from each series
        # URL to its known chapter URLs so Phase 2 can suppress a series entry
        # when Phase 0 already found those chapters via hydration data.
        # We walk UP the DOM from each /series/se/ link and look for the tightest
        # container that has both the series link and /s/ chapter links, using a
        # link-count size guard to avoid treating the whole page as a series group.
        _HARD_STOP_TAGS = {'html', 'body', '[document]'}
        _MAX_LINKS_IN_GROUP = 20  # a series group shouldn't contain more than this many links
        series_chapter_urls: set[str] = set()
        series_to_chapters: dict[str, set[str]] = {}

        for series_link in soup.find_all('a', href=lambda h: h and '/series/se/' in h):
            series_href = series_link['href'].split('?')[0]
            if not series_href.startswith('http'):
                series_href = 'https://www.literotica.com' + series_href

            container = series_link.parent
            for _ in range(8):
                if container is None:
                    break
                tag_name = getattr(container, 'name', None)
                if tag_name in _HARD_STOP_TAGS:
                    break
                all_links_here = container.find_all('a', href=True)
                chapter_links = [a for a in all_links_here if '/s/' in a.get('href', '')]
                if chapter_links:
                    if len(all_links_here) <= _MAX_LINKS_IN_GROUP:
                        # This is a tight grouping — collect the chapter URLs
                        chapters: set[str] = set()
                        for cl in chapter_links:
                            href = cl['href'].split('?')[0]
                            if not href.startswith('http'):
                                href = 'https://www.literotica.com' + href
                            series_chapter_urls.add(href)
                            chapters.add(href)
                        series_to_chapters[series_href] = chapters
                    # Either we collected chapters from a tight group, or the container
                    # is too large (whole-page level) — either way, stop climbing.
                    break
                container = container.parent

        # Phase 2: collect series entries + standalone stories.
        for link in soup.find_all('a', href=True):
            href = link['href']
            if not href.startswith('http'):
                href = 'https://www.literotica.com' + href

            if '/series/se/' in href:
                clean = href.split('?')[0]
                # Suppress the series URL if Phase 0 already found any of its
                # chapter slugs — those individual URLs will trigger the full
                # series download on their own, making this entry redundant.
                known_chapters = series_to_chapters.get(clean, set())
                if known_chapters & seen_story:
                    continue
                if clean not in seen_series:
                    seen_series.add(clean)
                    title = html_module.unescape(link.get_text(strip=True)) or 'Unknown Series'
                    results.append({'url': clean, 'title': title, 'is_series': True})

            elif '/s/' in href:
                clean = href.split('?')[0]
                if clean in series_chapter_urls:
                    continue
                if clean not in seen_story:
                    seen_story.add(clean)
                    title = html_module.unescape(link.get_text(strip=True)) or 'Unknown Story'
                    results.append({'url': clean, 'title': title, 'is_series': False})

        return results

    def _fetch_memberpage(self, session, author_url: str) -> list[dict]:
        """Legacy memberpage scrape fallback."""
        try:
            resp = session.get(author_url, timeout=15)
            resp.raise_for_status()
            return self._parse_works_html(resp.text, author_url)
        except Exception as e:
            log_error(f"[AuthorScraper] Error fetching memberpage {author_url}: {e}")
            return []
