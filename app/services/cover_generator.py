from __future__ import annotations
import os
import hashlib
import traceback
import logging
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import ebooklib
import ebooklib.epub as epub
from .logger import log_error

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
        
        background_colors = [
            (47, 53, 66),
            (44, 62, 80),
            (52, 73, 94),
            (69, 39, 60),
            (81, 46, 95),
            (45, 52, 54),
            (33, 33, 33),
            (25, 42, 86),
            (56, 29, 42),
            (28, 40, 51),
        ]
        
        color_index = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(background_colors)
        background_color = background_colors[color_index]
        
        text_color = (255, 255, 255)
        spine_color = tuple(max(0, c - 20) for c in background_color)
        
        image = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(image, 'RGBA')

        spine_width = 40
        draw.rectangle([(0, 0), (spine_width, height)], fill=spine_color)
        
        try:
            font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "Open_Sans", "OpenSans-VariableFont_wdth,wght.ttf")
            if not os.path.exists(font_path):
                raise Exception(f"Bundled font not found at {font_path}")

            title_font = ImageFont.truetype(font_path, 128)
            author_font = ImageFont.truetype(font_path, 72)
        except Exception as e:
            title_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
            logging.warning("Using default font as Open Sans not found")

        max_text_width = width - (spine_width + 100)
        
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
        total_text_height += 40 * (len(lines) - 1)
        
        current_y = (height // 3) - (total_text_height // 2)
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            x = (width - line_width) // 2
            draw.text((x, current_y), line, fill=text_color, font=title_font)
            current_y += line_height + 40

        author_bbox = draw.textbbox((0, 0), author, font=author_font)
        author_width = author_bbox[2] - author_bbox[0]
        author_height = author_bbox[3] - author_bbox[1]
        author_position = ((width - author_width) // 2, height - 200)
        draw.text(author_position, author, fill=text_color, font=author_font)

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
        book = epub.read_epub(epub_path)

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
