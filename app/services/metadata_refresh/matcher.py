from __future__ import annotations
from difflib import SequenceMatcher
from typing import Optional
from .literotica_search import LiteroticaSearchResult


class StoryMatcher:
    AUTO_MATCH_THRESHOLD = 0.85
    MIN_DISPLAY_THRESHOLD = 0.60

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title by removing common chapter/part suffixes for better matching."""
        import re
        normalized = title.lower().strip()
        
        # Remove common chapter/part patterns
        patterns = [
            r'\s+ch\.?\s*\d+$',
            r'\s+chapter\s+\d+$',
            r'\s+pt\.?\s*\d+$',
            r'\s+part\s+\d+$',
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        return normalized.strip()

    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        str1_normalized = str1.lower().strip()
        str2_normalized = str2.lower().strip()

        return SequenceMatcher(None, str1_normalized, str2_normalized).ratio()

    @classmethod
    def calculate_match_confidence(
        cls,
        expected_title: str,
        expected_author: str,
        result: LiteroticaSearchResult
    ) -> float:
        # Calculate direct similarity
        title_similarity = cls._calculate_similarity(expected_title, result.title)
        
        # Also calculate similarity with normalized titles (removing Ch./Pt. suffixes)
        normalized_expected = cls._normalize_title(expected_title)
        normalized_result = cls._normalize_title(result.title)
        normalized_similarity = cls._calculate_similarity(normalized_expected, normalized_result)
        
        # Use the better of the two scores
        return max(title_similarity, normalized_similarity)
    
    @classmethod
    def find_best_match(
        cls,
        title: str,
        author: str,
        results: list[LiteroticaSearchResult]
    ) -> Optional[LiteroticaSearchResult]:
        if not results:
            return None
        
        best_match = None
        best_confidence = 0.0
        
        for result in results:
            confidence = cls.calculate_match_confidence(title, author, result)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = result
        
        if best_confidence >= cls.AUTO_MATCH_THRESHOLD:
            return best_match
        
        return None
    
    @classmethod
    def rank_results(
        cls,
        title: str,
        author: str,
        results: list[LiteroticaSearchResult]
    ) -> list[tuple[LiteroticaSearchResult, float]]:
        ranked = []

        for result in results:
            confidence = cls.calculate_match_confidence(title, author, result)
            if confidence >= cls.MIN_DISPLAY_THRESHOLD:
                ranked.append((result, confidence))

        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked
