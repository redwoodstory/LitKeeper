from __future__ import annotations
import html as html_module
import re
from bs4 import BeautifulSoup
from .story_downloader import get_session
from .logger import log_action, log_error

# (slug, display_label, top_path)
# slug: used for the SPA /c/{slug}/new-{slug} newest URL
# top_path: used for the /top/{top_path} rated pages
CATEGORIES: list[tuple[str, str, str]] = [
    ('erotic-couplings',        'Erotic Couplings',          'Erotic-Couplings-2'),
    ('loving-wives',            'Loving Wives',               'Loving-Wives-12'),
    ('gay-sex-stories',         'Gay Male',                   'Gay-Male-6'),
    ('lesbian-sex-stories',     'Lesbian Sex',                'Lesbian-Sex-11'),
    ('mature-sex',              'Mature',                     'Mature-26'),
    ('adult-romance',           'Romance',                    'Romance-15'),
    ('bdsm-stories',            'BDSM',                       'BDSM-31'),
    ('non-consent-stories',     'Reluctance / NonConsent',    'Reluctance-NonConsent-13'),
    ('erotic-horror',           'Erotic Horror',              'Erotic-Horror-51'),
    ('science-fiction-fantasy', 'Sci-Fi & Fantasy',           'Sci-Fi-Fantasy-38'),
    ('mind-control',            'Mind Control',               'Mind-Control-29'),
    ('non-human-stories',       'NonHuman',                   'NonHuman-14'),
    ('taboo-sex-stories',       'Taboo / Incest',             'Taboo-Incest-9'),
    ('interracial-erotic-stories', 'Interracial Love',        'Interracial-Love-10'),
    ('group-sex-stories',       'Group Sex',                  'Group-Sex-7'),
    ('first-time-sex-stories',  'First Time',                 'First-Time-40'),
    ('exhibitionist-voyeur',    'Exhibitionist & Voyeur',     'Exhibitionist-Voyeur-4'),
    ('fetish-stories',          'Fetish',                     'Fetish-5'),
    ('anal-sex-stories',        'Anal',                       'Anal-37'),
    ('transgender',             'Transgender',                'Transgender-48'),
    ('crossdressing',           'Crossdressing',              'Crossdressing-58'),
    ('celebrity-stories',       'Fan Fiction & Celebrities',  'Fan-Fiction-Celebrities-27'),
    ('masturbation-stories',    'Toys & Masturbation',        'Toys-Masturbation-16'),
    ('erotic-novels',           'Novels and Novellas',        'Novels-and-Novellas-33'),
    ('non-erotic-stories',      'Non-Erotic',                 'Non-Erotic-35'),
    ('adult-humor',             'Humor & Satire',             'Humor-Satire-34'),
    ('adult-how-to',            'How To',                     'How-To-8'),
    ('reviews-and-essays',      'Reviews & Essays',           'Reviews-Essays-3'),
    ('chain-stories',           'Chain Stories',              'Chain-Stories-28'),
    ('audio-sex-stories',       'Audio',                      'Audio-39'),
    ('illustrated-erotic-fiction', 'Illustrated',             'Illustrated-45'),
    ('erotic-letters',          'Letters & Transcripts',      'Letters-Transcripts-53'),
]

_BY_SLUG = {slug: (label, top_path) for slug, label, top_path in CATEGORIES}

# Sort modes that use the legacy /top/ pages (have rating count + pagination)
_TOP_SORT_PATHS = {
    'top_all':  '{top_path}/alltime/',
    'top_30d':  '{top_path}/last-30-days/',
    'top_12mo': '{top_path}/last-12-months/',
}
_TOP_SORT_EXTRA_PARAMS = {
    'top_all':  '',
    'top_30d':  '&mode=publishes',
    'top_12mo': '&mode=publishes',
}

_DATE_RE = re.compile(r'\((\d{2}/\d{2}/\d{2,4})\)\s*$')

GLOBAL_MODES = ('top_rated', 'most_read', 'newest')

_GLOBAL_URLS = {
    'top_rated': 'https://www.literotica.com/top/top-rated-erotic-stories/',
    'most_read': 'https://www.literotica.com/top/most-read-erotic-stories/',
    'newest':    'https://www.literotica.com/new/stories',
}


def valid_category(slug: str) -> bool:
    return slug in _BY_SLUG


class CategoryScraper:

    def fetch_category(self, slug: str, sort: str = 'top_all', page: int = 1) -> dict:
        """
        Returns:
            {stories: [...], page: int, total_pages: int}
        Each story dict:
            url, title, score, vote_count, date_approve, description, author_name, author_url
        """
        info = _BY_SLUG.get(slug)
        if not info:
            return {'stories': [], 'page': 1, 'total_pages': 1}

        label, top_path = info

        if sort == 'newest':
            stories = self._fetch_newest(slug)
            return {'stories': stories, 'page': 1, 'total_pages': 1}

        if sort not in _TOP_SORT_PATHS:
            sort = 'top_all'

        path = _TOP_SORT_PATHS[sort].format(top_path=top_path)
        extra = _TOP_SORT_EXTRA_PARAMS[sort]
        url = f'https://www.literotica.com/top/{path}?page={page}{extra}'
        log_action(f"[CategoryScraper] Fetching {url}")

        session = get_session()
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
        except Exception as e:
            log_error(f"[CategoryScraper] Fetch failed: {e}")
            return {'stories': [], 'page': page, 'total_pages': 1}

        soup = BeautifulSoup(resp.text, 'html.parser')
        stories = self._parse_top_page(soup)
        total_pages = self._parse_total_pages(soup)
        log_action(f"[CategoryScraper] Parsed {len(stories)} stories, {total_pages} total pages")
        return {'stories': stories, 'page': page, 'total_pages': total_pages}

    # ------------------------------------------------------------------
    # Legacy /top/ page parser (table-based HTML, has vote counts)
    # ------------------------------------------------------------------

    def fetch_global(self, mode: str, page: int = 1) -> dict:
        """
        Returns:
            {stories: [...], page: int, total_pages: int}
        mode ∈ ('top_rated', 'most_read', 'newest')
        """
        if mode not in GLOBAL_MODES:
            return {'stories': [], 'page': 1, 'total_pages': 1}

        if mode == 'newest':
            url = _GLOBAL_URLS['newest']
            log_action(f"[CategoryScraper] Fetching global newest: {url}")
            session = get_session()
            try:
                resp = session.get(url, timeout=25)
                resp.raise_for_status()
            except Exception as e:
                log_error(f"[CategoryScraper] Fetch failed: {e}")
                return {'stories': [], 'page': 1, 'total_pages': 1}
            soup = BeautifulSoup(resp.text, 'html.parser')
            stories = self._parse_spa_stories(soup)
            log_action(f"[CategoryScraper] Parsed {len(stories)} global newest stories")
            return {'stories': stories, 'page': 1, 'total_pages': 1}

        url = _GLOBAL_URLS[mode] + f'?page={page}'
        log_action(f"[CategoryScraper] Fetching global {mode}: {url}")
        session = get_session()
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
        except Exception as e:
            log_error(f"[CategoryScraper] Fetch failed: {e}")
            return {'stories': [], 'page': page, 'total_pages': 1}

        soup = BeautifulSoup(resp.text, 'html.parser')
        parse_mode = 'read' if mode == 'most_read' else 'rated'
        stories = self._parse_top_page(soup, parse_mode=parse_mode)
        total_pages = self._parse_total_pages(soup)
        log_action(f"[CategoryScraper] Parsed {len(stories)} stories, {total_pages} total pages")
        return {'stories': stories, 'page': page, 'total_pages': total_pages}

    # ------------------------------------------------------------------
    # Legacy /top/ page parser (table-based HTML, has vote counts)
    # ------------------------------------------------------------------

    def _parse_top_page(self, soup: BeautifulSoup, parse_mode: str = 'rated') -> list[dict]:
        results = []
        for row in soup.select('table.tbl tr'):
            story = self._parse_top_row(row, parse_mode=parse_mode)
            if story:
                results.append(story)
        return results

    def _parse_top_row(self, row, parse_mode: str = 'rated') -> dict | None:
        title_a = row.select_one('td.mcol a.title')
        if not title_a:
            return None

        url = title_a.get('href', '').split('?')[0]
        if not url:
            return None
        title = html_module.unescape(title_a.get_text(strip=True))

        score: str | None = None
        vote_count: str | None = None
        read_count: str | None = None

        if parse_mode == 'read':
            vc = row.select_one('td.viewcount')
            if vc:
                read_count = vc.get_text(strip=True) or None
        else:
            rc = row.select_one('td.ratecount span')
            if rc:
                text = rc.get_text(strip=True)
                m = re.match(r'([\d.]+)\s*\((\d+)\)', text)
                if m:
                    score = m.group(1)
                    vote_count = m.group(2)

        desc_tag = row.select_one('span.des')
        description: str | None = None
        if desc_tag:
            raw = html_module.unescape(desc_tag.get('title') or desc_tag.get_text(strip=True))
            description = raw[:200] if len(raw) > 200 else raw or None

        author_a = row.select_one('td.mcol a[href*="/authors/"]')
        author_name: str | None = None
        author_url: str | None = None
        if author_a:
            author_name = html_module.unescape(author_a.get_text(strip=True)) or None
            ah = author_a.get('href', '')
            if ah and not ah.startswith('http'):
                ah = 'https://www.literotica.com' + ah
            author_url = ah or None

        date_approve: str | None = None
        mcol = row.select_one('td.mcol')
        if mcol:
            cell_text = mcol.get_text(' ', strip=True)
            dm = _DATE_RE.search(cell_text)
            if dm:
                raw_date = dm.group(1)
                parts = raw_date.split('/')
                if len(parts) == 3 and len(parts[2]) == 2:
                    parts[2] = '20' + parts[2]
                date_approve = '/'.join(parts)

        return {
            'url': url,
            'title': title,
            'score': score,
            'vote_count': vote_count,
            'read_count': read_count,
            'date_approve': date_approve,
            'description': description,
            'author_name': author_name,
            'author_url': author_url,
        }

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        max_page = 1
        for a in soup.select('div.pager a[href]'):
            try:
                n = int(a.get_text(strip=True))
                if n > max_page:
                    max_page = n
            except ValueError:
                pass
        return max_page

    # ------------------------------------------------------------------
    # SPA newest page parser (no vote counts, no pagination)
    # ------------------------------------------------------------------

    def _fetch_newest(self, slug: str) -> list[dict]:
        url = f'https://www.literotica.com/c/{slug}/new-{slug}'
        log_action(f"[CategoryScraper] Fetching newest: {url}")
        session = get_session()
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
        except Exception as e:
            log_error(f"[CategoryScraper] Fetch failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        return self._parse_spa_stories(soup)

    def _parse_spa_stories(self, soup: BeautifulSoup) -> list[dict]:
        results = []
        seen: set[str] = set()
        for item in soup.find_all(lambda t: t.name in ('div', 'article') and self._has_prefix(t, '_works_item_')):
            story = self._parse_spa_item(item)
            if story and story['url'] not in seen:
                seen.add(story['url'])
                results.append(story)
        return results

    @staticmethod
    def _has_prefix(tag, prefix: str) -> bool:
        classes = tag.get('class', [])
        if isinstance(classes, str):
            classes = classes.split()
        return any(prefix in c for c in classes)

    def _parse_spa_item(self, item) -> dict | None:
        title_a = item.find('a', class_=lambda c: c and any(
            '_item_title_' in x for x in (c if isinstance(c, list) else c.split())))
        if not title_a:
            return None

        href = title_a.get('href', '').split('?')[0]
        if not href:
            return None
        if not href.startswith('http'):
            href = 'https://www.literotica.com' + href
        title = html_module.unescape(title_a.get_text(strip=True))

        score: str | None = None
        for stat in item.find_all('span', class_=lambda c: c and any(
                '_work_item__stat_' in x for x in (c if isinstance(c, list) else c.split()))):
            if 'Rating' not in stat.get_text(strip=True):
                continue
            val_span = stat.find('span', class_=lambda c: c and any(
                '_stats__text_' in x for x in (c if isinstance(c, list) else c.split())))
            if val_span:
                try:
                    v = float(val_span.get_text(strip=True))
                    if 1.0 <= v <= 5.0:
                        score = val_span.get_text(strip=True)
                        break
                except ValueError:
                    pass

        date_tag = item.find('time', class_=lambda c: c and any(
            '_date_approve_' in x for x in (c if isinstance(c, list) else c.split())))
        date_approve = html_module.unescape(date_tag.get_text(strip=True)) if date_tag else None

        desc_tag = item.find('p', class_=lambda c: c and any(
            '_item_description_' in x for x in (c if isinstance(c, list) else c.split())))
        description: str | None = None
        if desc_tag:
            raw = html_module.unescape(desc_tag.get_text(strip=True))
            description = raw[:200] if len(raw) > 200 else raw or None

        author_a = item.find('a', class_=lambda c: c and any(
            '_item_authorname_link_' in x for x in (c if isinstance(c, list) else c.split())))
        author_name: str | None = None
        author_url: str | None = None
        if author_a:
            author_name = html_module.unescape(author_a.get_text(strip=True)) or None
            ah = author_a.get('href', '').split('?')[0]
            if ah:
                if not ah.startswith('http'):
                    ah = 'https://www.literotica.com' + ah
                author_url = ah

        return {
            'url': href,
            'title': title,
            'score': score,
            'vote_count': None,
            'read_count': None,
            'date_approve': date_approve,
            'description': description,
            'author_name': author_name,
            'author_url': author_url,
        }
