"""
Database models and operations for DRADIS
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json

class DradisDB:
    def __init__(self, db_path: str = "dradis.db") -> None:
        self.db_path = db_path
        self.init_database()
    
    def init_database(self) -> None:
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Papers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    categories TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    updated_date TEXT,
                    pdf_url TEXT,
                    arxiv_url TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User research profile
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY,
                    orcid TEXT,
                    inspire_id TEXT,
                    google_scholar TEXT,
                    email TEXT,
                    research_keywords TEXT,
                    research_topics TEXT,
                    previous_papers TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Paper analysis results
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_analysis (
                    paper_id TEXT PRIMARY KEY,
                    relevance_score REAL,
                    key_concepts TEXT,
                    summary TEXT,
                    flagged BOOLEAN DEFAULT FALSE,
                    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers (id)
                )
            ''')
            
            # Notifications/contacts log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT,
                    notification_type TEXT,
                    recipient TEXT,
                    status TEXT,
                    sent_date TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers (id)
                )
            ''')
            
            conn.commit()
    
    def add_paper(self, paper_data: Dict) -> bool:
        """Add a paper to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO papers 
                    (id, title, authors, abstract, categories, published_date, 
                     updated_date, pdf_url, arxiv_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    paper_data['id'],
                    paper_data['title'],
                    json.dumps(paper_data['authors']),
                    paper_data['abstract'],
                    json.dumps(paper_data['categories']),
                    paper_data['published'],
                    paper_data.get('updated'),
                    paper_data.get('pdf_url'),
                    paper_data.get('arxiv_url')
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding paper: {e}")
            return False
    
    def get_unprocessed_papers(self) -> List[Dict]:
        """Get papers that haven't been analyzed yet"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM papers WHERE processed = FALSE
                ORDER BY published_date DESC
            ''')
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def mark_paper_processed(self, paper_id: str):
        """Mark a paper as processed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE papers SET processed = TRUE WHERE id = ?
            ''', (paper_id,))
            conn.commit()
    
    def save_paper_analysis(self, paper_id: str, analysis: Dict):
        """Save analysis results for a paper"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO paper_analysis
                (paper_id, relevance_score, key_concepts, summary, flagged)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                paper_id,
                analysis.get('relevance_score', 0.0),
                json.dumps(analysis.get('key_concepts', [])),
                analysis.get('summary', ''),
                analysis.get('flagged', False)
            ))
            conn.commit()
    
    def get_flagged_papers(self, limit: int = 10, target_date: str = None) -> List[Dict]:
        """Get papers flagged as relevant, optionally filtered by target date"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if target_date:
                # Handle different date formats in the database
                # Convert input date to multiple possible formats for matching
                from datetime import datetime
                
                # If target_date is in YYYY-MM-DD format, convert to multiple formats
                if len(target_date) == 10 and target_date.count('-') == 2:
                    try:
                        parsed_date = datetime.strptime(target_date, '%Y-%m-%d')
                        # Generate multiple format patterns to match against
                        iso_pattern = target_date  # 2025-09-03
                        rss_pattern = parsed_date.strftime('%d %b %Y')  # 03 Sep 2025
                        
                        cursor.execute('''
                            SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                            FROM papers p
                            JOIN paper_analysis pa ON p.id = pa.paper_id
                            WHERE pa.flagged = TRUE AND (
                                p.published_date LIKE ? OR 
                                p.published_date LIKE ?
                            )
                            ORDER BY pa.relevance_score DESC, p.published_date DESC
                            LIMIT ?
                        ''', (f'{iso_pattern}%', f'%{rss_pattern}%', limit))
                    except ValueError:
                        # If parsing fails, fall back to simple LIKE matching
                        cursor.execute('''
                            SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                            FROM papers p
                            JOIN paper_analysis pa ON p.id = pa.paper_id
                            WHERE pa.flagged = TRUE AND p.published_date LIKE ?
                            ORDER BY pa.relevance_score DESC, p.published_date DESC
                            LIMIT ?
                        ''', (f'{target_date}%', limit))
                else:
                    # For other date formats, use simple LIKE matching
                    cursor.execute('''
                        SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                        FROM papers p
                        JOIN paper_analysis pa ON p.id = pa.paper_id
                        WHERE pa.flagged = TRUE AND p.published_date LIKE ?
                        ORDER BY pa.relevance_score DESC, p.published_date DESC
                        LIMIT ?
                    ''', (f'{target_date}%', limit))
            else:
                # Get recent flagged papers (original behavior)
                cursor.execute('''
                    SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                    FROM papers p
                    JOIN paper_analysis pa ON p.id = pa.paper_id
                    WHERE pa.flagged = TRUE
                    ORDER BY pa.relevance_score DESC, p.published_date DESC
                    LIMIT ?
                ''', (limit,))
                
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def update_user_profile(self, profile_data: Dict):
        """Update user research profile"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Delete existing profile and insert new one
            cursor.execute('DELETE FROM user_profile')
            cursor.execute('''
                INSERT INTO user_profile
                (orcid, inspire_id, google_scholar, email, research_keywords, 
                 research_topics, previous_papers)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile_data.get('orcid'),
                profile_data.get('inspire_id'),
                profile_data.get('google_scholar'),
                profile_data.get('email'),
                json.dumps(profile_data.get('research_keywords', [])),
                json.dumps(profile_data.get('research_topics', [])),
                json.dumps(profile_data.get('previous_papers', []))
            ))
            conn.commit()
    
    def get_papers_by_date(self, target_date: str, limit: int = 100) -> List[Dict]:
        """Get all papers submitted on a specific date"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Handle different date formats in the database
            if len(target_date) == 10 and target_date.count('-') == 2:
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(target_date, '%Y-%m-%d')
                    # Generate multiple format patterns to match against
                    iso_pattern = target_date  # 2025-09-03
                    rss_pattern = parsed_date.strftime('%d %b %Y')  # 03 Sep 2025
                    
                    cursor.execute('''
                        SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                        FROM papers p
                        LEFT JOIN paper_analysis pa ON p.id = pa.paper_id
                        WHERE p.published_date LIKE ? OR p.published_date LIKE ?
                        ORDER BY p.published_date DESC
                        LIMIT ?
                    ''', (f'{iso_pattern}%', f'%{rss_pattern}%', limit))
                except ValueError:
                    # If parsing fails, fall back to simple LIKE matching
                    cursor.execute('''
                        SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                        FROM papers p
                        LEFT JOIN paper_analysis pa ON p.id = pa.paper_id
                        WHERE p.published_date LIKE ?
                        ORDER BY p.published_date DESC
                        LIMIT ?
                    ''', (f'{target_date}%', limit))
            else:
                # For other date formats, use simple LIKE matching
                cursor.execute('''
                    SELECT p.*, pa.relevance_score, pa.summary, pa.key_concepts
                    FROM papers p
                    LEFT JOIN paper_analysis pa ON p.id = pa.paper_id
                    WHERE p.published_date LIKE ?
                    ORDER BY p.published_date DESC
                    LIMIT ?
                ''', (f'{target_date}%', limit))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_user_profile(self) -> Optional[Dict]:
        """Get user research profile"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_profile LIMIT 1')
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                profile = dict(zip(columns, row))
                # Parse JSON fields
                profile['research_keywords'] = json.loads(profile['research_keywords'] or '[]')
                profile['research_topics'] = json.loads(profile['research_topics'] or '[]')
                profile['previous_papers'] = json.loads(profile['previous_papers'] or '[]')
                return profile
            return None