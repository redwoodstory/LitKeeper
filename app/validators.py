from __future__ import annotations
from pydantic import BaseModel, HttpUrl, field_validator, Field
from typing import Literal

class StoryDownloadRequest(BaseModel):
    """Validation schema for story download requests."""
    url: str
    wait: bool = True
    format: list[Literal["epub", "html"]] = Field(default=["epub"], min_length=1)
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        v = v.split()[0] if v else ""
        
        if not v:
            raise ValueError("URL cannot be empty")
        
        if not v.startswith("https://www.literotica.com/"):
            raise ValueError("Only Literotica URLs are allowed")
        
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
        if not v.startswith("https://www.literotica.com/"):
            raise ValueError("Only Literotica URLs are allowed")
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
    sort_by: Literal["name", "date", "author", "category", "length"] = "date"
    sort_order: Literal["asc", "desc"] = "desc"

    @field_validator('search')
    @classmethod
    def validate_search(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        return v.strip()
