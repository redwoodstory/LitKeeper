from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask.testing import FlaskClient
from app.models import db, Story, Author, Category, Tag
from app.services.metadata_refresh_service import MetadataRefreshService
import time


@pytest.fixture
def metadata_service() -> MetadataRefreshService:
    """Create metadata refresh service instance."""
    return MetadataRefreshService()


class TestMetadataRefreshService:
    
    def test_refresh_metadata_with_new_tags(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test refreshing metadata with completely new tags."""
        with app.app_context():
            unique_id = str(int(time.time() * 1000000))
            
            author = Author.query.filter_by(name="Test Author").first()
            if not author:
                author = Author(name="Test Author")
                db.session.add(author)
                db.session.flush()
            
            category = Category.query.filter_by(name="Romance").first()
            if not category:
                category = Category(name="Romance")
                db.session.add(category)
                db.session.flush()
            
            tag1 = Tag.query.filter_by(name="love").first()
            if not tag1:
                tag1 = Tag(name="love")
                db.session.add(tag1)
            
            tag2 = Tag.query.filter_by(name="drama").first()
            if not tag2:
                tag2 = Tag(name="drama")
                db.session.add(tag2)
            
            db.session.flush()
            
            story = Story(
                title=f"Test Story {unique_id}",
                author_id=author.id,
                category_id=category.id,
                filename_base=f"test-story-{unique_id}"
            )
            story.tags = [tag1, tag2]
            db.session.add(story)
            db.session.commit()
            
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic', 'passion'],
                'page_count': 1,
                'author_url': 'https://www.literotica.com/authors/testauthor'
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result['success'] is True
            assert 'tags' in result['fields_changed']
            
            story = db.session.get(Story, story_id)
            tag_names = {tag.name for tag in story.tags}
            assert tag_names == {'first time', 'romantic', 'passion'}
            
            for tag in story.tags:
                assert tag.slug is not None
                assert tag.slug == Tag.create_slug(tag.name)
    
    def test_refresh_metadata_with_duplicate_tags(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test refreshing metadata when tags already exist in database."""
        with app.app_context():
            existing_tag = Tag.query.filter_by(name='first time').first()
            if not existing_tag:
                existing_tag = Tag(name='first time')
                db.session.add(existing_tag)
                db.session.commit()
            
            story = create_test_story(app)
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result['success'] is True
            
            story = db.session.get(Story, story_id)
            tag_names = {tag.name for tag in story.tags}
            assert tag_names == {'first time', 'romantic'}
            
            all_tags = Tag.query.filter(Tag.name.in_(['first time', 'romantic'])).all()
            assert len(all_tags) == 2
            
            for tag in all_tags:
                assert Tag.query.filter_by(slug=tag.slug).count() == 1
    
    def test_refresh_metadata_with_same_slug_different_name(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test that tags with same slug but different names reuse existing tag."""
        with app.app_context():
            existing_tag = Tag.query.filter_by(name='first-time').first()
            if not existing_tag:
                existing_tag = Tag(name='first-time')
                db.session.add(existing_tag)
                db.session.commit()
            
            story = create_test_story(app)
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result['success'] is True
            
            story = db.session.get(Story, story_id)
            assert len(story.tags.all()) == 1
            
            tag = story.tags.first()
            assert tag.id == existing_tag.id
            assert tag.name == 'first-time'
    
    def test_refresh_metadata_multiple_times_same_tags(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test refreshing metadata multiple times with same tags doesn't create duplicates."""
        with app.app_context():
            story = create_test_story(app)
            story_id = story.id
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result1 = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result1['success'] is True
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result2 = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result2['success'] is True
            
            story = db.session.get(Story, story_id)
            tag_names = {tag.name for tag in story.tags}
            assert tag_names == {'first time', 'romantic'}
            
            all_first_time_tags = Tag.query.filter_by(name='first time').all()
            assert len(all_first_time_tags) == 1
            
            all_romantic_tags = Tag.query.filter_by(name='romantic').all()
            assert len(all_romantic_tags) == 1
    
    def test_refresh_metadata_replacing_tags(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test that old tags are properly replaced with new ones."""
        with app.app_context():
            story = create_test_story(app)
            story_id = story.id
            original_tag_names = {tag.name for tag in story.tags}
            assert original_tag_names == {'love', 'drama'}
            
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Romance',
                'tags': ['first time', 'romantic', 'passion'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result['success'] is True
            
            story = db.session.get(Story, story_id)
            new_tag_names = {tag.name for tag in story.tags}
            assert new_tag_names == {'first time', 'romantic', 'passion'}
            assert new_tag_names != original_tag_names
    
    def test_refresh_metadata_with_category_change(self, app: Flask, metadata_service: MetadataRefreshService):
        """Test refreshing metadata with category change."""
        with app.app_context():
            story = create_test_story(app)
            story_id = story.id
            assert story.category.name == 'Romance'
            
            unique_url = f'https://www.literotica.com/s/test-story-{story_id}'
            
            mock_metadata = {
                'category': 'Erotic Couplings',
                'tags': ['love'],
                'page_count': 1
            }
            
            with patch.object(metadata_service.searcher, 'fetch_metadata_from_url', return_value=mock_metadata):
                result = metadata_service.refresh_metadata_from_url(
                    story_id,
                    unique_url,
                    'manual'
                )
            
            assert result['success'] is True
            assert 'category' in result['fields_changed']
            
            story = db.session.get(Story, story_id)
            assert story.category.name == 'Erotic Couplings'
