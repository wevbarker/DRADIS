"""
Notification and author contact system for DRADIS
"""
import smtplib
import time
import subprocess
import tempfile
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
import re

from .config import (EMAIL_METHOD, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, 
                    USER_EMAIL, RELEVANCE_THRESHOLD, MUTT_COMMAND, MUTT_FROM_ADDRESS)
from .database import DradisDB
from .friends_manager import FriendsManager

class NotificationSystem:
    def __init__(self) -> None:
        self.db = DradisDB()
        self.friends_manager = FriendsManager()
        
    def generate_daily_report(self, target_date: str = None) -> Dict:
        """Generate daily report of flagged papers"""
        flagged_papers = self.db.get_flagged_papers(limit=20, target_date=target_date)
        
        # Also get all papers for the date to check for friend papers
        # (friend papers should be included even if not AI-flagged)
        all_papers = self.db.get_papers_by_date(target_date) if target_date else []
        
        # Identify friend papers from all papers, not just flagged ones
        friend_summary = self.friends_manager.get_friend_papers_summary(all_papers)
        
        # Combine flagged papers with friend papers (avoiding duplicates)
        all_relevant_papers = flagged_papers.copy()
        flagged_ids = {p['id'] for p in flagged_papers}
        
        # Add friend papers that weren't already flagged
        for friend_paper in friend_summary['friend_papers']:
            if friend_paper['id'] not in flagged_ids:
                all_relevant_papers.append(friend_paper)
        
        report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_flagged': len(all_relevant_papers),  # Include friend papers in count
            'high_relevance': [p for p in all_relevant_papers if p.get('relevance_score', 0) > 0.8],
            'medium_relevance': [p for p in all_relevant_papers if 0.6 <= p.get('relevance_score', 0) <= 0.8],
            'papers': all_relevant_papers,
            'friend_papers': friend_summary['friend_papers'],
            'friend_count': friend_summary['friend_count'],
            'friend_names': friend_summary['friend_names']
        }
        
        return report
    
    def format_daily_email(self, report: Dict, date_info: str = None) -> str:
        """Format daily report as email HTML"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #fff5f5; color: #2d1b1b; }}
                .header {{ background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                .header h2 {{ margin: 0; font-size: 24px; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); }}
                .header p {{ margin: 5px 0; opacity: 0.9; }}
                .paper {{ border: 2px solid #fecaca; margin: 15px 0; padding: 15px; background-color: #fefefe; border-radius: 6px; }}
                .high {{ border-left: 6px solid #dc2626; background-color: #fef2f2; }}
                .medium {{ border-left: 6px solid #f97316; background-color: #fff7ed; }}
                .friend {{ border-left: 6px solid #059669; background-color: #f0fdf4; }}
                .score {{ font-weight: bold; color: #dc2626; background-color: #fee2e2; padding: 2px 8px; border-radius: 12px; }}
                .title {{ font-size: 18px; font-weight: bold; color: #991b1b; margin-bottom: 8px; }}
                .authors {{ color: #7c2d12; font-style: italic; margin-bottom: 10px; }}
                .abstract {{ margin-top: 12px; color: #451a03; line-height: 1.4; }}
                .links {{ margin-top: 15px; }}
                .links a {{ margin-right: 15px; color: #dc2626; font-weight: bold; text-decoration: none; }}
                .links a:hover {{ color: #b91c1c; text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>DRADIS EARLY WARNING SYSTEM</h2>
                <p>DATE: {date_info if date_info else report['date']}</p>
                <p>TARGET: Found <strong>{report['total_flagged']}</strong> relevant papers today</p>
                <p>ANALYSIS: High relevance: {len(report['high_relevance'])}, Medium relevance: {len(report['medium_relevance'])}</p>
                {f"<p>FRIENDS: <strong>{report['friend_count']}</strong> papers by friends: {', '.join(report['friend_names'])}</p>" if report['friend_count'] > 0 else ""}
            </div>
        """
        
        # Friend papers section (if any)
        if report['friend_papers']:
            html += "<h3>👥 Papers by Friends</h3>"
            for paper in report['friend_papers']:
                html += self._format_paper_html(paper, 'friend')
        
        # High relevance papers first
        if report['high_relevance']:
            html += "<h3>🔴 High Relevance Papers</h3>"
            for paper in report['high_relevance']:
                html += self._format_paper_html(paper, 'high')
        
        # Medium relevance papers
        if report['medium_relevance']:
            html += "<h3>🟡 Medium Relevance Papers</h3>"
            for paper in report['medium_relevance']:
                html += self._format_paper_html(paper, 'medium')
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _format_paper_html(self, paper: Dict, relevance_class: str) -> str:
        """Format a single paper for email"""
        # Parse JSON fields if they're strings
        authors = paper['authors']
        if isinstance(authors, str):
            try:
                import json
                authors = json.loads(authors)
            except:
                authors = [authors]
        
        authors_str = ', '.join(authors[:5])  # Limit to first 5 authors
        if len(authors) > 5:
            authors_str += ' et al.'
        
        # Add friend indicators if this is a friend paper
        friend_indicator = ""
        if relevance_class == 'friend' and 'detected_friends' in paper:
            friend_names = [d['friend']['name'] for d in paper['detected_friends']]
            friend_indicator = f"<div style='color: #4CAF50; font-weight: bold;'>👥 Friend authors: {', '.join(friend_names)}</div>"
        
        return f"""
        <div class="paper {relevance_class}">
            <div class="title">{paper['title']}</div>
            <div class="authors">{authors_str}</div>
            {friend_indicator}
            <div class="score">Relevance Score: {paper['relevance_score']:.2f}</div>
            <div class="abstract">{paper['abstract'][:300]}...</div>
            <div class="links">
                <a href="{paper.get('arxiv_url', '#')}">arXiv</a>
                <a href="{paper.get('pdf_url', '#')}">PDF</a>
            </div>
        </div>
        """
    
    def send_daily_report(self, report: Dict, target_date: str = None) -> bool:
        """Send daily report email"""
        if EMAIL_METHOD.lower() == 'mutt':
            return self._send_via_mutt(report, target_date)
        else:
            return self._send_via_smtp(report)
    
    def _send_via_mutt(self, report: Dict, target_date: str = None) -> bool:
        """Send email using mutt command"""
        try:
            if not USER_EMAIL:
                print("USER_EMAIL not configured")
                return False
            
            # Create subject line with target date and timestamp
            from datetime import datetime
            creation_time = datetime.now()
            crawl_timestamp = creation_time.strftime("%Y-%m-%d_%H-%M-%S")
            
            if target_date:
                date_info = f"{target_date} (created {creation_time.strftime('%Y-%m-%d %H:%M')})"
                if report['total_flagged'] == 0:
                    subject = f"NO DRADIS CONTACTS - {target_date}"
                elif report['total_flagged'] == 1:
                    subject = f"DRADIS CONTACT - {target_date}"
                else:
                    subject = f"MULTIPLE DRADIS CONTACTS - {target_date}"
            else:
                date_info = f"{creation_time.strftime('%Y-%m-%d')} (created {creation_time.strftime('%H:%M')})"
                if report['total_flagged'] == 0:
                    subject = f"NO DRADIS CONTACTS - {creation_time.strftime('%Y-%m-%d')}"
                elif report['total_flagged'] == 1:
                    subject = f"DRADIS CONTACT - {creation_time.strftime('%Y-%m-%d')}"
                else:
                    subject = f"MULTIPLE DRADIS CONTACTS - {creation_time.strftime('%Y-%m-%d')}"
            
            html_content = self.format_daily_email(report, date_info)
            
            # Create reports directory if it doesn't exist
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Save HTML report in reports directory
            report_filename = f"dradis_report_{crawl_timestamp}.html"
            report_path = os.path.join(reports_dir, report_filename)
            with open(report_path, 'w') as f:
                f.write(html_content)
                print(f"📄 HTML report saved: {report_path}")
            
            # Create temporary file for email sending
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_file = f.name
            
            try:
                # Use simple mutt command without custom config
                cmd = [
                    MUTT_COMMAND,
                    '-e', 'set content_type=text/html',  # Set content type to HTML
                    '-e', 'set sendmail="/usr/bin/msmtp"',  # Use msmtp directly
                    '-e', f'set from="{self.mutt_from_address}"',  # Set from address
                    '-e', 'set use_from=yes',
                    '-s', subject,  # Subject
                    USER_EMAIL  # Recipient
                ]
                
                # Send email with HTML file as input
                with open(temp_file, 'r') as html_file:
                    result = subprocess.run(
                        cmd,
                        stdin=html_file,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                
                if result.returncode == 0:
                    print(f"✅ Daily report sent via mutt to {USER_EMAIL}")
                    return True
                else:
                    print(f"❌ Mutt failed: {result.stderr}")
                    return False
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            
        except subprocess.TimeoutExpired:
            print("❌ Mutt command timed out")
            return False
        except Exception as e:
            print(f"❌ Error sending via mutt: {e}")
            return False
    
    def _send_via_smtp(self, report: Dict) -> bool:
        """Send email using SMTP (fallback method)"""
        try:
            if not USER_EMAIL or not SMTP_USER or not SMTP_PASSWORD:
                print("SMTP configuration not complete")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"DRADIS Daily Report - {report['total_flagged']} Relevant Papers"
            msg['From'] = SMTP_USER
            msg['To'] = USER_EMAIL
            
            # Create HTML content
            html_content = self.format_daily_email(report)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Daily report sent via SMTP to {USER_EMAIL}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending via SMTP: {e}")
            return False
    
    def generate_author_contact_email(self, paper: Dict, contact_reason: str) -> Dict:
        """Generate professional email for contacting paper authors"""
        # Extract first author email if available
        authors = paper['authors']
        if isinstance(authors, str):
            try:
                import json
                authors = json.loads(authors)
            except:
                authors = [authors]
        
        # Create professional email template
        subject_templates = {
            'citation': f"Question about your recent work: {paper['title'][:50]}...",
            'collaboration': f"Research synergy with your paper: {paper['title'][:50]}...",
            'clarification': f"Follow-up question on: {paper['title'][:50]}..."
        }
        
        body_templates = {
            'citation': f"""Dear Dr. {authors[0].split()[-1] if authors else 'Author'},

I recently read your paper "{paper['title']}" with great interest. Your work on [SPECIFIC TOPIC] is highly relevant to my research in theoretical physics.

I believe there may be opportunities for citing your work in my upcoming research, particularly regarding [SPECIFIC CONNECTION]. Would you be interested in discussing potential connections between our work?

My research profile: [PROFILE_LINKS]

Best regards,
[YOUR_NAME]
[YOUR_AFFILIATION]
[YOUR_EMAIL]""",
            
            'collaboration': f"""Dear Dr. {authors[0].split()[-1] if authors else 'Author'},

I found your recent paper "{paper['title']}" very compelling and believe there may be synergies with my current research in theoretical physics.

Your approach to [SPECIFIC_ASPECT] complements my work on [YOUR_WORK]. I would be interested in exploring potential collaboration opportunities.

Please find my research profile here: [PROFILE_LINKS]

Best regards,
[YOUR_NAME]
[YOUR_AFFILIATION]
[YOUR_EMAIL]"""
        }
        
        return {
            'subject': subject_templates.get(contact_reason, subject_templates['citation']),
            'body': body_templates.get(contact_reason, body_templates['citation']),
            'authors': authors,
            'paper_id': paper['id']
        }
    
    def extract_author_emails(self, paper: Dict) -> List[str]:
        """Extract author email addresses from paper metadata"""
        # This is a placeholder - in practice, would use arXiv API 
        # or other sources to get author contact information
        emails = []
        
        # arXiv doesn't typically provide email addresses directly
        # Would need to use INSPIRE, ORCID, or institutional directories
        
        return emails
    
    def send_author_contact(self, paper: Dict, contact_reason: str, 
                          custom_message: str = None) -> bool:
        """Send professional email to paper authors"""
        try:
            # Generate email content
            if custom_message:
                email_content = {
                    'subject': f"Regarding your paper: {paper['title'][:50]}...",
                    'body': custom_message,
                    'authors': paper['authors'],
                    'paper_id': paper['id']
                }
            else:
                email_content = self.generate_author_contact_email(paper, contact_reason)
            
            # Get author emails (placeholder - would need actual implementation)
            author_emails = self.extract_author_emails(paper)
            
            if not author_emails:
                print(f"No email addresses found for paper {paper['id']}")
                return False
            
            # Send to first author only to avoid spam
            recipient = author_emails[0]
            
            msg = MIMEText(email_content['body'])
            msg['Subject'] = email_content['subject']
            msg['From'] = SMTP_USER
            msg['To'] = recipient
            
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            # Log the contact
            self._log_notification(paper['id'], 'author_contact', recipient, 'sent')
            
            print(f"Author contact sent for paper {paper['id']}")
            return True
            
        except Exception as e:
            print(f"Error sending author contact: {e}")
            return False
    
    def _log_notification(self, paper_id: str, notification_type: str, 
                         recipient: str, status: str):
        """Log notification in database"""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO notifications 
                    (paper_id, notification_type, recipient, status, sent_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (paper_id, notification_type, recipient, status, datetime.now()))
                conn.commit()
        except Exception as e:
            print(f"Error logging notification: {e}")
    
    def get_daily_summary(self) -> str:
        """Get a brief text summary for CLI display"""
        flagged_papers = self.db.get_flagged_papers(limit=5)
        
        if not flagged_papers:
            return "No relevant papers found today."
        
        summary = f"Found {len(flagged_papers)} relevant papers:\n\n"
        
        for i, paper in enumerate(flagged_papers[:3], 1):
            summary += f"{i}. {paper['title'][:60]}...\n"
            summary += f"   Score: {paper['relevance_score']:.2f} | arXiv: {paper['id']}\n\n"
        
        if len(flagged_papers) > 3:
            summary += f"...and {len(flagged_papers) - 3} more papers.\n"
        
        return summary