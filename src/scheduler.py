"""
Scheduling and automation system for DRADIS
"""
import schedule
import time
import subprocess
import logging
from datetime import datetime
import os

from .config import DAILY_CHECK_TIME

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dradis.log'),
        logging.StreamHandler()
    ]
)

class DradisScheduler:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        
    def run_daily_harvest(self):
        """Run the daily harvest job"""
        self.logger.info("Starting scheduled daily harvest")
        try:
            # Run the DRADIS harvest command
            result = subprocess.run(
                ['python', 'dradis.py', 'harvest'],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                self.logger.info("Daily harvest completed successfully")
                self.logger.info(f"Output: {result.stdout}")
            else:
                self.logger.error(f"Daily harvest failed with return code {result.returncode}")
                self.logger.error(f"Error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.error("Daily harvest timed out after 1 hour")
        except Exception as e:
            self.logger.error(f"Error running daily harvest: {e}")
    
    def setup_schedule(self):
        """Set up the daily schedule"""
        # Schedule daily harvest
        schedule.every().day.at(DAILY_CHECK_TIME).do(self.run_daily_harvest)
        
        # Optional: Weekly summary (every Sunday at 10:00)
        schedule.every().sunday.at("10:00").do(self.generate_weekly_summary)
        
        self.logger.info(f"Scheduler configured: Daily harvest at {DAILY_CHECK_TIME}")
    
    def generate_weekly_summary(self):
        """Generate a weekly summary of findings"""
        self.logger.info("Generating weekly summary")
        # This could generate a more comprehensive weekly report
        # For now, just log that it would run
        pass
    
    def run(self):
        """Run the scheduler"""
        self.setup_schedule()
        
        self.logger.info("DRADIS Scheduler started")
        self.logger.info(f"Next harvest scheduled for: {schedule.next_run()}")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user")
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")

def main() -> None:
    """Main function for standalone scheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DRADIS Scheduler')
    parser.add_argument('--once', action='store_true',
                       help='Run harvest once and exit (for testing)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon process')
    
    args = parser.parse_args()
    
    scheduler = DradisScheduler()
    
    if args.once:
        # Run harvest once for testing
        scheduler.run_daily_harvest()
    elif args.daemon:
        # Run as daemon (would need additional daemon setup)
        print("Daemon mode not fully implemented. Use a process manager like systemd.")
        scheduler.run()
    else:
        # Normal scheduled mode
        scheduler.run()

if __name__ == '__main__':
    main()