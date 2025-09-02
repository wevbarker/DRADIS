"""
Configuration settings for DRADIS - arXiv monitoring system
All configuration consolidated into single .env file
"""
import os
import json
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# ARXIV API SETTINGS
# =============================================================================
ARXIV_RSS_FEEDS = {
    'hep-th': 'https://rss.arxiv.org/rss/hep-th',
    'gr-qc': 'https://rss.arxiv.org/rss/gr-qc', 
    'astro-ph.CO': 'https://rss.arxiv.org/rss/astro-ph.CO',
    'physics.comp-ph': 'https://rss.arxiv.org/rss/physics.comp-ph'
}

ARXIV_API_BASE = 'http://export.arxiv.org/api/query'

# =============================================================================
# AI API SETTINGS
# =============================================================================
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# =============================================================================
# DATABASE SETTINGS
# =============================================================================
DATABASE_PATH = os.getenv('DATABASE_PATH', 'dradis.db')

# =============================================================================
# USER PROFILE SETTINGS
# =============================================================================
USER_ORCID = os.getenv('USER_ORCID', '')
USER_INSPIRE_ID = os.getenv('USER_INSPIRE_ID', '')
USER_GOOGLE_SCHOLAR = os.getenv('USER_GOOGLE_SCHOLAR', '')
USER_EMAIL = os.getenv('USER_EMAIL', '')

# =============================================================================
# EMAIL SETTINGS
# =============================================================================
EMAIL_METHOD = os.getenv('EMAIL_METHOD', 'mutt')  # 'mutt' or 'smtp'

# SMTP settings (now from consolidated config)
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_TLS = os.getenv('SMTP_TLS', 'true').lower() == 'true'
SMTP_AUTH = os.getenv('SMTP_AUTH', 'true').lower() == 'true'
SMTP_STARTTLS = os.getenv('SMTP_STARTTLS', 'true').lower() == 'true'

# Mutt settings
MUTT_COMMAND = os.getenv('MUTT_COMMAND', 'mutt')
MUTT_FROM_ADDRESS = os.getenv('MUTT_FROM_ADDRESS', USER_EMAIL)
MUTT_DISABLE_CRYPTO = os.getenv('MUTT_DISABLE_CRYPTO', 'true').lower() == 'true'
MUTT_CHARSET = os.getenv('MUTT_CHARSET', 'utf-8')
MUTT_LOG_FILE = os.getenv('MUTT_LOG_FILE', '~/.msmtp-automated.log')

# =============================================================================
# FRIENDS/COLLABORATORS SETTINGS
# =============================================================================
def load_friends_data() -> Dict:
    """Load friends data from consolidated config (simple CSV format)"""
    names = os.getenv('FRIEND_NAMES', '').split(',') if os.getenv('FRIEND_NAMES') else []
    institutions = os.getenv('FRIEND_INSTITUTIONS', '').split(',') if os.getenv('FRIEND_INSTITUTIONS') else []
    papers = os.getenv('FRIEND_PAPERS', '').split(',') if os.getenv('FRIEND_PAPERS') else []
    
    friends = []
    for i, name in enumerate(names):
        if name.strip():
            friend = {
                'name': name.strip(),
                'institution': institutions[i].strip() if i < len(institutions) else '',
                'papers_together': int(papers[i]) if i < len(papers) and papers[i].strip().isdigit() else 1,
                'notes': f'Collaborated on {papers[i] if i < len(papers) else "1"} papers'
            }
            friends.append(friend)
    
    return {
        'friends': friends,
        'metadata': {
            'generated': '2025-09-01 22:50:00',
            'total_collaborators': len(friends),
            'source': 'consolidated .env config'
        }
    }

FRIENDS_DATA = load_friends_data()

# =============================================================================
# ANALYSIS SETTINGS
# =============================================================================
RELEVANCE_THRESHOLD = float(os.getenv('RELEVANCE_THRESHOLD', '0.7'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '20'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '5'))
MAX_DAILY_PAPERS = 100     # Maximum papers to analyze per day
RATE_LIMIT_DELAY = 1       # Seconds between API calls

# =============================================================================
# SYSTEM SETTINGS
# =============================================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'
DAILY_CHECK_TIME = "09:00"  # Time to run daily checks

# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================
def validate_config() -> List[str]:
    """Validate configuration settings"""
    errors = []
    
    # Critical settings
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is required")
    
    if not USER_EMAIL:
        errors.append("USER_EMAIL is required for notifications")
    
    # Email validation
    if EMAIL_METHOD not in ['mutt', 'smtp']:
        errors.append("EMAIL_METHOD must be 'mutt' or 'smtp'")
    
    if EMAIL_METHOD == 'smtp' and not SMTP_PASSWORD:
        errors.append("SMTP_PASSWORD is required when using SMTP")
    
    # Network settings
    if SMTP_PORT <= 0 or SMTP_PORT > 65535:
        errors.append("SMTP_PORT must be a valid port number (1-65535)")
    
    # Analysis settings
    if RELEVANCE_THRESHOLD < 0 or RELEVANCE_THRESHOLD > 1:
        errors.append("RELEVANCE_THRESHOLD must be between 0 and 1")
    
    if MAX_DAILY_PAPERS <= 0:
        errors.append("MAX_DAILY_PAPERS must be positive")
    
    if RATE_LIMIT_DELAY < 0:
        errors.append("RATE_LIMIT_DELAY must be non-negative")
    
    if BATCH_SIZE <= 0:
        errors.append("BATCH_SIZE must be positive")
    
    if MAX_WORKERS <= 0:
        errors.append("MAX_WORKERS must be positive")
    
    return errors

# Validate configuration on import
config_errors = validate_config()
if config_errors:
    import sys
    print("❌ Configuration errors detected:")
    for error in config_errors:
        print(f"  - {error}")
    if len(config_errors) > 3:  # Only exit for critical errors
        print("\nPlease check your .env file and fix these issues.")
        sys.exit(1)