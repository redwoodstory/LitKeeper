from __future__ import annotations
import requests
from bs4 import BeautifulSoup
import time
import random
import traceback
from typing import Optional
from .logger import log_url, log_error

def get_random_user_agent() -> str:
    """Return a random User-Agent string."""
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
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

def download_story(url: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[list[str]], Optional[str], Optional[int]]:
    """Download and extract the full story content and metadata from the given Literotica URL."""
    try:
        session = get_session()
        story_content = ""
        current_page = 1
        total_pages = 0
        story_title = "Unknown Title"
        story_author = "Unknown Author"
        story_category = None
        story_tags = []
        story_author_url = None
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
                    return None, None, None, None, None, None, None
                except Exception as e:
                    error_msg = f"Error processing chapter {current_chapter}: {str(e)}\n{traceback.format_exc()}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None, None, None

        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"

        return story_content, story_title, story_author, story_category, story_tags, story_author_url, total_pages

    except Exception as e:
        error_msg = f"Unexpected error in download_story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        return None, None, None, None, None, None, None

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
