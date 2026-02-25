from __future__ import annotations
import os
import hashlib
import traceback
import logging
import warnings
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import ebooklib
import ebooklib.epub as epub
from .logger import log_error

warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

def generate_cover_image(title: str, author: str, cover_path: str) -> None:
    """
    Generate a cover image with a gradient background, a simulated spine effect,
    and styled text that mimics the provided design.

    Args:
        title: The title of the story.
        author: The author's name.
        cover_path: The file path to save the generated cover.
    """
    try:
        width, height = 1200, 1600

        palettes = [
            # --- The Dark Academia Collection (Deep, moody jewel tones) ---
            {'bg': (15, 25, 45),  'accent': (190, 200, 215), 'spine': (25, 40, 65)},  # Midnight Blue & Silver
            {'bg': (12, 35, 25),  'accent': (210, 185, 120), 'spine': (20, 50, 35)},  # Deep Emerald & Gold
            {'bg': (45, 15, 20),  'accent': (225, 180, 170), 'spine': (65, 25, 30)},  # Oxblood & Rose Gold
            {'bg': (35, 15, 35),  'accent': (230, 215, 190), 'spine': (50, 25, 50)},  # Royal Plum & Champagne
            {'bg': (15, 40, 45),  'accent': (215, 160, 120), 'spine': (25, 55, 60)},  # Dark Teal & Copper
            # --- The Antiquarian Library (Warm, earthy, vintage leather vibes) ---
            {'bg': (30, 20, 15),  'accent': (180, 150, 100), 'spine': (45, 30, 22)},  # Espresso & Antique Brass
            {'bg': (35, 40, 25),  'accent': (190, 175, 130), 'spine': (50, 55, 35)},  # Olive Grove & Tarnished Gold
            {'bg': (40, 45, 50),  'accent': (220, 220, 225), 'spine': (55, 60, 65)},  # Slate Grey & Pearl
            {'bg': (60, 25, 15),  'accent': (230, 215, 195), 'spine': (80, 35, 22)},  # Rust & Parchment
            {'bg': (50, 45, 40),  'accent': (200, 195, 190), 'spine': (65, 60, 55)},  # Deep Taupe & Warm Silver
            # --- The Collector's Edition (Rich, vibrant, and highly saturated) ---
            {'bg': (20, 40, 80),  'accent': (235, 195, 100), 'spine': (30, 55, 100)},  # Lapis Lazuli & Bright Gold
            {'bg': (75, 15, 20),  'accent': (240, 210, 150), 'spine': (95, 22, 28)},  # Crimson & Pale Gold
            {'bg': (20, 50, 30),  'accent': (240, 235, 220), 'spine': (30, 65, 40)},  # Forest Green & Ivory
            {'bg': (55, 30, 70),  'accent': (215, 215, 225), 'spine': (70, 42, 88)},  # Amethyst & Platinum
            {'bg': (10, 55, 65),  'accent': (200, 150, 100), 'spine': (15, 70, 82)},  # Peacock Blue & Bronze
            # --- The Soft Classics (Muted, dreamy, and sophisticated) ---
            {'bg': (85, 55, 60),  'accent': (245, 230, 215), 'spine': (105, 70, 75)},  # Dusty Rose & Cream
            {'bg': (55, 70, 60),  'accent': (225, 225, 200), 'spine': (70, 88, 75)},  # Sage Green & White Gold
            {'bg': (45, 50, 75),  'accent': (200, 205, 220), 'spine': (60, 65, 95)},  # Muted Indigo & Silver
            {'bg': (65, 45, 35),  'accent': (240, 200, 180), 'spine': (82, 58, 45)},  # Warm Sepia & Soft Peach
            {'bg': (50, 65, 80),  'accent': (235, 230, 220), 'spine': (65, 82, 100)},  # Fog Blue & Linen
        ]

        palette = palettes[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(palettes)]
        bg, accent, spine_color = palette['bg'], palette['accent'], palette['spine']

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image, 'RGBA')

        spine_width = 40
        draw.rectangle([(0, 0), (spine_width, height)], fill=spine_color)

        try:
            title_font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "PlayfairDisplay-Regular.ttf")
            author_font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "PlayfairDisplay-Regular.ttf")
            
            if not os.path.exists(title_font_path) or not os.path.exists(author_font_path):
                raise Exception(f"Playfair Display fonts not found")

            title_font = ImageFont.truetype(title_font_path, 164)
            author_font = ImageFont.truetype(author_font_path, 96)
        except Exception:
            title_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
            logging.warning("Using default font as Playfair Display not found")

        display_title = title.upper()
        max_text_width = width - (spine_width + 100)

        words = display_title.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=title_font)
            if bbox[2] - bbox[0] <= max_text_width:
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

        total_text_height = sum(
            draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1]
            for line in lines
        )
        total_text_height += 40 * (len(lines) - 1)

        current_y = (height // 3) - (total_text_height // 2)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (width - line_width) // 2
            draw.text((x, current_y), line, fill=(255, 255, 255), font=title_font)
            current_y += line_height + 40

        author_bbox = draw.textbbox((0, 0), author, font=author_font)
        author_width = author_bbox[2] - author_bbox[0]
        author_position = ((width - author_width) // 2, height - 300)
        draw.text(author_position, author, fill=(255, 255, 255), font=author_font)

        image = image.resize((600, 800), Image.Resampling.LANCZOS)
        image.save(cover_path, "JPEG", quality=95, optimize=True)

    except Exception as e:
        error_msg = f"Error generating cover image: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)

def extract_cover_from_epub(epub_path: str, cover_path: str) -> bool:
    """
    Extract cover image from an EPUB file.

    Args:
        epub_path: Path to the EPUB file.
        cover_path: Path where the cover should be saved.

    Returns:
        True if cover was extracted successfully, False otherwise.
    """
    try:
        book = epub.read_epub(epub_path, options={'ignore_ncx': True})

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                with open(cover_path, 'wb') as cover_file:
                    cover_file.write(item.get_content())
                return True

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_name = item.get_name().lower()
            if 'cover' in item_name:
                with open(cover_path, 'wb') as cover_file:
                    cover_file.write(item.get_content())
                return True

        return False

    except Exception as e:
        error_msg = f"Error extracting cover from EPUB: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return False
