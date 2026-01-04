from __future__ import annotations
from difflib import SequenceMatcher
from typing import Optional
from .literotica_search import LiteroticaSearchResult


class StoryMatcher:
    AUTO_MATCH_THRESHOLD = 0.85
    MIN_DISPLAY_THRESHOLD = 0.60

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
        title_similarity = cls._calculate_similarity(expected_title, result.title)

        return title_similarity
    
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
