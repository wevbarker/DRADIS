#!/usr/bin/env python3
"""
Unit tests for configuration management
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import load_friends_data, validate_config

class TestConfig(unittest.TestCase):
    """Test configuration loading and validation"""
    
    @patch('config.os.getenv')
    def test_load_friends_data_empty(self, mock_getenv):
        """Test loading friends data with empty config"""
        mock_getenv.return_value = ''
        result = load_friends_data()
        
        self.assertIn('friends', result)
        self.assertIn('metadata', result)
        self.assertEqual(len(result['friends']), 0)
        self.assertEqual(result['metadata']['total_collaborators'], 0)
    
    @patch('config.os.getenv')
    def test_load_friends_data_single(self, mock_getenv):
        """Test loading friends data with single friend"""
        def side_effect(key, default=''):
            if key == 'FRIEND_NAMES':
                return 'John Smith'
            elif key == 'FRIEND_INSTITUTIONS':
                return 'MIT'
            elif key == 'FRIEND_PAPERS':
                return '5'
            return default
        
        mock_getenv.side_effect = side_effect
        result = load_friends_data()
        
        self.assertEqual(len(result['friends']), 1)
        friend = result['friends'][0]
        self.assertEqual(friend['name'], 'John Smith')
        self.assertEqual(friend['institution'], 'MIT')
        self.assertEqual(friend['papers_together'], 5)
    
    @patch('config.GEMINI_API_KEY', '')
    @patch('config.USER_EMAIL', '')
    def test_validate_config_missing_required(self):
        """Test config validation with missing required fields"""
        errors = validate_config()
        
        self.assertIn("GEMINI_API_KEY is required", errors)
        self.assertIn("USER_EMAIL is required for notifications", errors)
    
    @patch('config.GEMINI_API_KEY', 'test-key')
    @patch('config.USER_EMAIL', 'test@example.com')
    @patch('config.EMAIL_METHOD', 'invalid')
    def test_validate_config_invalid_method(self):
        """Test config validation with invalid email method"""
        errors = validate_config()
        
        self.assertIn("EMAIL_METHOD must be 'mutt' or 'smtp'", errors)
    
    @patch('config.GEMINI_API_KEY', 'test-key')
    @patch('config.USER_EMAIL', 'test@example.com')
    @patch('config.EMAIL_METHOD', 'mutt')
    @patch('config.RELEVANCE_THRESHOLD', 0.7)
    def test_validate_config_valid(self):
        """Test config validation with valid config"""
        errors = validate_config()
        
        # Should have no critical errors (some warnings might exist)
        critical_errors = [e for e in errors if 'required' in e.lower()]
        self.assertEqual(len(critical_errors), 0)

if __name__ == '__main__':
    unittest.main()