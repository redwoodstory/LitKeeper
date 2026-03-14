from __future__ import annotations
import requests
from bs4 import BeautifulSoup
import time
import random
import traceback
from typing import Optional
from .logger import log_url, log_error

def get_random_user_agent() -> str:
    """Return a random User-Agent string from a broad pool of real browser UAs."""
    USER_AGENTS = [
        # Chrome on Windows (various versions)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on macOS (various versions)
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:120.0) Gecko/20100101 Firefox/120.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        # Edge on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    ]
    return random.choice(USER_AGENTS)

def get_session() -> requests.Session:
    """Create and return a session with default headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    return session

def detect_url_type(url: str) -> tuple[str, Optional[str]]:
    """
    Detect URL type and extract base URL.

    Returns:
        tuple[url_type, series_url]
        url_type: 'series', 'chapter', or 'unknown'
        series_url: The series URL if type is 'series', None otherwise
    """
    if '/series/se/' in url:
        return 'series', url
    elif '/s/' in url:
        return 'chapter', None
    else:
        return 'unknown', None

def _clean_series_title(title: str) -> str:
    """
    Clean series title by removing chapter number suffixes.

    Examples:
        "My Story Ch. 01" -> "My Story"
        "My Story: Ch 02" -> "My Story"
        "My Story Pt. 1" -> "My Story"
    """
    import re

    patterns = [
        r'\s*:\s*Ch\.?\s*\d+$',
        r'\s+Ch\.?\s*\d+$',
        r'\s*:\s*Pt\.?\s*\d+$',
        r'\s+Pt\.?\s*\d+$',
        r'\s*:\s*Part\s+\d+$',
        r'\s+Part\s+\d+$',
    ]

    cleaned = title
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()

def extract_series_url_from_chapter(chapter_url: str, session: requests.Session) -> Optional[str]:
    """
    Extract series URL from a chapter page's 'READ MORE OF THIS SERIES' section.

    Returns:
        Series URL if found, None otherwise
    """
    try:
        from .logger import log_action
        log_action(f"Attempting to extract series URL from chapter: {chapter_url}")
        response = session.get(chapter_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        series_link = soup.find("a", href=lambda h: h and "/series/se/" in h)
        if series_link:
            series_url = series_link.get("href", "")
            if not series_url.startswith("http"):
                series_url = "https://www.literotica.com" + series_url
            log_action(f"Found series URL: {series_url}")
            return series_url

        log_action("No series URL found in chapter page")
        return None

    except Exception as e:
        log_error(f"Error extracting series URL from chapter: {str(e)}", chapter_url)
        return None

def _download_single_chapter(
    chapter_url: str,
    session: requests.Session,
    is_first_chapter: bool = False
) -> tuple[str, dict]:
    """
    Download all pages of a single chapter.

    Returns:
        tuple[chapter_content, metadata_dict]
        metadata_dict contains: author, author_url, category, tags, page_count
    """
    import html as html_module
    chapter_content = ""
    current_page = 1
    page_count = 0
    current_url = chapter_url

    metadata = {
        'author': 'Unknown Author',
        'author_url': None,
        'category': None,
        'tags': [],
        'page_count': 0,
        'description': None
    }

    while current_url:
        try:
            response = session.get(current_url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(response.text, "html.parser")

            if current_page == 1 and is_first_chapter:
                author_tag = soup.find("a", class_=lambda c: c and "_author__title_" in str(c))
                if author_tag:
                    metadata['author'] = html_module.unescape(author_tag.text.strip())
                    if author_tag.get('href'):
                        author_href = author_tag.get('href')
                        if not author_href.startswith('http'):
                            metadata['author_url'] = 'https://www.literotica.com' + author_href
                        else:
                            metadata['author_url'] = author_href

                breadcrumb = soup.find("nav", class_=lambda c: c and "_breadcrumbs_" in str(c))
                if breadcrumb:
                    breadcrumb_items = breadcrumb.find_all("span", itemprop="name")
                    if len(breadcrumb_items) >= 2:
                        metadata['category'] = breadcrumb_items[1].text.strip()
                        if "taboo" in metadata['category'].lower():
                            metadata['category'] = "I/T"

                tag_elements = soup.find_all("a", class_=lambda c: c and "_tags__link_" in str(c))
                metadata['tags'] = [tag.text.strip() for tag in tag_elements
                                   if not tag.text.strip().lower().startswith("inc")]
                if metadata['category'] and metadata['category'] not in metadata['tags']:
                    metadata['tags'] = [metadata['category']] + metadata['tags']

                og_desc = soup.find("meta", attrs={"property": "og:description"})
                if og_desc and og_desc.get("content", "").strip():
                    metadata['description'] = og_desc.get("content").strip()
                else:
                    desc_elem = soup.find("div", class_=lambda c: c and "_widget__info_" in str(c))
                    metadata['description'] = desc_elem.get_text(strip=True) if desc_elem else None

            content_div = soup.find("div", class_=lambda c: c and "_article__content_" in str(c))
            if content_div:
                for paragraph in content_div.find_all("p"):
                    chapter_content += paragraph.get_text(strip=True) + "\n\n"

            page_count += 1

            next_page_link = None
            pagination_links = soup.find_all("a", class_=lambda c: c and "_pagination__item_" in str(c))
            for link in pagination_links:
                href = link.get("href", "")
                if f"?page={current_page + 1}" in href or f"&page={current_page + 1}" in href:
                    next_page_link = link
                    break

            if next_page_link:
                next_url = next_page_link["href"]
                if not next_url.startswith("http"):
                    next_url = "https://www.literotica.com" + next_url
                current_url = next_url
                current_page += 1
                time.sleep(3)
            else:
                current_url = None

        except Exception as e:
            log_error(f"Error downloading chapter page {current_page}: {str(e)}", current_url)
            return "", metadata

    metadata['page_count'] = page_count
    return chapter_content, metadata

def _download_from_series_page(
    series_url: str,
    session: requests.Session
) -> Optional[tuple[str, str, str, Optional[str], Optional[list[str]], Optional[str], int, str, Optional[str]]]:
    """
    Download complete story using series page as source of truth.

    Returns:
        Same tuple as download_story() or None if failed
    """
    from .series_page_checker import SeriesPageChecker
    from .logger import log_action

    try:
        checker = SeriesPageChecker()
        series_info = checker.check_series_parts(series_url)

        if not series_info or not series_info.get('parts'):
            log_action("Series page parser returned no parts")
            return None

        series_title = series_info.get('series_title', 'Unknown Series')
        parts = series_info['parts']
        total_parts = len(parts)
        series_description = series_info.get('description')

        log_action(f"Series '{series_title}' has {total_parts} parts")

        story_author = "Unknown Author"
        story_author_url = None
        story_category = None
        story_tags = []
        story_description = None
        total_pages = 0
        chapter_titles = []
        chapter_contents = []

        for idx, part in enumerate(parts, 1):
            part_url = part['url']
            part_title = part['title']
            log_action(f"Downloading part {idx}/{total_parts}: {part_title}")

            chapter_content, chapter_metadata = _download_single_chapter(
                part_url,
                session,
                is_first_chapter=(idx == 1)
            )

            if not chapter_content:
                log_error(f"Failed to download part {idx}", part_url)
                return None

            chapter_contents.append(chapter_content)
            chapter_titles.append(part_title)
            total_pages += chapter_metadata['page_count']

            if idx == 1:
                story_author = chapter_metadata['author']
                story_author_url = chapter_metadata['author_url']
                story_category = chapter_metadata['category']
                story_tags = chapter_metadata['tags']
                story_description = chapter_metadata.get('description') or series_description

            time.sleep(3)

        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"

        clean_title = _clean_series_title(series_title)

        return (
            story_content,
            clean_title,
            story_author,
            story_category,
            story_tags,
            story_author_url,
            total_pages,
            series_url,
            story_description
        )

    except Exception as e:
        log_error(f"Error in series-first download: {str(e)}", series_url)
        return None

def download_story(url: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[list[str]], Optional[str], Optional[int], Optional[str], Optional[str]]:
    """Download and extract the full story content and metadata from the given Literotica URL."""
    try:
        session = get_session()
        
        url = url.split('?')[0]
        from .logger import log_action
        log_action(f"Normalized URL to start from page 1: {url}")

        url_type, series_url = detect_url_type(url)
        log_url(f"URL type detected: {url_type}")

        if url_type == 'chapter':
            series_url = extract_series_url_from_chapter(url, session)

        if series_url:
            try:
                result = _download_from_series_page(series_url, session)
                if result:
                    log_url(f"Successfully downloaded via series page")
                    return result
                else:
                    log_url("Series download failed, falling back to sequential method")
            except Exception as e:
                log_error(f"Error in series-first download: {str(e)}", series_url)
                log_url("Falling back to sequential chapter download method")

        log_url("Using sequential chapter download method")

        story_content = ""
        current_page = 1
        total_pages = 0
        story_title = "Unknown Title"
        story_author = "Unknown Author"
        story_category = None
        story_tags = []
        story_author_url = None
        story_description = None
        series_url = None
        chapter_urls = [url]
        processed_urls = set()
        series_title = None
        chapter_titles = []
        chapter_contents = []

        while chapter_urls:
            current_url = chapter_urls.pop(0)
            if current_url in processed_urls:
                continue
                
            processed_urls.add(current_url)
            current_chapter = len(chapter_contents) + 1
            current_chapter_content = ""
            log_url(current_url)

            while current_url:
                try:
                    response = session.get(current_url, timeout=10)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding or 'utf-8'

                    soup = BeautifulSoup(response.text, "html.parser")

                    if current_page == 1:
                        title_tag = soup.find("h1", class_=lambda c: c and c.startswith("_title_"))
                        author_tag = soup.find("a", class_=lambda c: c and "_author__title_" in str(c))
                        current_title = title_tag.text.strip() if title_tag else "Unknown Chapter"

                        import html
                        current_title = html.unescape(current_title)

                        if current_chapter == 1:
                            story_title = current_title
                            story_author = author_tag.text.strip() if author_tag else story_author
                            story_author = html.unescape(story_author)

                            if author_tag and author_tag.get('href'):
                                author_href = author_tag.get('href')
                                if not author_href.startswith('http'):
                                    story_author_url = 'https://www.literotica.com' + author_href
                                else:
                                    story_author_url = author_href

                            breadcrumb = soup.find("nav", class_=lambda c: c and "_breadcrumbs_" in str(c))
                            if breadcrumb:
                                breadcrumb_items = breadcrumb.find_all("span", itemprop="name")
                                if len(breadcrumb_items) >= 2:
                                    story_category = breadcrumb_items[1].text.strip()
                                    if "taboo" in story_category.lower():
                                        story_category = "I/T"

                            tag_elements = soup.find_all("a", class_=lambda c: c and "_tags__link_" in str(c))
                            story_tags = [tag.text.strip() for tag in tag_elements
                                        if not tag.text.strip().lower().startswith("inc")]
                            if story_category and story_category not in story_tags:
                                story_tags = [story_category] + story_tags

                            og_desc = soup.find("meta", attrs={"property": "og:description"})
                            if og_desc and og_desc.get("content", "").strip():
                                story_description = og_desc.get("content").strip()
                            else:
                                desc_elem = soup.find("div", class_=lambda c: c and "_widget__info_" in str(c))
                                story_description = desc_elem.get_text(strip=True) if desc_elem else None

                    content_div = soup.find("div", class_=lambda c: c and "_article__content_" in str(c))
                    if content_div:
                        if current_page == 1:
                            chapter_titles.append(current_title)

                        for paragraph in content_div.find_all("p"):
                            current_chapter_content += paragraph.get_text(strip=True) + "\n\n"

                    total_pages += 1
                    next_page_link = None
                    pagination_links = soup.find_all("a", class_=lambda c: c and "_pagination__item_" in str(c))
                    for link in pagination_links:
                        href = link.get("href", "")
                        if f"?page={current_page + 1}" in href or f"&page={current_page + 1}" in href:
                            next_page_link = link
                            break

                    if next_page_link:
                        next_url = next_page_link["href"]
                        if not next_url.startswith("http"):
                            next_url = "https://www.literotica.com" + next_url
                        current_url = next_url
                        current_page += 1
                    else:
                        chapter_contents.append(current_chapter_content)
                        
                        series_section = None
                        for section in soup.find_all("section", class_=lambda c: c and "_panel_" in str(c)):
                            heading = section.find("h3", class_=lambda c: c and "_heading_" in str(c))
                            if heading and heading.get_text(strip=True) == "READ MORE OF THIS SERIES":
                                series_section = section
                                break

                        if series_section:
                            if not series_url:
                                series_link = series_section.find("a", href=lambda h: h and "/series/se/" in h)
                                if series_link:
                                    series_url = series_link.get("href", "")
                                    if not series_url.startswith("http"):
                                        series_url = "https://www.literotica.com" + series_url

                            data_list = series_section.find("div", class_=lambda c: c and "_data_list_" in str(c))
                            if data_list:
                                items = data_list.find_all("div", class_=lambda c: c and "_item_" in str(c))

                                for item in items:
                                    next_part_span = item.find("span", string=lambda s: s and "Next Part" in s)
                                    if next_part_span:
                                        link = item.find("a", href=lambda h: h and "/s/" in h)
                                        if link:
                                            next_url = link.get("href", "")
                                            if not next_url.startswith("http"):
                                                next_url = "https://www.literotica.com" + next_url

                                            base_next_url = next_url.split("?")[0]

                                            if base_next_url not in processed_urls:
                                                chapter_urls.append(base_next_url)
                                                break

                        current_url = None
                        current_page = 1

                    time.sleep(3)

                except requests.RequestException as e:
                    error_msg = f"Network error while downloading chapter {current_chapter}: {str(e)}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None, None, None, None, None
                except Exception as e:
                    error_msg = f"Error processing chapter {current_chapter}: {str(e)}\n{traceback.format_exc()}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None, None, None, None, None

        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"

        return story_content, story_title, story_author, story_category, story_tags, story_author_url, total_pages, series_url, story_description

    except Exception as e:
        error_msg = f"Unexpected error in download_story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        return None, None, None, None, None, None, None, None, None

def fetch_story_metadata(url: str) -> dict:
    """
    Fetch only metadata from the first page of a story URL without downloading content.

    Returns a dict with: title, author, author_url, category, tags, page_count, series_url.
    Returns an empty dict on failure.
    """
    import html as html_module
    import re

    try:
        session = get_session()
        url = url.split('?')[0]

        response = session.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        title_tag = soup.find('h1', class_=lambda c: c and c.startswith('_title_'))
        title = html_module.unescape(title_tag.text.strip()) if title_tag else 'Unknown Title'

        author_tag = soup.find('a', class_=lambda c: c and '_author__title_' in str(c))
        author = html_module.unescape(author_tag.text.strip()) if author_tag else 'Unknown Author'
        author_url = None
        if author_tag and author_tag.get('href'):
            href = author_tag.get('href')
            author_url = href if href.startswith('http') else 'https://www.literotica.com' + href

        category = None
        breadcrumb = soup.find('nav', class_=lambda c: c and '_breadcrumbs_' in str(c))
        if breadcrumb:
            items = breadcrumb.find_all('span', itemprop='name')
            if len(items) >= 2:
                category = items[1].text.strip()
                if 'taboo' in category.lower():
                    category = 'I/T'

        tag_elements = soup.find_all('a', class_=lambda c: c and '_tags__link_' in str(c))
        tags = [t.text.strip() for t in tag_elements
                if not t.text.strip().lower().startswith('inc')]
        if category and category not in tags:
            tags = [category] + tags

        page_count = 1
        pagination_links = soup.find_all('a', class_=lambda c: c and '_pagination__item_' in str(c))
        for link in pagination_links:
            match = re.search(r'[?&]page=(\d+)', link.get('href', ''))
            if match:
                page_count = max(page_count, int(match.group(1)))

        series_url = None
        series_link = soup.find('a', href=lambda h: h and '/series/se/' in h)
        if series_link:
            href = series_link.get('href', '')
            series_url = href if href.startswith('http') else 'https://www.literotica.com' + href

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content", "").strip():
            description = og_desc.get("content").strip()
        else:
            desc_elem = soup.find('div', class_=lambda c: c and '_widget__info_' in str(c))
            description = desc_elem.get_text(strip=True) if desc_elem else None

        return {
            'title': title,
            'author': author,
            'author_url': author_url,
            'category': category,
            'tags': tags,
            'page_count': page_count,
            'series_url': series_url,
            'description': description,
        }

    except Exception as e:
        log_error(f'Error fetching story metadata: {str(e)}', url)
        return {}


def extract_chapter_titles(story_content: str) -> list[str]:
    """
    Extract chapter titles from story content.

    Args:
        story_content: The full story text with chapters separated by "\\n\\nChapter "

    Returns:
        List of chapter titles (e.g., ["Chapter 1", "Chapter 2: The Beginning"])
        Returns empty list if no chapters found or content is malformed
    """
    if not story_content:
        return []

    chapter_titles = []
    chapter_texts = story_content.split("\n\nChapter ")

    for chapter_text in chapter_texts[1:]:
        title_end = chapter_text.find("\n\n")
        if title_end != -1:
            chapter_titles.append(f"Chapter {chapter_text[:title_end]}")

    return chapter_titles
