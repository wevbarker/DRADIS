#!/usr/bin/env python3
"""
Unit tests for relevance engine
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.relevance_engine import RelevanceEngine

class TestRelevanceEngine(unittest.TestCase):
    """Test relevance scoring functionality"""
    
    def setUp(self):
        """Set up test relevance engine"""
        with patch('src.relevance_engine.DradisDB'), \
             patch('src.relevance_engine.FriendsManager'):
            self.engine = RelevanceEngine()
    
    def test_calculate_keyword_similarity(self):
        """Test keyword similarity calculation"""
        paper = {
            'title': 'Black holes in string theory',
            'abstract': 'We study black hole solutions in string theory and their thermodynamic properties.',
            'categories': ['hep-th']
        }
        
        user_profile = {
            'research_keywords': ['black holes', 'string theory', 'thermodynamics'],
            'research_topics': ['theoretical physics', 'quantum gravity']
        }
        
        similarity = self.engine.calculate_keyword_similarity(paper, user_profile)
        self.assertGreater(similarity, 0.5)  # Should find strong keyword matches
    
    def test_calculate_keyword_similarity_no_match(self):
        """Test keyword similarity with no matching keywords"""
        paper = {
            'title': 'Machine learning applications in chemistry',
            'abstract': 'We apply neural networks to predict chemical reaction outcomes.',
            'categories': ['cs.ML']
        }
        
        user_profile = {
            'research_keywords': ['black holes', 'string theory', 'cosmology'],
            'research_topics': ['theoretical physics', 'quantum gravity']
        }
        
        similarity = self.engine.calculate_keyword_similarity(paper, user_profile)
        self.assertLess(similarity, 0.3)  # Should find few or no matches
    
    def test_calculate_category_similarity(self):
        """Test category similarity calculation"""
        paper = {
            'categories': ['hep-th', 'gr-qc']
        }
        
        user_profile = {
            'research_keywords': ['string theory', 'black holes']  # These map to hep-th and gr-qc
        }
        
        similarity = self.engine.calculate_category_similarity(paper, user_profile)
        self.assertGreater(similarity, 0)  # Should find overlap in hep-th
    
    def test_calculate_category_similarity_no_overlap(self):
        """Test category similarity with no overlap"""
        paper = {
            'categories': ['cs.ML', 'stat.ML']
        }
        
        user_profile = {
            'research_keywords': ['computer vision', 'neural networks']  # No overlap with physics
        }
        
        similarity = self.engine.calculate_category_similarity(paper, user_profile)
        self.assertEqual(similarity, 0)  # Should find no overlap
    
    def test_calculate_recency_score(self):
        """Test recency scoring"""
        from datetime import datetime, timedelta
        
        # Recent paper
        recent_date = datetime.now().strftime('%Y-%m-%d')
        recent_paper = {'published': recent_date}
        recent_score = self.engine.calculate_recency_score(recent_paper)
        
        # Old paper
        old_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        old_paper = {'published': old_date}
        old_score = self.engine.calculate_recency_score(old_paper)
        
        self.assertGreater(recent_score, old_score)
    
    def test_calculate_citation_potential(self):
        """Test citation potential calculation"""
        paper = {
            'title': 'Quantum gravity and black holes',
            'abstract': 'A comprehensive review of quantum gravity approaches to black hole physics.',
            'categories': ['hep-th', 'gr-qc']
        }
        
        user_profile = {
            'research_keywords': ['quantum gravity', 'black holes'],
            'research_topics': ['theoretical physics'],
            'categories': ['hep-th']
        }
        
        potential = self.engine.calculate_citation_potential(paper, user_profile)
        self.assertGreaterEqual(potential, 0)
        self.assertLessEqual(potential, 1)

if __name__ == '__main__':
    unittest.main()