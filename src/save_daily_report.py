#!/usr/bin/env python3
"""
Save daily DRADIS report to HTML file
"""
from .notification_system import NotificationSystem
from datetime import datetime

def save_daily_report() -> None:
    """Generate and save today's report to HTML file"""
    notifier = NotificationSystem()
    report = notifier.generate_daily_report()
    
    if report['total_flagged'] == 0:
        print("No flagged papers to report today")
        return
    
    # Generate HTML content
    html_content = notifier.format_daily_email(report)
    
    # Save to file with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d')
    filename = f'dradis_report_{timestamp}.html'
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Daily report saved to: {filename}")
    print(f"📊 Contains {report['total_flagged']} flagged papers")
    print(f"🔗 Open in browser: file://{filename}")

if __name__ == '__main__':
    save_daily_report()