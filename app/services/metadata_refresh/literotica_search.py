from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
from ..story_downloader import download_story, get_session
from .rate_limiter import RateLimiter


@dataclass
class LiteroticaSearchResult:
    title: str
    author: str
    url: str
    category: Optional[str] = None


class LiteroticaSearcher:
    def __init__(self):
        self.rate_limiter = RateLimiter(max_requests=10, time_window=60)
        self.base_search_url = "https://www.literotica.com/stories/search.php"
    
    def search_story(self, title: str, author: str) -> list[LiteroticaSearchResult]:
        from ..logger import log_action
        
        self.rate_limiter.wait_if_needed()
        
        author_slug = author.lower().replace(' ', '_')
        author_works_url = f"https://www.literotica.com/authors/{author_slug}/works/stories"
        
        log_action(f"[SEARCH] Querying URL: {author_works_url}")
        
        try:
            session = get_session()
            response = session.get(author_works_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            story_links = soup.find_all("a", href=lambda h: h and "/s/" in h)
            
            for link in story_links:
                story_title = link.get_text(strip=True)
                if not story_title:
                    continue
                
                story_url = link.get("href", "")
                if not story_url.startswith("http"):
                    story_url = "https://www.literotica.com" + story_url
                
                parent = link.find_parent()
                story_category = None
                
                if parent:
                    category_link = parent.find("a", href=lambda h: h and "/c/" in str(h))
                    if category_link:
                        story_category = category_link.get_text(strip=True)
                
                results.append(LiteroticaSearchResult(
                    title=story_title,
                    author=author,
                    url=story_url,
                    category=story_category
                ))
            
            return results
        
        except requests.RequestException as e:
            return []
        except Exception as e:
            return []
    
    def fetch_metadata_from_url(self, url: str) -> Optional[dict]:
        self.rate_limiter.wait_if_needed()

        try:
            content, title, author, category, tags, author_url, page_count, series_url = download_story(url)

            if title and author:
                return {
                    "title": title,
                    "author": author,
                    "category": category,
                    "tags": tags or [],
                    "author_url": author_url,
                    "page_count": page_count or 0,
                    "series_url": series_url,
                    "literotica_url": url
                }

            return None

        except Exception as e:
            return None
