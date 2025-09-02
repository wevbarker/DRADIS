#!/usr/bin/env python3
"""
Test mutt email functionality for DRADIS
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.notification_system import NotificationSystem
from src.config import EMAIL_METHOD, USER_EMAIL

def test_mutt():
    """Test mutt email sending"""
    print("🧪 Testing DRADIS mutt integration")
    print("=" * 40)
    print(f"Email method: {EMAIL_METHOD}")
    print(f"Target email: {USER_EMAIL}")
    print("")
    
    if not USER_EMAIL:
        print("❌ USER_EMAIL not configured. Please set it in .env file.")
        return False
    
    # Create test report
    test_report = {
        'date': '2025-08-27',
        'total_flagged': 2,
        'high_relevance': [
            {
                'title': 'Test Paper: Quantum Foundations of String Theory',
                'authors': ['Alice Test', 'Bob Example'],
                'relevance_score': 0.95,
                'abstract': 'This is a test paper for DRADIS email functionality. It explores the quantum foundations of string theory with applications to black hole thermodynamics.',
                'arxiv_url': 'https://arxiv.org/abs/test.00001',
                'pdf_url': 'https://arxiv.org/pdf/test.00001.pdf',
                'id': 'test.00001'
            }
        ],
        'medium_relevance': [
            {
                'title': 'Test Paper: Dark Energy and Modified Gravity',
                'authors': ['Carol Test'],
                'relevance_score': 0.75,
                'abstract': 'A test paper examining dark energy models in the context of modified gravity theories.',
                'arxiv_url': 'https://arxiv.org/abs/test.00002', 
                'pdf_url': 'https://arxiv.org/pdf/test.00002.pdf',
                'id': 'test.00002'
            }
        ],
        'papers': [],
        'friend_papers': [],
        'friend_count': 0,
        'friend_names': []
    }
    
    # Initialize notification system and test
    notifier = NotificationSystem()
    
    print("📧 Attempting to send test email...")
    success = notifier.send_daily_report(test_report)
    
    if success:
        print("✅ Test email sent successfully!")
        print(f"📬 Check your email at {USER_EMAIL}")
        return True
    else:
        print("❌ Failed to send test email")
        print("💡 Troubleshooting tips:")
        print("   - Check that mutt is installed: which mutt")
        print("   - Verify mutt configuration: mutt -v")
        print("   - Test mutt manually: echo 'test' | mutt -s 'test' your-email@example.com")
        return False

if __name__ == '__main__':
    test_mutt()