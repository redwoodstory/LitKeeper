import os
import requests
from bs4 import BeautifulSoup
import time
import random
from PIL import Image, ImageDraw, ImageFont
import ebooklib.epub as epub
import uuid
from urllib.parse import quote
import re
import hashlib
import traceback
from datetime import datetime

# Environment variables to control logging (default to enabled)
ENABLE_ACTION_LOG = os.getenv('ENABLE_ACTION_LOG', 'true').lower() == 'true'
ENABLE_ERROR_LOG = os.getenv('ENABLE_ERROR_LOG', 'true').lower() == 'true'
ENABLE_URL_LOG = os.getenv('ENABLE_URL_LOG', 'true').lower() == 'true'

# Environment variables for notifications
NOTIFICATION_URLS = os.getenv('NOTIFICATION_URLS', '').split(',')

# Legacy Telegram support
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    telegram_url = f"tgram://{TELEGRAM_BOT_TOKEN}/{TELEGRAM_CHAT_ID}"
    if telegram_url not in NOTIFICATION_URLS:
        NOTIFICATION_URLS.append(telegram_url)

ENABLE_NOTIFICATIONS = bool(NOTIFICATION_URLS and NOTIFICATION_URLS[0])

def log_action(message):
    """Log an action to log.txt with timestamp."""
    if not ENABLE_ACTION_LOG:
        return

    log_directory = os.path.join(os.path.dirname(__file__), "data", "logs")
    os.makedirs(log_directory, exist_ok=True)
    log_file = os.path.join(log_directory, "log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"{timestamp} - {message}\n")

def log_error(error_message, url=None):
    """Log an error message to error_log.txt with timestamp and optional URL."""
    if not ENABLE_ERROR_LOG:
        return

    log_directory = os.path.join(os.path.dirname(__file__), "data", "logs")
    os.makedirs(log_directory, exist_ok=True)
    log_file = os.path.join(log_directory, "error_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"{timestamp} - {error_message}"
    # Only add URL line if URL isn't already in the error message
    if url and url not in error_message:
        message += f"\nURL: {url}"
    message += "\n" + "-"*50 + "\n"
    
    with open(log_file, "a") as f:
        f.write(message)
    
    log_action(f"Error logged: {error_message}")

def log_url(url):
    """Log URL to url_log.txt with timestamp."""
    if not ENABLE_URL_LOG:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(os.path.dirname(__file__), "data", "logs", "url_log.txt")
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    with open(log_file, "a") as f:
        f.write(f"{timestamp} - {url}\n")
    
    log_action("URL logged to url_log.txt")

def send_notification(message, is_error=False):
    """Send a notification using Apprise to configured notification services."""
    if not ENABLE_NOTIFICATIONS:
        return

    try:
        import apprise

        # Create an Apprise instance
        apobj = apprise.Apprise()
        
        # Add all notification URLs
        for url in NOTIFICATION_URLS:
            url = url.strip()
            if url:  # Only add non-empty URLs
                apobj.add(url)

        # Format the message
        icon = "❌" if is_error else "✅"
        formatted_message = f"{icon} {message}"
        
        # Send the notification
        if apobj.notify(body=formatted_message):
            log_action(f"Notification sent: {message}")
        else:
            log_error("Failed to send notification")
    except Exception as e:
        log_error(f"Error sending notification: {str(e)}")

def get_random_user_agent():
    """Return a random User-Agent string."""
    import random
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
    ]
    return random.choice(USER_AGENTS)

def get_session():
    """Create and return a session with default headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    log_action("Created new requests session")
    return session

def download_story(url):
    """Download and extract the full story content and metadata from the given Literotica URL."""
    try:
        session = get_session()
        story_content = ""
        current_page = 1
        story_title = "Unknown Title"
        story_author = "Unknown Author"
        story_category = None
        story_tags = []
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
            log_action(f"Processing chapter {current_chapter} from URL: {current_url}")
            log_url(current_url)

            while current_url:
                try:
                    log_action(f"Fetching page {current_page} of chapter {current_chapter}")
                    response = session.get(current_url, timeout=10)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, "html.parser")
                    log_action("Successfully parsed page content")

                    if current_page == 1:
                        # Find title using partial class match
                        title_tag = soup.find("h1", class_=lambda c: c and c.startswith("_title_"))
                        # Find author using partial class match
                        author_tag = soup.find("a", class_=lambda c: c and "_author__title_" in str(c))
                        current_title = title_tag.text.strip() if title_tag else "Unknown Chapter"

                        if current_chapter == 1:
                            story_title = current_title
                            story_author = author_tag.text.strip() if author_tag else story_author
                            log_action(f"Extracted story metadata - Title: {story_title}, Author: {story_author}")

                            # Find category from breadcrumbs using partial class match
                            breadcrumb = soup.find("nav", class_=lambda c: c and "_breadcrumbs_" in str(c))
                            if breadcrumb:
                                # The second breadcrumb item is usually the category
                                breadcrumb_items = breadcrumb.find_all("span", itemprop="name")
                                if len(breadcrumb_items) >= 2:
                                    story_category = breadcrumb_items[1].text.strip()
                                    if story_category.lower().startswith("inc"):
                                        story_category = "I/T"

                            # Find tags using partial class match
                            tag_elements = soup.find_all("a", class_=lambda c: c and "_tags__link_" in str(c))
                            story_tags = [tag.text.strip() for tag in tag_elements
                                        if not tag.text.strip().lower().startswith("inc")]
                            if story_category and story_category not in story_tags:
                                story_tags = [story_category] + story_tags
                            log_action(f"Extracted category: {story_category} and {len(story_tags)} tags")

                    # Find content using partial class match
                    content_div = soup.find("div", class_=lambda c: c and "_article__content_" in str(c))
                    if content_div:
                        if current_page == 1:
                            chapter_titles.append(current_title)
                            log_action(f"Added chapter title: {current_title}")
                                
                        for paragraph in content_div.find_all("p"):
                            current_chapter_content += paragraph.get_text(strip=True) + "\n\n"
                        log_action(f"Extracted content from page {current_page}")

                    # Find pagination links using partial class match
                    # Look for links with ?page= parameter in href
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
                        log_action(f"Found next page link: {next_url}")
                    else:
                        chapter_contents.append(current_chapter_content)
                        log_action(f"Completed chapter {current_chapter}")
                        
                        # Look for series navigation using partial class match
                        # Find section with "READ MORE OF THIS SERIES" heading (must be actual h3 tag, not i18n string)
                        series_section = None
                        for section in soup.find_all("section", class_=lambda c: c and "_panel_" in str(c)):
                            heading = section.find("h3", class_=lambda c: c and "_heading_" in str(c))
                            if heading and heading.get_text(strip=True) == "READ MORE OF THIS SERIES":
                                series_section = section
                                log_action("Found series section with 'READ MORE OF THIS SERIES' heading")
                                break

                        if series_section:
                            # Find the data list container (div with _data_list_ class)
                            data_list = series_section.find("div", class_=lambda c: c and "_data_list_" in str(c))
                            if data_list:
                                # Find all items in the list (div with _item_ class)
                                items = data_list.find_all("div", class_=lambda c: c and "_item_" in str(c))
                                log_action(f"Found {len(items)} items in series list")

                                for item in items:
                                    # Look for "Next Part" indicator
                                    next_part_span = item.find("span", string=lambda s: s and "Next Part" in s)
                                    if next_part_span:
                                        # Find the story link in this item
                                        link = item.find("a", href=lambda h: h and "/s/" in h)
                                        if link:
                                            next_url = link.get("href", "")
                                            if not next_url.startswith("http"):
                                                next_url = "https://www.literotica.com" + next_url

                                            # Remove query parameters to get base URL
                                            base_next_url = next_url.split("?")[0]

                                            # Check if not already processed
                                            if base_next_url not in processed_urls:
                                                chapter_urls.append(base_next_url)
                                                log_action(f"Found next part in series: {base_next_url}")
                                                break
                        
                        current_url = None
                        current_page = 1

                    time.sleep(3)
                    log_action("Waiting 3 seconds before next request")

                except requests.RequestException as e:
                    error_msg = f"Network error while downloading chapter {current_chapter}: {str(e)}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None
                except Exception as e:
                    error_msg = f"Error processing chapter {current_chapter}: {str(e)}\n{traceback.format_exc()}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None

        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"
        log_action(f"Combined {len(chapter_contents)} chapters into final story content")
        
        return story_content, story_title, story_author, story_category, story_tags

    except Exception as e:
        error_msg = f"Unexpected error in download_story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        return None, None, None, None, None

def format_story_content(content):
    """Format story content into properly formatted paragraphs for EPUB."""
    css = """
        <style>
            body {
                margin: 1em;
                padding: 0 1em;
            }
            p {
                margin: 1.5em 0;
                line-height: 1.7;
                font-size: 1.1em;
            }
            h1 {
                margin: 2em 0 1em 0;
                text-align: center;
            }
        </style>
    """
    
    paragraphs = content.split('\n\n')
    formatted_paragraphs = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
    return css + '\n'.join(formatted_paragraphs)

def format_metadata_content(category=None, tags=None):
    """Format metadata content with proper styling."""
    css = """
        <style>
            body {
                margin: 1em;
                padding: 0 1em;
            }
            h1 {
                margin: 2em 0 1em 0;
                text-align: center;
            }
            .metadata {
                margin: 1.5em 0;
                line-height: 1.7;
                font-size: 1.1em;
            }
            .metadata-item {
                margin: 1em 0;
            }
            .metadata-label {
                font-weight: bold;
                margin-right: 0.5em;
            }
        </style>
    """
    
    content = f"{css}<h1>Story Information</h1><div class='metadata'>"
    if category:
        content += f"<div class='metadata-item'><span class='metadata-label'>Category: </span>{category}</div>"
    if tags:
        content += f"<div class='metadata-item'><span class='metadata-label'>Tags: </span>{', '.join(tags)}</div>"
    content += "</div>"
    return content

def generate_cover_image(title, author, cover_path):
    """
    Generate a cover image with a gradient background, a simulated spine effect, 
    and styled text that mimics the provided design.
    
    Args:
        title (str): The title of the story.
        author (str): The author's name.
        cover_path (str): The file path to save the generated cover.
    """
    try:
        log_action(f"Generating cover image for '{title}' by {author}")
        width, height = 1200, 1600  # Double the size for higher resolution
        
        background_colors = [
            (47, 53, 66),   # Dark slate
            (44, 62, 80),   # Midnight blue
            (52, 73, 94),   # Dark ocean
            (69, 39, 60),   # Deep purple
            (81, 46, 95),   # Royal purple
            (45, 52, 54),   # Dark jungle
            (33, 33, 33),   # Charcoal
            (25, 42, 86),   # Navy blue
            (56, 29, 42),   # Wine red
            (28, 40, 51),   # Dark navy
        ]
        
        color_index = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(background_colors)
        background_color = background_colors[color_index]
        
        text_color = (255, 255, 255)  # White text
        spine_color = tuple(max(0, c - 20) for c in background_color)  # Slightly darker version of background color
        
        image = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(image, 'RGBA')  # Use RGBA for better anti-aliasing

        spine_width = 40  # Increased spine width for larger image
        draw.rectangle([(0, 0), (spine_width, height)], fill=spine_color)
        
        try:
            font_path = os.path.join(os.path.dirname(__file__), "static", "fonts", "Open_Sans", "OpenSans-VariableFont_wdth,wght.ttf")
            if not os.path.exists(font_path):
                raise Exception(f"Bundled font not found at {font_path}")
                
            title_font = ImageFont.truetype(font_path, 128)  # Large title font
            author_font = ImageFont.truetype(font_path, 72)  # Large author font
        except Exception as e:
            title_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
            log_action("Using default font as Open Sans not found")

        max_text_width = width - (spine_width + 100)  # Leave 50px margin on each side
        
        words = title.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=title_font)
            test_width = bbox[2] - bbox[0]
            
            if test_width <= max_text_width:
                current_line.append(word)
            else:
                if current_line:  
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:  
                    lines.append(word)
                    current_line = []
        
        if current_line:  
            lines.append(' '.join(current_line))
        
        total_text_height = sum(draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] for line in lines)
        total_text_height += 40 * (len(lines) - 1)  # Add spacing between lines
        
        current_y = (height // 3) - (total_text_height // 2)  # Center the text block vertically around the 1/3 point
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (width - line_width) // 2
            draw.text((x, current_y), line, fill=text_color, font=title_font)
            current_y += line_height + 40

        author_bbox = draw.textbbox((0, 0), author, font=author_font)  # Get bounding box of the author text
        author_width = author_bbox[2] - author_bbox[0]
        author_height = author_bbox[3] - author_bbox[1]
        author_position = ((width - author_width) // 2, height - 200)  # Moved up from bottom
        draw.text(author_position, author, fill=text_color, font=author_font)

        image = image.resize((600, 800), Image.Resampling.LANCZOS)  # Resize with high-quality resampling
        image.save(cover_path, "JPEG", quality=95, optimize=True)  
        log_action("Successfully saved cover image")

    except Exception as e:
        error_msg = f"Error generating cover image: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        log_action("Failed to generate cover image")

def create_epub_file(story_title, story_author, story_content, output_directory, cover_image_path=None, story_category=None, story_tags=None):
    """Create an EPUB file from the story content."""
    try:
        log_action(f"Starting EPUB creation for '{story_title}' by {story_author}")
        os.makedirs(output_directory, exist_ok=True)
        log_action(f"Created/verified output directory: {output_directory}")

        if cover_image_path is None:
            cover_image_path = os.path.join(output_directory, "cover.jpg")
            generate_cover_image(story_title, story_author, cover_image_path)

        book = epub.EpubBook()
        log_action("Created new EPUB book object")

        book.set_identifier(str(uuid.uuid4()))
        book.set_title(story_title)
        book.set_language('en')
        book.add_author(story_author)
        log_action("Set basic EPUB metadata")

        if story_category:
            book.add_metadata('DC', 'subject', story_category)
        if story_tags:
            for tag in story_tags:
                book.add_metadata('DC', 'subject', tag)
        log_action("Added category and tags to EPUB metadata")

        try:
            if os.path.exists(cover_image_path):
                with open(cover_image_path, 'rb') as cover_file:
                    book.set_cover("cover.jpg", cover_file.read())
                log_action("Added cover image to EPUB")
        except Exception as e:
            error_msg = f"Error adding cover image: {str(e)}"
            log_error(error_msg)

        chapters = []
        toc = []

        if story_category or story_tags:
            try:
                metadata_content = format_metadata_content(story_category, story_tags)
                metadata_chapter = epub.EpubHtml(title='Story Information',
                                               file_name='metadata.xhtml',
                                               content=metadata_content)
                book.add_item(metadata_chapter)
                chapters.append(metadata_chapter)
                toc.append(metadata_chapter)
                log_action("Added metadata chapter to EPUB")
            except Exception as e:
                error_msg = f"Error adding metadata chapter: {str(e)}"
                log_error(error_msg)

        chapter_texts = story_content.split("\n\nChapter ")
        
        if chapter_texts[0].strip():
            try:
                intro_content = format_story_content(chapter_texts[0])
                intro_chapter = epub.EpubHtml(title='Introduction',
                                            file_name='intro.xhtml',
                                            content=f'<h1>Introduction</h1>{intro_content}')
                book.add_item(intro_chapter)
                chapters.append(intro_chapter)
                toc.append(intro_chapter)
                log_action("Added introduction chapter to EPUB")
            except Exception as e:
                error_msg = f"Error adding introduction chapter: {str(e)}"
                log_error(error_msg)

        for i, chapter_text in enumerate(chapter_texts[1:], 1):
            try:
                title_end = chapter_text.find("\n\n")
                if title_end == -1:
                    chapter_title = f"Chapter {i}"
                    chapter_content = chapter_text
                else:
                    chapter_title = f"Chapter {chapter_text[:title_end]}"
                    chapter_content = chapter_text[title_end:].strip()
                
                formatted_content = format_story_content(chapter_content)
                chapter = epub.EpubHtml(title=chapter_title,
                                      file_name=f'chapter_{i}.xhtml',
                                      content=f'<h1>{chapter_title}</h1>{formatted_content}')
                
                book.add_item(chapter)
                chapters.append(chapter)
                toc.append(chapter)
                log_action(f"Added chapter {i} to EPUB")
            except Exception as e:
                error_msg = f"Error processing chapter {i}: {str(e)}"
                log_error(error_msg)
                continue

        if not chapters:
            error_msg = "No valid chapters found to create EPUB"
            log_error(error_msg)
            raise ValueError(error_msg)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        log_action("Added navigation files to EPUB")

        book.toc = toc
        book.spine = ['nav'] + chapters
        log_action("Set table of contents and spine")

        def sanitize_filename(filename):
            return re.sub(r'[^a-zA-Z0-9._-]', '', filename)

        epub_path = os.path.join(output_directory, f"{sanitize_filename(story_title)}.epub")
        epub.write_epub(epub_path, book, {})
        log_action(f"Successfully wrote EPUB file to: {epub_path}")
        
        send_notification(f"EPUB created: {story_title} by {story_author}")
        
        return epub_path

    except Exception as e:
        error_msg = f"Error creating EPUB file for '{story_title}' by {story_author}: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        send_notification(f"EPUB creation failed: {story_title} by {story_author}", is_error=True)
        raise

# Example usage:
if __name__ == "__main__":
    TEST_URL = "https://www.literotica.com/s/seven-nights-adippin"  # Replace with your story URL
    OUTPUT_DIR = "epub_files"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    full_content, title, author, category, tags = download_story(TEST_URL)
    if full_content:
        epub_path = create_epub_file(title, author, full_content, OUTPUT_DIR, story_category=category, story_tags=tags)
    else:
        print("Failed to download story.")