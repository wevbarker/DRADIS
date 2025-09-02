#!/usr/bin/env python3
"""
Unit tests for friends manager
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.friends_manager import FriendsManager

class TestFriendsManager(unittest.TestCase):
    """Test friends management functionality"""
    
    def setUp(self):
        """Set up test friends manager"""
        with patch('src.friends_manager.FRIENDS_DATA', {
            'friends': [
                {
                    'name': 'Lasenby, A.N.',
                    'institution': 'Cambridge',
                    'papers_together': 11,
                    'notes': 'Collaborated on 11 papers'
                },
                {
                    'name': 'Hobson, M.P.',
                    'institution': 'Cambridge', 
                    'papers_together': 11,
                    'notes': 'Collaborated on 11 papers'
                }
            ],
            'metadata': {
                'total_collaborators': 2,
                'source': 'test'
            }
        }):
            self.fm = FriendsManager()
    
    def test_normalize_name(self):
        """Test name normalization"""
        test_cases = [
            ("Dr. John Smith", "john smith"),
            ("Prof. Jane Doe PhD", "jane doe"),
            ("  Multiple   Spaces  ", "multiple spaces"),
            ("Smith, J.", "smith, j."),
        ]
        
        for input_name, expected in test_cases:
            result = self.fm.normalize_name(input_name)
            self.assertEqual(result, expected)
    
    def test_extract_name_components(self):
        """Test name component extraction"""
        # Test INSPIRE format (Surname, Initials)
        components = self.fm.extract_name_components("Smith, J.A.")
        self.assertEqual(components['surname'], 'smith')
        self.assertEqual(components['initials'], ['j', 'a'])
        
        # Test arXiv format (First Last)
        components = self.fm.extract_name_components("John Adam Smith")
        self.assertEqual(components['surname'], 'smith')
        self.assertEqual(components['initials'], ['j', 'a'])
    
    def test_name_similarity(self):
        """Test name similarity matching"""
        # Exact match
        similarity = self.fm.name_similarity("Smith, J.", "Smith, J.")
        self.assertEqual(similarity, 1.0)
        
        # Same surname, matching initials
        similarity = self.fm.name_similarity("Lasenby, A.N.", "Anthony N. Lasenby")
        self.assertGreaterEqual(similarity, 0.9)
        
        # Different surnames
        similarity = self.fm.name_similarity("Smith, J.", "Jones, J.")
        self.assertLess(similarity, 0.85)
        
        # Same surname, different initials
        similarity = self.fm.name_similarity("Smith, J.", "Smith, M.")
        self.assertLess(similarity, 0.85)
    
    def test_detect_friend_authors(self):
        """Test friend detection in paper authors"""
        paper = {
            'authors': ['John Smith', 'Anthony Lasenby', 'Jane Doe']
        }
        
        detected = self.fm.detect_friend_authors(paper)
        
        # Should detect Lasenby
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]['author_name'], 'Anthony Lasenby')
        self.assertGreaterEqual(detected[0]['similarity'], 0.85)
    
    def test_is_friend_paper(self):
        """Test if paper has friend authors"""
        # Paper with friend
        friend_paper = {
            'authors': ['Anthony Lasenby', 'Jane Doe']
        }
        self.assertTrue(self.fm.is_friend_paper(friend_paper))
        
        # Paper without friends
        non_friend_paper = {
            'authors': ['John Smith', 'Jane Doe']  
        }
        self.assertFalse(self.fm.is_friend_paper(non_friend_paper))
    
    def test_get_friend_boost(self):
        """Test relevance boost for friend papers"""
        # Friend paper should get boost
        friend_paper = {
            'authors': ['Anthony Lasenby', 'Jane Doe']
        }
        boost = self.fm.get_friend_boost(friend_paper)
        self.assertGreater(boost, 0)
        
        # Non-friend paper should get no boost
        non_friend_paper = {
            'authors': ['John Smith', 'Jane Doe']
        }
        boost = self.fm.get_friend_boost(non_friend_paper)
        self.assertEqual(boost, 0)

if __name__ == '__main__':
    unittest.main()