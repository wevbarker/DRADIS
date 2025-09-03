#!/usr/bin/env python3
"""
DRADIS - Automated arXiv Research Discovery and Analysis System
Main application and CLI interface
"""
import argparse
import sys
from datetime import datetime
import json

from .config import USER_ORCID, USER_INSPIRE_ID, USER_GOOGLE_SCHOLAR, USER_EMAIL
from .database import DradisDB
from .arxiv_monitor import ArxivMonitor
from .paper_analyzer import PaperAnalyzer
from .relevance_engine import RelevanceEngine
from .notification_system import NotificationSystem
from .profile_builder import ProfileBuilder
from .fast_analyzer import FastPaperAnalyzer
from .friends_manager import FriendsManager
from .logger import get_logger, set_dev_mode

class DRADIS:
    def __init__(self, skip_replacements: bool = True) -> None:
        self.logger = get_logger()
        self.db = DradisDB()
        self.monitor = ArxivMonitor(skip_replacements=skip_replacements)
        self.analyzer = PaperAnalyzer()
        self.relevance_engine = RelevanceEngine()
        self.notification_system = NotificationSystem()
        self.profile_builder = ProfileBuilder()
        self.fast_analyzer = FastPaperAnalyzer()
        self.friends_manager = FriendsManager()
        self.logger.info("DRADIS initialized", skip_replacements=skip_replacements)
    
    def setup_user_profile(self, interactive=True):
        """Set up user research profile"""
        print("Setting up your research profile...")
        
        if interactive:
            # Interactive profile setup
            orcid = input(f"ORCID ID [{USER_ORCID}]: ").strip() or USER_ORCID
            inspire_id = input(f"INSPIRE ID [{USER_INSPIRE_ID}]: ").strip() or USER_INSPIRE_ID
            google_scholar = input(f"Google Scholar URL [{USER_GOOGLE_SCHOLAR}]: ").strip() or USER_GOOGLE_SCHOLAR
            email = input(f"Email [{USER_EMAIL}]: ").strip() or USER_EMAIL
            
            print("\nEnter your research keywords (comma-separated):")
            print("Examples: string theory, quantum field theory, cosmology, black holes")
            keywords_input = input("Keywords: ").strip()
            keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
            
            print("\nEnter your main research topics (comma-separated):")
            print("Examples: AdS/CFT correspondence, quantum gravity, dark energy")
            topics_input = input("Topics: ").strip()
            topics = [t.strip() for t in topics_input.split(',') if t.strip()]
            
            print("\nEnter titles of your recent papers (one per line, empty line to finish):")
            papers = []
            while True:
                paper = input("Paper title: ").strip()
                if not paper:
                    break
                papers.append(paper)
        
        else:
            # Use environment variables
            orcid = USER_ORCID
            inspire_id = USER_INSPIRE_ID
            google_scholar = USER_GOOGLE_SCHOLAR
            email = USER_EMAIL
            keywords = []
            topics = []
            papers = []
        
        profile_data = {
            'orcid': orcid,
            'inspire_id': inspire_id,
            'google_scholar': google_scholar,
            'email': email,
            'research_keywords': keywords,
            'research_topics': topics,
            'previous_papers': papers
        }
        
        self.db.update_user_profile(profile_data)
        print("✅ User profile saved successfully!")
        
        return profile_data
    
    def build_automated_profile(self, inspire_id: str = None, orcid_id: str = None, 
                               author_name: str = None):
        """Build profile automatically from author's papers"""
        print("🚀 Building automated research profile from your publications...")
        
        # Use provided IDs or fall back to config
        inspire_id = inspire_id or USER_INSPIRE_ID
        orcid_id = orcid_id or USER_ORCID
        
        if not inspire_id and not orcid_id and not author_name:
            print("❌ No INSPIRE ID, ORCID ID, or author name provided")
            print("   Please provide at least one identifier")
            return None
        
        try:
            # Build profile from papers
            profile = self.profile_builder.build_profile_from_ids(
                inspire_id=inspire_id,
                orcid_id=orcid_id,
                author_name=author_name
            )
            
            if not profile:
                print("❌ Could not build profile from available data")
                return None
            
            # Save to database
            user_info = {
                'orcid': orcid_id,
                'inspire_id': inspire_id,
                'google_scholar': USER_GOOGLE_SCHOLAR,
                'email': USER_EMAIL
            }
            
            success = self.profile_builder.save_profile_to_database(profile, user_info)
            
            if success:
                print("\n🎉 Automated profile building complete!")
                print(f"📊 Found {profile.get('paper_count', 0)} papers")
                print(f"🔬 Primary areas: {', '.join(profile.get('primary_research_areas', [])[:3])}")
                print(f"🏷️  Keywords: {len(profile.get('research_keywords', []))} extracted")
                print(f"📝 Summary: {profile.get('research_summary', '')[:100]}...")
                
                return profile
            else:
                print("❌ Failed to save profile to database")
                return None
                
        except Exception as e:
            print(f"❌ Error building automated profile: {e}")
            return None
    
    def run_fast_harvest(self, target_date: str = None, send_email: bool = True):
        """Run fast parallel daily harvest"""
        start_time = datetime.now()
        self.logger.operation_start("Fast Harvest", start_time=start_time.isoformat())
        print(f"⚡ Starting FAST harvest at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check if user profile exists
        self.logger.info("Checking user profile...")
        user_profile = self.db.get_user_profile()
        if not user_profile:
            self.logger.error("No user profile found")
            print("❌ No user profile found. Please run: python dradis.py setup")
            return
        
        self.logger.info("User profile loaded", email=user_profile.get('email'))
        
        # Harvest new papers
        self.logger.operation_start("Paper Harvesting")
        new_papers = self.monitor.daily_harvest(target_date)
        self.logger.operation_end("Paper Harvesting", new_papers=new_papers)
        print(f"📥 Harvested {new_papers} new papers")
        
        if new_papers == 0:
            self.logger.info("No new papers to analyze")
            print("ℹ️  No new papers to analyze today")
            return
        
        # Fast parallel analysis
        self.logger.operation_start("Fast Parallel Analysis")
        analyzed_papers = self.fast_analyzer.fast_analyze_pending_papers()
        self.logger.operation_end("Fast Parallel Analysis", analyzed=analyzed_papers)
        print(f"⚡ Fast-analyzed {analyzed_papers} papers")
        
        # Generate and send daily report
        self.logger.operation_start("Report Generation")
        report = self.notification_system.generate_daily_report(target_date)
        self.logger.operation_end("Report Generation", flagged=report['total_flagged'])
        print(f"📊 Generated report: {report['total_flagged']} relevant papers found")
        
        # Send email report if configured and requested
        if send_email:
            self.logger.operation_start("Email Sending")
            email_sent = self.notification_system.send_daily_report(report, target_date)
            if email_sent:
                self.logger.operation_end("Email Sending", success=True)
                print("📧 Daily report sent via email")
            else:
                self.logger.operation_end("Email Sending", success=False)
                print("⚠️  Email not configured or failed to send")
        
        # Display summary
        summary = self.notification_system.get_daily_summary()
        print("\n" + "="*50)
        print("⚡ FAST DAILY SUMMARY")
        print("="*50)
        print(summary)
        
        # Log completion
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self.logger.operation_end("Fast Harvest", 
                                duration_seconds=duration,
                                papers_harvested=new_papers,
                                papers_analyzed=analyzed_papers,
                                papers_flagged=report['total_flagged'])
    
    def run_daily_harvest(self, target_date: str = None):
        """Run the daily paper harvesting process"""
        print(f"🔄 Starting daily harvest at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check if user profile exists
        user_profile = self.db.get_user_profile()
        if not user_profile:
            print("❌ No user profile found. Please run: python dradis.py setup")
            return
        
        # Harvest new papers
        new_papers = self.monitor.daily_harvest(target_date)
        print(f"📥 Harvested {new_papers} new papers")
        
        if new_papers == 0:
            print("ℹ️  No new papers to analyze today")
            return
        
        # Analyze papers with AI
        analyzed_papers = self.analyzer.analyze_pending_papers()
        print(f"🧠 Analyzed {analyzed_papers} papers with AI")
        
        # Generate and send daily report
        report = self.notification_system.generate_daily_report(target_date)
        print(f"📊 Generated report: {report['total_flagged']} relevant papers found")
        
        # Always send email report (even if no flagged papers)
        email_sent = self.notification_system.send_daily_report(report, target_date)
        if email_sent:
            print("📧 Daily report sent via email")
        else:
            print("⚠️  Email not configured or failed to send")
        
        # Display summary
        summary = self.notification_system.get_daily_summary()
        print("\n" + "="*50)
        print("📈 DAILY SUMMARY")
        print("="*50)
        print(summary)
    
    def show_flagged_papers(self, limit=10):
        """Display flagged papers"""
        papers = self.db.get_flagged_papers(limit)
        
        if not papers:
            print("No flagged papers found.")
            return
        
        print(f"\n🔍 Showing top {len(papers)} relevant papers:\n")
        
        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper['title']}")
            print(f"   Score: {paper['relevance_score']:.2f}")
            print(f"   arXiv: https://arxiv.org/abs/{paper['id']}")
            
            # Parse authors
            authors = paper['authors']
            if isinstance(authors, str):
                try:
                    authors = json.loads(authors)
                except:
                    authors = [authors]
            
            authors_str = ', '.join(authors[:3])
            if len(authors) > 3:
                authors_str += ' et al.'
            print(f"   Authors: {authors_str}")
            
            if paper.get('summary'):
                print(f"   Summary: {paper['summary'][:100]}...")
            
            print()
    
    def search_papers(self, query, max_results=10):
        """Search for papers using arXiv API"""
        print(f"🔍 Searching for: {query}")
        papers = self.monitor.search_papers(query, max_results)
        
        if not papers:
            print("No papers found.")
            return
        
        print(f"\nFound {len(papers)} papers:\n")
        
        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper['title']}")
            print(f"   Authors: {', '.join(paper['authors'][:3])}")
            if len(paper['authors']) > 3:
                print("   et al.")
            print(f"   arXiv: https://arxiv.org/abs/{paper['id']}")
            print()
    
    def show_status(self):
        """Show system status"""
        profile = self.db.get_user_profile()
        
        print("🚀 DRADIS System Status")
        print("="*30)
        
        if profile:
            print(f"✅ User Profile: {profile['email']}")
            print(f"   Keywords: {len(profile.get('research_keywords', []))}")
            print(f"   Topics: {len(profile.get('research_topics', []))}")
        else:
            print("❌ User Profile: Not configured")
        
        # Database stats
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM papers")
                total_papers = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM papers WHERE processed = TRUE")
                processed_papers = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM paper_analysis WHERE flagged = TRUE")
                flagged_papers = cursor.fetchone()[0]
                
                print(f"📚 Total Papers: {total_papers}")
                print(f"🧠 Processed: {processed_papers}")
                print(f"🚩 Flagged: {flagged_papers}")
                
        except Exception as e:
            print(f"❌ Database Error: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description='DRADIS - Automated arXiv Research Discovery and Analysis System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dradis.py setup                    # Set up user profile manually
  python dradis.py auto-profile             # Build profile from your papers automatically
  python dradis.py harvest                  # Run daily harvest (slow, thorough)
  python dradis.py fast-harvest             # Run fast parallel harvest (2-4 hours)
  python dradis.py fast-harvest --date 2025-08-15  # Harvest specific historical date
  python dradis.py show                     # Show flagged papers
  python dradis.py search "string theory"   # Search papers
  python dradis.py status                   # Show system status
  
Development mode:
  python dradis.py --dev-mode fast-harvest # Run with verbose logging
  python dradis.py fast-harvest --date 2025-08-01 # Test with historical data
        """
    )
    
    # Global options
    parser.add_argument('--dev-mode', action='store_true',
                        help='Enable development mode with verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up user research profile')
    setup_parser.add_argument('--non-interactive', action='store_true',
                            help='Use environment variables instead of prompts')
    
    # Auto-profile command
    auto_parser = subparsers.add_parser('auto-profile', help='Build profile automatically from your papers')
    auto_parser.add_argument('--inspire-id', help='Your INSPIRE ID (e.g., INSPIRE-00123456)')
    auto_parser.add_argument('--orcid-id', help='Your ORCID ID (e.g., 0000-0000-0000-0000)')
    auto_parser.add_argument('--author-name', help='Your name for arXiv search')
    
    # Harvest command
    harvest_parser = subparsers.add_parser('harvest', help='Run daily paper harvesting')
    
    # Fast harvest command  
    fast_harvest_parser = subparsers.add_parser('fast-harvest', help='Run fast parallel paper harvesting')
    fast_harvest_parser.add_argument('--include-replacements', action='store_true',
                                    help='Include replacement papers (default: skip them)')
    fast_harvest_parser.add_argument('--date', type=str,
                                    help='Specific date to harvest (YYYY-MM-DD or YYYYMMDD format)')
    fast_harvest_parser.add_argument('--no-email', action='store_true',
                                    help='Skip sending email report')
    
    # Regular harvest command also gets the option
    harvest_parser.add_argument('--include-replacements', action='store_true',
                               help='Include replacement papers (default: skip them)')
    harvest_parser.add_argument('--date', type=str,
                               help='Specific date to harvest (YYYY-MM-DD or YYYYMMDD format)')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show flagged papers')
    show_parser.add_argument('--limit', type=int, default=10,
                           help='Number of papers to show (default: 10)')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for papers')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--max-results', type=int, default=10,
                             help='Maximum number of results (default: 10)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    # Friends management commands
    friends_parser = subparsers.add_parser('friends', help='Manage friend authors')
    friends_subparsers = friends_parser.add_subparsers(dest='friends_command', help='Friend commands')
    
    # Add friend
    add_friend_parser = friends_subparsers.add_parser('add', help='Add a friend')
    add_friend_parser.add_argument('name', help='Friend name')
    add_friend_parser.add_argument('--inspire-id', help='INSPIRE ID')
    add_friend_parser.add_argument('--orcid', help='ORCID ID')
    add_friend_parser.add_argument('--institution', help='Institution')
    add_friend_parser.add_argument('--notes', help='Notes about this friend')
    
    # Remove friend
    remove_friend_parser = friends_subparsers.add_parser('remove', help='Remove a friend')
    remove_friend_parser.add_argument('name', help='Friend name to remove')
    
    # List friends
    list_friends_parser = friends_subparsers.add_parser('list', help='List all friends')
    
    args = parser.parse_args()
    
    # Enable development mode if requested
    if args.dev_mode:
        set_dev_mode(True)
        print("🔧 Development mode enabled - verbose logging active")
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Determine if we should skip replacements (default: yes, skip them)
        skip_replacements = True
        if hasattr(args, 'include_replacements') and args.include_replacements:
            skip_replacements = False
        
        dradis = DRADIS(skip_replacements=skip_replacements)
        
        if args.command == 'setup':
            dradis.setup_user_profile(interactive=not args.non_interactive)
        
        elif args.command == 'auto-profile':
            dradis.build_automated_profile(
                inspire_id=args.inspire_id,
                orcid_id=args.orcid_id,
                author_name=args.author_name
            )
        
        elif args.command == 'harvest':
            dradis.run_daily_harvest(target_date=args.date)
        
        elif args.command == 'fast-harvest':
            dradis.run_fast_harvest(target_date=args.date, send_email=not args.no_email)
        
        elif args.command == 'show':
            dradis.show_flagged_papers(args.limit)
        
        elif args.command == 'search':
            dradis.search_papers(args.query, args.max_results)
        
        elif args.command == 'status':
            dradis.show_status()
        
        elif args.command == 'friends':
            if args.friends_command == 'add':
                dradis.friends_manager.add_friend(
                    name=args.name,
                    inspire_id=args.inspire_id,
                    orcid=args.orcid,
                    institution=args.institution,
                    notes=args.notes
                )
            elif args.friends_command == 'remove':
                dradis.friends_manager.remove_friend(args.name)
            elif args.friends_command == 'list':
                dradis.friends_manager.list_friends()
            else:
                friends_parser.print_help()
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()