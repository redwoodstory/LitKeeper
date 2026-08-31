from __future__ import annotations
import io
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

_CATEGORY_OVERRIDES: dict[str, str] = {
    "I/T": "Taboo",
}

COVER_SIZE = (600, 800)
COVER_CORNER_RADIUS_FRAC = 0.045  # of the cover width — a light touch; the web UI adds its own CSS rounding on top

KOREADER_CORNER_RADIUS_FRAC = 0.10  # noticeably rounder than the web card, since this is the *entire* visible rounding
KOREADER_BORDER_WIDTH = 6
KOREADER_BORDER_COLOR = (60, 60, 60)

# A bold, geometric sans (vs. the web cover's Playfair Display serif) reads
# far better at KOReader grid-thumbnail size on a low-res e-ink/Kaleido
# panel. Pillow has no real "bold" weight bundled for this font, so text is
# drawn with stroke_width as a faux-bold — thickens the strokes without
# needing an extra font asset.
_KOREADER_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "ibmplexsans-400.ttf")

# Deliberately high-contrast pairs only — half dark-bg/white-text, half
# light-bg/dark-text — for legibility on e-ink rather than the web cover's
# softer "dark academia" palette. Each entry: bg, spine (a darker/lighter
# shade of bg for the existing spine-bar motif), accent (category text/
# divider lines), fg (title/author text — always high-contrast against bg).
KOREADER_PALETTES = [
    {'bg': (18, 24, 40),    'spine': (12, 16, 28),   'accent': (247, 197, 72),  'fg': (255, 255, 255)},
    {'bg': (20, 70, 55),    'spine': (13, 48, 38),   'accent': (255, 214, 90),  'fg': (255, 255, 255)},
    {'bg': (120, 25, 35),   'spine': (85, 15, 24),   'accent': (245, 225, 180), 'fg': (255, 255, 255)},
    {'bg': (35, 35, 42),    'spine': (22, 22, 27),   'accent': (110, 200, 190), 'fg': (255, 255, 255)},
    {'bg': (55, 30, 78),    'spine': (37, 18, 55),   'accent': (235, 190, 220), 'fg': (255, 255, 255)},
    {'bg': (25, 55, 110),   'spine': (16, 38, 80),   'accent': (255, 205, 90),  'fg': (255, 255, 255)},
    {'bg': (238, 235, 224), 'spine': (218, 212, 195),'accent': (185, 40, 40),   'fg': (25, 25, 25)},
    {'bg': (215, 225, 210), 'spine': (185, 200, 178),'accent': (35, 95, 60),    'fg': (20, 25, 20)},
    {'bg': (212, 226, 236), 'spine': (178, 198, 214),'accent': (25, 60, 110),   'fg': (20, 24, 30)},
    {'bg': (233, 217, 192), 'spine': (208, 186, 152),'accent': (165, 70, 30),   'fg': (30, 24, 18)},
    {'bg': (227, 227, 227), 'spine': (195, 195, 195),'accent': (175, 35, 45),   'fg': (20, 20, 20)},
]


def _finalize_cover_image(image: Image.Image) -> Image.Image:
    """
    Center-crop to the canonical cover aspect ratio (like the web UI's CSS
    `aspect-[3/4]` + `object-cover`) and bake in lightly rounded white
    corners. Every served cover (generated or extracted from an EPUB) goes
    through this before being saved.
    """
    image = image.convert("RGB")
    target_w, target_h = COVER_SIZE
    target_ratio = target_w / target_h
    w, h = image.size
    src_ratio = w / h

    if src_ratio > target_ratio:
        new_w = round(h * target_ratio)
        left = (w - new_w) // 2
        image = image.crop((left, 0, left + new_w, h))
    elif src_ratio < target_ratio:
        new_h = round(w / target_ratio)
        top = (h - new_h) // 2
        image = image.crop((0, top, w, top + new_h))

    image = image.resize(COVER_SIZE, Image.Resampling.LANCZOS)

    radius = round(target_w * COVER_CORNER_RADIUS_FRAC)
    rounded_mask = Image.new("L", COVER_SIZE, 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle(
        [(0, 0), (target_w - 1, target_h - 1)], radius=radius, fill=255)

    result = Image.new("RGB", COVER_SIZE, (255, 255, 255))
    result.paste(image, (0, 0), mask=rounded_mask)
    return result


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test_line = ' '.join(current + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines


def _widest_line(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.FreeTypeFont) -> int:
    return max((draw.textbbox((0, 0), line, font=font)[2] for line in lines), default=0)


def _break_word_to_width(draw: ImageDraw.ImageDraw, word: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Last-resort hard break of a single word that's still too wide for
    max_width even at the smallest font size — splits mid-word rather than
    letting it run off the cover."""
    chunks: list[str] = []
    current = ""
    for ch in word:
        test = current + ch
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width or not current:
            current = test
        else:
            chunks.append(current)
            current = ch
    if current:
        chunks.append(current)
    return chunks


def _fit_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    initial_size: int,
    max_width: int,
    min_size: int = 60,
    max_lines: int = 4,
    step: int = 10,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """
    Wraps `text` to `max_width` and shrinks the font size until every
    wrapped line actually fits within that width (not just word-count
    heuristics) and the line count is within `max_lines`. `_wrap_lines`
    only breaks on whitespace, so a single implausibly long word can still
    be wider than `max_width` at `min_size` — as a last resort, that word
    is hard-broken mid-word so it never overflows the cover.
    """
    size = initial_size
    font = ImageFont.truetype(font_path, size)
    lines = _wrap_lines(draw, text, font, max_width)
    while size > min_size and (len(lines) > max_lines or _widest_line(draw, lines, font) > max_width):
        size -= step
        font = ImageFont.truetype(font_path, size)
        lines = _wrap_lines(draw, text, font, max_width)

    if _widest_line(draw, lines, font) > max_width:
        fixed_lines: list[str] = []
        for line in lines:
            if draw.textbbox((0, 0), line, font=font)[2] <= max_width:
                fixed_lines.append(line)
            else:
                fixed_lines.extend(_break_word_to_width(draw, line, font, max_width))
        lines = fixed_lines

    return font, lines, size


def generate_koreader_cover_image(title: str, author: str, cover_path: str, category: Optional[str] = None) -> None:
    """
    Generates the KOReader-specific placeholder cover: same overall layout
    as generate_cover_image (title upper-third, author near the bottom,
    optional category flanked by divider lines — no spine bar, unlike the
    web version) but with much larger bold sans-serif text spread across
    the full frame and a higher-contrast palette (KOREADER_PALETTES), for
    legibility on a low-res e-ink/Kaleido grid thumbnail. See
    make_koreader_cover for the corner-rounding/border pass applied after
    this.
    """
    try:
        width, height = 1200, 1600
        palette = KOREADER_PALETTES[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(KOREADER_PALETTES)]
        bg, accent, fg = palette['bg'], palette['accent'], palette['fg']

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)

        margin = 90
        title_stroke = 4
        max_text_width = width - 2 * margin
        display_title = title.upper()
        title_font, lines, title_size = _fit_text_to_width(
            draw, display_title, _KOREADER_FONT_PATH, 190, max_text_width, min_size=90, max_lines=4)

        line_heights = [draw.textbbox((0, 0), line, font=title_font)[3] for line in lines]
        line_height = max(line_heights) if line_heights else title_size
        leading = int(line_height * 1.22)
        total_text_height = leading * len(lines)
        current_y = (height // 3) - (total_text_height // 2)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            line_width = bbox[2] - bbox[0]
            x = (width - line_width) // 2
            draw.text((x, current_y), line, font=title_font, fill=fg, stroke_width=title_stroke, stroke_fill=fg)
            current_y += leading

        title_bottom_y = current_y

        author_text = author.upper()
        author_font, author_lines, _ = _fit_text_to_width(
            draw, author_text, _KOREADER_FONT_PATH, 130, max_text_width, min_size=60, max_lines=1)
        author_y = height - 340
        for author_line in author_lines:
            author_bbox = draw.textbbox((0, 0), author_line, font=author_font)
            author_width = author_bbox[2] - author_bbox[0]
            author_x = (width - author_width) // 2
            draw.text((author_x, author_y), author_line, font=author_font, fill=fg, stroke_width=2, stroke_fill=fg)
            author_y += int((author_bbox[3] - author_bbox[1]) * 1.22)

        if category:
            try:
                from app.models.config import AppConfig
                cfg = AppConfig.query.filter_by(key='covers_show_category').first()
                show_category = cfg.get_value() if cfg else False
            except Exception:
                show_category = False

            if show_category:
                abbrev = abbreviate_category(category)
                cat_font = ImageFont.truetype(_KOREADER_FONT_PATH, 110)
                cat_text = abbrev.upper()
                cat_bbox = draw.textbbox((0, 0), cat_text, font=cat_font)
                cat_w = cat_bbox[2] - cat_bbox[0]
                cat_h = cat_bbox[3] - cat_bbox[1]

                gap_center_y = (title_bottom_y + author_y) // 2
                cat_x = (width - cat_w) // 2 - cat_bbox[0]
                cat_y = gap_center_y - cat_h // 2 - cat_bbox[1]

                line_y = gap_center_y
                text_margin = 40
                draw.line([(margin, line_y), (cat_x - text_margin, line_y)], fill=accent, width=4)
                draw.line([(cat_x + cat_w + text_margin, line_y), (width - margin, line_y)], fill=accent, width=4)
                draw.text((cat_x, cat_y), cat_text, font=cat_font, fill=accent, stroke_width=2, stroke_fill=accent)

        image = image.resize(COVER_SIZE, Image.Resampling.LANCZOS)
        image.save(cover_path, "JPEG", quality=95, optimize=True)

    except Exception as e:
        error_msg = f"Error generating koreader cover image: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)


def make_koreader_cover(src_path: str, dest_path: str) -> None:
    """
    Builds the KOReader-specific cover variant: a heavier rounded corner
    plus a visible border, baked directly into the pixels.

    KOReader's widget toolkit can't clip a child widget (the cover image)
    to a rounded rect the way CSS `overflow-hidden` does for the web UI, so
    doing this client-side needs fragile SVG-corner-mask hacks (or produces
    wrong colors — KOReader's SVG renderer doesn't reliably honor fill
    colors). Baking the finished look into a dedicated image, served from
    its own route/cache file (see /api/story/<id>/cover/koreader), keeps
    the plugin itself a plain image display with no client-side styling
    hacks, and keeps this heavier styling off the web UI's own cover
    (which already does its own lighter CSS rounding).
    """
    image = Image.open(src_path).convert("RGB")
    w, h = image.size

    radius = round(w * KOREADER_CORNER_RADIUS_FRAC)
    rounded_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(rounded_mask).rounded_rectangle(
        [(0, 0), (w - 1, h - 1)], radius=radius, fill=255)

    result = Image.new("RGB", (w, h), (255, 255, 255))
    result.paste(image, (0, 0), mask=rounded_mask)

    inset = KOREADER_BORDER_WIDTH // 2
    ImageDraw.Draw(result).rounded_rectangle(
        [(inset, inset), (w - 1 - inset, h - 1 - inset)],
        radius=radius, outline=KOREADER_BORDER_COLOR, width=KOREADER_BORDER_WIDTH)

    result.save(dest_path, "JPEG", quality=95, optimize=True)

def abbreviate_category(name: str) -> str:
    if name in _CATEGORY_OVERRIDES:
        return _CATEGORY_OVERRIDES[name]
    if '&' in name:
        return name.split('&')[0].strip()
    return name


def generate_cover_image(title: str, author: str, cover_path: str, category: Optional[str] = None) -> None:
    """
    Generate a cover image with a gradient background, a simulated spine effect,
    and styled text that mimics the provided design.

    Args:
        title: The title of the story.
        author: The author's name.
        cover_path: The file path to save the generated cover.
        category: Optional category name; rendered as a badge when covers_show_category is enabled.
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

        display_title = title.upper()
        max_text_width = width - (spine_width + 100)

        try:
            title_font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "PlayfairDisplay-Regular.ttf")
            author_font_path = title_font_path

            if not os.path.exists(title_font_path):
                raise Exception(f"Playfair Display fonts not found")

            title_font, lines, _ = _fit_text_to_width(
                draw, display_title, title_font_path, 154, max_text_width, min_size=70, max_lines=6)
            author_font = ImageFont.truetype(author_font_path, 116)
        except Exception:
            title_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
            lines = _wrap_lines(draw, display_title, title_font, max_text_width)
            logging.warning("Using default font as Playfair Display not found")

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

        title_bottom_y = current_y

        author_y = height - 300
        try:
            author_font, author_lines, _ = _fit_text_to_width(
                draw, author, author_font_path, 116, max_text_width, min_size=50, max_lines=1)
        except Exception:
            author_lines = _wrap_lines(draw, author, author_font, max_text_width)

        for author_line in author_lines:
            author_bbox = draw.textbbox((0, 0), author_line, font=author_font)
            author_width = author_bbox[2] - author_bbox[0]
            draw.text(((width - author_width) // 2, author_y), author_line, fill=(255, 255, 255), font=author_font)
            author_y += int((author_bbox[3] - author_bbox[1]) * 1.3)

        if category:
            try:
                from app.models.config import AppConfig
                cfg = AppConfig.query.filter_by(key='covers_show_category').first()
                show_category = cfg.get_value() if cfg else False
            except Exception:
                show_category = False

            if show_category:
                abbrev = abbreviate_category(category)
                try:
                    cat_font = ImageFont.truetype(title_font_path, 90)
                except Exception:
                    cat_font = ImageFont.load_default()

                cat_bbox = draw.textbbox((0, 0), abbrev, font=cat_font)
                cat_w = cat_bbox[2] - cat_bbox[0]
                cat_h = cat_bbox[3] - cat_bbox[1]

                # Center vertically in the gap between title bottom and author
                gap_center_y = (title_bottom_y + author_y) // 2
                cat_y = gap_center_y - cat_h // 2 - cat_bbox[1]
                cat_x = (width - cat_w) // 2 - cat_bbox[0]

                # Thin decorative lines flanking the text
                line_y = gap_center_y
                line_color = (*accent, 160)
                margin = spine_width + 80
                text_margin = 30
                draw.line([(margin, line_y), (cat_x - text_margin, line_y)], fill=line_color, width=2)
                draw.line([(cat_x + cat_w + text_margin, line_y), (width - margin, line_y)], fill=line_color, width=2)

                draw.text((cat_x, cat_y), abbrev, fill=(255, 255, 255), font=cat_font)

        image = _finalize_cover_image(image)
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

        cover_bytes = None
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                cover_bytes = item.get_content()
                break

        if cover_bytes is None:
            for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                if 'cover' in item.get_name().lower():
                    cover_bytes = item.get_content()
                    break

        if cover_bytes is None:
            return False

        try:
            image = Image.open(io.BytesIO(cover_bytes))
            image = _finalize_cover_image(image)
            image.save(cover_path, "JPEG", quality=95, optimize=True)
        except Exception:
            # Cover in a format Pillow can't parse — fall back to the raw
            # bytes rather than losing the cover entirely.
            with open(cover_path, 'wb') as cover_file:
                cover_file.write(cover_bytes)

        return True

    except Exception as e:
        error_msg = f"Error extracting cover from EPUB: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return False
