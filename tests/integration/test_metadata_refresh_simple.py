from __future__ import annotations
import pytest
from unittest.mock import patch
from flask import Flask
from app.models import db, Story, Author, Category, Tag
from app.services.metadata_refresh_service import MetadataRefreshService
import time


@pytest.fixture
def metadata_service() -> MetadataRefreshService:
    """Create metadata refresh service instance."""
    return MetadataRefreshService()


class TestMetadataRefreshTagHandling:
    """Focused tests for tag handling in metadata refresh."""
    
    def test_tags_assigned_correctly_with_unique_slugs(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test that tags are created with proper slugs and assigned without duplicates."""
        with app.app_context():
            unique_id = str(int(time.time() * 1000000))
            
            author = Author(name=f"Author {unique_id}")
            db.session.add(author)
            db.session.flush()
            
            category = Category.query.filter_by(name="Romance").first()
            if not category:
                category = Category(name="Romance")
                db.session.add(category)
                db.session.flush()
            
            story = Story(
                title=f"Story {unique_id}",
                author_id=author.id,
                category_id=category.id,
                filename_base=f"story-{unique_id}"
            )
            db.session.add(story)
            db.session.commit()
            
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/story-{unique_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic', 'passion'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(story_id, unique_url, 'manual')
            
            assert result['success'] is True
            
            story = db.session.get(Story, story_id)
            tag_names = {tag.name.lower() for tag in story.tags}
            assert tag_names == {'first time', 'romantic', 'passion'}
            
            for tag in story.tags:
                assert tag.slug is not None
                assert tag.slug == Tag.create_slug(tag.name)
    
    def test_refresh_twice_no_duplicate_tags(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test that refreshing twice with same tags doesn't create duplicates."""
        with app.app_context():
            unique_id = str(int(time.time() * 1000000))
            
            author = Author(name=f"Author {unique_id}")
            db.session.add(author)
            db.session.flush()
            
            category = Category.query.filter_by(name="Romance").first()
            if not category:
                category = Category(name="Romance")
                db.session.add(category)
                db.session.flush()
            
            story = Story(
                title=f"Story {unique_id}",
                author_id=author.id,
                category_id=category.id,
                filename_base=f"story-{unique_id}"
            )
            db.session.add(story)
            db.session.commit()
            
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/story-{unique_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result1 = metadata_service.refresh_metadata_from_url(story_id, unique_url, 'manual')
            
            assert result1['success'] is True
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result2 = metadata_service.refresh_metadata_from_url(story_id, unique_url, 'manual')
            
            assert result2['success'] is True
            
            story = db.session.get(Story, story_id)
            assert len(story.tags) == 2
            
            all_first_time_tags = Tag.query.filter_by(slug='first-time').all()
            assert len(all_first_time_tags) == 1
