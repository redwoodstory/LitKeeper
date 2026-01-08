#!/usr/bin/env python3
"""
Backfill word_count for existing stories in the database.
Reads from EPUB files and calculates word count.
"""
from app import create_app
from app.models import Story
from app.models.base import db
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings('ignore', category=FutureWarning, module='ebooklib')

def calculate_word_count_from_epub(epub_path: str) -> int:
    """Calculate word count from EPUB file"""
    try:
        book = epub.read_epub(epub_path, options={'ignore_ncx': True})
        total_text = ""
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            total_text += soup.get_text(separator=' ', strip=True) + " "
        
        return len(total_text.split())
    except Exception as e:
        print(f"  Error reading EPUB: {e}")
        return 0

def main():
    app = create_app()
    
    with app.app_context():
        stories = Story.query.filter(
            (Story.word_count == None) | (Story.word_count == 0)
        ).all()
        
        print(f"Found {len(stories)} stories without word_count")
        print()
        
        updated = 0
        failed = 0
        
        for story in stories:
            print(f"Processing: {story.title}")
            
            epub_format = next((f for f in story.formats if f.format_type == 'epub'), None)
            
            if not epub_format:
                print(f"  No EPUB format found, skipping")
                failed += 1
                continue
            
            word_count = calculate_word_count_from_epub(epub_format.file_path)
            
            if word_count > 0:
                story.word_count = word_count
                print(f"  Set word_count to {word_count:,}")
                updated += 1
            else:
                print(f"  Failed to calculate word_count")
                failed += 1
        
        if updated > 0:
            db.session.commit()
            print()
            print(f"✅ Successfully updated {updated} stories")
        
        if failed > 0:
            print(f"⚠️  Failed to update {failed} stories")

if __name__ == '__main__':
    main()
