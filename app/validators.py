from __future__ import annotations
from pydantic import BaseModel, HttpUrl, field_validator, Field
from typing import Literal
from urllib.parse import urlparse

class StoryDownloadRequest(BaseModel):
    """Validation schema for story download requests."""
    url: str
    wait: bool = True
    format: list[Literal["epub", "html"]] = Field(default=["epub", "html"], min_length=1)
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        v = v.split()[0] if v else ""

        if not v:
            raise ValueError("URL cannot be empty")

        parsed = urlparse(v)

        if parsed.scheme != "https":
            raise ValueError("Only HTTPS URLs are allowed")

        host = parsed.netloc.lower()

        if not (host == "literotica.com" or host.endswith(".literotica.com")):
            raise ValueError("Only Literotica URLs are allowed")

        if "/s/" not in parsed.path and "/series/se/" not in parsed.path:
            raise ValueError("URL must be a story chapter (/s/) or series page (/series/se/)")

        return v
    
    @field_validator('format')
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one format must be specified")
        
        valid_formats = {"epub", "html"}
        for fmt in v:
            if fmt not in valid_formats:
                raise ValueError(f"Invalid format: {fmt}. Must be 'epub' or 'html'")
        
        return v

class StoryMetadataUpdate(BaseModel):
    """Validation schema for story metadata updates."""
    url: str
    title: str
    author: str = "Unknown Author"
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    formats: list[Literal["epub", "html"]] = Field(default=["epub"], min_length=1)

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        parsed = urlparse(v)

        if parsed.scheme != "https":
            raise ValueError("Only HTTPS URLs are allowed")

        host = parsed.netloc.lower()

        if not (host == "literotica.com" or host.endswith(".literotica.com")):
            raise ValueError("Only Literotica URLs are allowed")

        if "/s/" not in parsed.path and "/series/se/" not in parsed.path:
            raise ValueError("URL must be a story chapter (/s/) or series page (/series/se/)")

        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v

    @field_validator('author')
    @classmethod
    def validate_author(cls, v: str) -> str:
        return v.strip() if v else "Unknown Author"

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        return v.strip() if v else None

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        return [tag.strip() for tag in v if tag.strip()]

class LibraryFilterRequest(BaseModel):
    """Validation schema for library filter requests."""
    search: str = ""
    category: str = "all"
    sort_by: Literal["name", "date", "author", "category", "length", "rating", "last_opened", "community_score", "pages"] = "date"
    sort_order: Literal["asc", "desc"] = "desc"
    queue_only: bool = False
    min_community_score: float = 0.0
    min_pages: int = 0
    max_pages: int = 0

    @field_validator('search')
    @classmethod
    def validate_search(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        return v.strip()
