from __future__ import annotations
from typing import Optional


def create_mock_literotica_response(
    title: str = "Test Story",
    author: str = "TestAuthor",
    content: list[str] = None,
    category: str = "Romance",
    tags: list[str] = None,
    has_next_page: bool = False,
    page_number: int = 1,
    has_series_link: bool = False,
    series_url: str = None
) -> str:
    """Generate mocked Literotica HTML response matching their CSS class structure.

    Args:
        title: Story title
        author: Author name
        content: List of paragraph strings
        category: Story category
        tags: List of tags
        has_next_page: Whether to include pagination link
        page_number: Current page number
        has_series_link: Whether to include series continuation link
        series_url: URL for next story in series

    Returns:
        HTML string matching Literotica's structure
    """
    if content is None:
        content = [
            "This is the first paragraph of the story.",
            "This is the second paragraph with more content.",
            "This is the third paragraph continuing the narrative."
        ]

    if tags is None:
        tags = ["Romance", "Love"]

    paragraphs_html = "\n        ".join(f"<p>{p}</p>" for p in content)

    tags_html = "\n        ".join(
        f'<a class="_tags__link_tag" href="/tags/{tag.lower()}">{tag}</a>'
        for tag in tags
    )

    pagination_html = ""
    if has_next_page:
        next_page = page_number + 1
        pagination_html = f'''
    <div class="pagination">
        <a href="/s/{title.lower().replace(" ", "-")}-1?page={next_page}" class="next-page">Next Page</a>
    </div>'''

    series_html = ""
    if has_series_link:
        series_link = series_url or f"/s/{title.lower().replace(' ', '-')}-ch-02"
        series_html = f'''
    <div class="series-links">
        <a href="{series_link}" class="next-chapter">READ MORE OF THIS SERIES</a>
    </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{title} - Literotica.com</title>
</head>
<body>
    <div class="page-container">
        <h1 class="_title_abc123">{title}</h1>
        <div class="author-info">
            <a class="_author__title_xyz789" href="/members/{author.lower()}">{author}</a>
        </div>

        <nav class="_breadcrumbs_nav" aria-label="Breadcrumb">
            <span itemprop="name">Home</span>
            <span class="separator">&gt;</span>
            <span itemprop="name">{category}</span>
        </nav>

        <div class="_article__content_content">
        {paragraphs_html}
        </div>

        <div class="_tags_list">
        {tags_html}
        </div>{pagination_html}{series_html}
    </div>
</body>
</html>'''


def create_mock_multipage_story(
    title: str = "Multipage Story",
    author: str = "TestAuthor",
    num_pages: int = 3,
    category: str = "Romance"
) -> dict[int, str]:
    """Create a multi-page story with pagination.

    Args:
        title: Story title
        author: Author name
        num_pages: Number of pages
        category: Story category

    Returns:
        Dictionary mapping page number to HTML content
    """
    pages = {}

    for page_num in range(1, num_pages + 1):
        content = [
            f"This is page {page_num}, paragraph 1.",
            f"This is page {page_num}, paragraph 2.",
            f"This is page {page_num}, paragraph 3."
        ]

        has_next = page_num < num_pages

        pages[page_num] = create_mock_literotica_response(
            title=title,
            author=author,
            content=content,
            category=category,
            has_next_page=has_next,
            page_number=page_num
        )

    return pages


def create_mock_series(
    base_title: str = "Series Story",
    author: str = "TestAuthor",
    num_chapters: int = 3,
    category: str = "Romance"
) -> dict[int, str]:
    """Create a multi-chapter series with continuation links.

    Args:
        base_title: Base story title (will be suffixed with chapter numbers)
        author: Author name
        num_chapters: Number of chapters in series
        category: Story category

    Returns:
        Dictionary mapping chapter number to HTML content
    """
    chapters = {}

    for chapter_num in range(1, num_chapters + 1):
        title = f"{base_title} Ch. {chapter_num:02d}"
        content = [
            f"Chapter {chapter_num} begins here.",
            f"This is the content of chapter {chapter_num}.",
            f"More content for chapter {chapter_num}."
        ]

        has_series = chapter_num < num_chapters
        series_url = None
        if has_series:
            next_ch = chapter_num + 1
            series_url = f"/s/{base_title.lower().replace(' ', '-')}-ch-{next_ch:02d}"

        chapters[chapter_num] = create_mock_literotica_response(
            title=title,
            author=author,
            content=content,
            category=category,
            has_series_link=has_series,
            series_url=series_url
        )

    return chapters
