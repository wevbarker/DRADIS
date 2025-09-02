#!/usr/bin/env python3
"""
Morning scheduler for DRADIS
Runs fast harvest automatically in early morning hours
"""
import schedule
import time
import subprocess
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dradis_morning.log'),
        logging.StreamHandler()
    ]
)

def run_morning_harvest() -> None:
    """Run the morning fast harvest"""
    logger = logging.getLogger(__name__)
    logger.info("Starting morning DRADIS harvest")
    
    try:
        # Run fast harvest (skip replacements by default)
        result = subprocess.run(
            ['python', 'dradis.py', 'fast-harvest'],
            capture_output=True,
            text=True,
            timeout=14400  # 4 hour timeout
        )
        
        if result.returncode == 0:
            logger.info("Morning harvest completed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"Morning harvest failed with return code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("Morning harvest timed out after 4 hours")
    except Exception as e:
        logger.error(f"Error running morning harvest: {e}")

def main() -> None:
    """Main scheduler function"""
    logger = logging.getLogger(__name__)
    
    # Schedule morning harvest
    # arXiv announcements happen ~8PM Eastern = 1AM UK time
    # Schedule for 2AM UK time to ensure papers are available
    schedule.every().day.at("02:00").do(run_morning_harvest)
    
    logger.info("Morning DRADIS scheduler started")
    logger.info("Scheduled: Fast harvest daily at 02:00 UK time")
    logger.info(f"Next run: {schedule.next_run()}")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(300)  # Check every 5 minutes
            
    except KeyboardInterrupt:
        logger.info("Morning scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

if __name__ == '__main__':
    main()