#!/usr/bin/env python3
"""
Unit tests for database operations
"""
import sys
import os
import unittest
import tempfile
import sqlite3

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DradisDB

class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = DradisDB(self.temp_db.name)
    
    def tearDown(self):
        """Clean up temporary database"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def test_database_initialization(self):
        """Test that database is initialized with proper tables"""
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            
            # Check papers table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='papers'")
            self.assertIsNotNone(cursor.fetchone())
            
            # Check user_profile table exists  
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'")
            self.assertIsNotNone(cursor.fetchone())
    
    def test_add_paper(self):
        """Test adding a paper to database"""
        paper_data = {
            'id': 'test.00001',
            'title': 'Test Paper',
            'abstract': 'This is a test abstract',
            'authors': ['Test Author'],
            'categories': ['hep-th'],
            'published': '2024-01-01',
            'updated': '2024-01-01',
            'arxiv_url': 'https://arxiv.org/abs/test.00001',
            'pdf_url': 'https://arxiv.org/pdf/test.00001.pdf'
        }
        
        result = self.db.add_paper(paper_data)
        self.assertTrue(result)
        
        # Verify paper was added
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM papers WHERE id = ?", (paper_data['id'],))
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)
    
    def test_add_duplicate_paper(self):
        """Test adding duplicate paper (should not create duplicate)"""
        paper_data = {
            'id': 'test.00001',
            'title': 'Test Paper',
            'abstract': 'This is a test abstract',
            'authors': ['Test Author'],
            'categories': ['hep-th'],
            'published': '2024-01-01',
            'updated': '2024-01-01',
            'arxiv_url': 'https://arxiv.org/abs/test.00001',
            'pdf_url': 'https://arxiv.org/pdf/test.00001.pdf'
        }
        
        # Add paper twice
        self.db.add_paper(paper_data)
        self.db.add_paper(paper_data)
        
        # Should only have one copy
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM papers WHERE id = ?", (paper_data['id'],))
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)
    
    def test_get_unprocessed_papers(self):
        """Test retrieving unprocessed papers"""
        # Add a test paper
        paper_data = {
            'id': 'test.00001',
            'title': 'Test Paper',
            'abstract': 'This is a test abstract',
            'authors': ['Test Author'],
            'categories': ['hep-th'],
            'published': '2024-01-01',
            'updated': '2024-01-01',
            'arxiv_url': 'https://arxiv.org/abs/test.00001',
            'pdf_url': 'https://arxiv.org/pdf/test.00001.pdf'
        }
        self.db.add_paper(paper_data)
        
        # Should retrieve the unprocessed paper
        unprocessed = self.db.get_unprocessed_papers()
        self.assertEqual(len(unprocessed), 1)
        self.assertEqual(unprocessed[0]['id'], 'test.00001')

if __name__ == '__main__':
    unittest.main()