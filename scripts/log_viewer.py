#!/usr/bin/env python3
"""
DRADIS Log Viewer - Development tool for parsing and analyzing DRADIS logs
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import json

class LogEntry:
    """Represents a single log entry"""
    
    def __init__(self, line: str):
        self.raw = line.strip()
        self.timestamp = None
        self.level = None
        self.module = None
        self.function = None
        self.message = None
        self.extras = {}
        
        self._parse()
    
    def _parse(self):
        """Parse log line into components"""
        # Pattern: 2025-08-27 14:30:45 | INFO     | dradis          | run_fast_harvest | Message | key=value
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d{3})? \| (\w+)\s+ \| ([^|]+?) \| ([^|]+?) \| (.+)'
        match = re.match(pattern, self.raw)
        
        if match:
            self.timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            self.level = match.group(2).strip()
            self.module = match.group(3).strip()
            self.function = match.group(4).strip()
            
            # Parse message and extras
            rest = match.group(5)
            parts = rest.split(' | ')
            self.message = parts[0]
            
            # Parse key=value pairs
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    self.extras[key] = value
    
    def __str__(self):
        return f"[{self.timestamp}] {self.level}: {self.message}"

class LogViewer:
    """Log viewer and analyzer"""
    
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
    
    def get_log_files(self) -> List[Path]:
        """Get all log files, sorted by date"""
        if not self.log_dir.exists():
            return []
        
        log_files = list(self.log_dir.glob("*.log"))
        return sorted(log_files, key=lambda f: f.stat().st_mtime, reverse=True)
    
    def load_entries(self, log_file: Path, 
                    level_filter: Optional[str] = None,
                    since: Optional[datetime] = None,
                    operation_filter: Optional[str] = None) -> List[LogEntry]:
        """Load and filter log entries"""
        entries = []
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entry = LogEntry(line)
                        
                        # Apply filters
                        if level_filter and entry.level != level_filter.upper():
                            continue
                        
                        if since and entry.timestamp and entry.timestamp < since:
                            continue
                        
                        if operation_filter and operation_filter.lower() not in entry.message.lower():
                            continue
                        
                        entries.append(entry)
        
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
        
        return entries
    
    def show_operations(self, entries: List[LogEntry]):
        """Show operation flow"""
        print("📋 Operation Flow:")
        print("=" * 60)
        
        operations = {}
        
        for entry in entries:
            if '[START]' in entry.message:
                op_name = entry.message.replace('[START]', '').strip()
                operations[op_name] = {'start': entry, 'end': None, 'progress': []}
            elif '[SUCCESS]' in entry.message or '[FAILED]' in entry.message:
                op_name = entry.message.replace('[SUCCESS]', '').replace('[FAILED]', '').strip()
                if op_name in operations:
                    operations[op_name]['end'] = entry
            elif '[PROGRESS]' in entry.message:
                # Extract operation name from progress message
                match = re.match(r'\[PROGRESS\] ([^:]+):', entry.message)
                if match:
                    op_name = match.group(1)
                    if op_name in operations:
                        operations[op_name]['progress'].append(entry)
        
        for op_name, data in operations.items():
            start = data['start']
            end = data['end']
            
            status_icon = "✅" if end and '[SUCCESS]' in end.message else "❌" if end else "⏳"
            print(f"{status_icon} {op_name}")
            
            if start:
                print(f"    Started: {start.timestamp}")
                
            if data['progress']:
                latest_progress = data['progress'][-1]
                print(f"    Progress: {latest_progress.message}")
                
            if end:
                duration = (end.timestamp - start.timestamp).total_seconds() if start else 0
                print(f"    Completed: {end.timestamp} ({duration:.1f}s)")
            
            print()
    
    def show_errors(self, entries: List[LogEntry]):
        """Show error entries"""
        errors = [e for e in entries if e.level in ['ERROR', 'CRITICAL']]
        
        if not errors:
            print("✅ No errors found")
            return
        
        print(f"❌ Found {len(errors)} error(s):")
        print("=" * 60)
        
        for error in errors:
            print(f"[{error.timestamp}] {error.module}.{error.function}")
            print(f"    {error.message}")
            if error.extras:
                for key, value in error.extras.items():
                    print(f"    {key}: {value}")
            print()
    
    def show_summary(self, entries: List[LogEntry]):
        """Show log summary"""
        if not entries:
            print("No log entries found")
            return
        
        # Count by level
        level_counts = {}
        for entry in entries:
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
        
        # Time range
        timestamps = [e.timestamp for e in entries if e.timestamp]
        start_time = min(timestamps) if timestamps else None
        end_time = max(timestamps) if timestamps else None
        
        print("📊 Log Summary:")
        print("=" * 40)
        print(f"Entries: {len(entries)}")
        if start_time and end_time:
            print(f"Time Range: {start_time} to {end_time}")
            print(f"Duration: {end_time - start_time}")
        
        print(f"Log Levels:")
        for level, count in sorted(level_counts.items()):
            icon = {"DEBUG": "🔍", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "💥"}.get(level, "📝")
            print(f"  {icon} {level}: {count}")
        
        print()
    
    def tail(self, log_file: Path, lines: int = 20):
        """Show last N lines of log file"""
        print(f"📄 Last {lines} lines of {log_file.name}:")
        print("=" * 60)
        
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                
            for line in all_lines[-lines:]:
                print(line.rstrip())
                
        except Exception as e:
            print(f"Error reading {log_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description='DRADIS Log Viewer')
    parser.add_argument('--log-dir', type=Path, default=Path('logs'),
                        help='Log directory path')
    parser.add_argument('--file', type=str, help='Specific log file to view')
    parser.add_argument('--level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Filter by log level')
    parser.add_argument('--since', type=str, help='Show logs since time (YYYY-MM-DD HH:MM)')
    parser.add_argument('--operation', type=str, help='Filter by operation name')
    parser.add_argument('--tail', type=int, default=0, help='Show last N lines')
    parser.add_argument('--errors', action='store_true', help='Show only errors')
    parser.add_argument('--operations', action='store_true', help='Show operation flow')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    viewer = LogViewer(args.log_dir)
    
    # Determine log file to use
    if args.file:
        log_file = args.log_dir / args.file
        if not log_file.exists():
            print(f"Log file not found: {log_file}")
            return 1
    else:
        log_files = viewer.get_log_files()
        if not log_files:
            print(f"No log files found in {args.log_dir}")
            return 1
        log_file = log_files[0]  # Most recent
    
    print(f"📋 Viewing: {log_file}")
    
    # Handle tail mode
    if args.tail:
        viewer.tail(log_file, args.tail)
        return 0
    
    # Parse since time
    since = None
    if args.since:
        try:
            since = datetime.strptime(args.since, '%Y-%m-%d %H:%M')
        except ValueError:
            print("Invalid --since format. Use: YYYY-MM-DD HH:MM")
            return 1
    
    # Load entries
    entries = viewer.load_entries(log_file, args.level, since, args.operation)
    
    if args.summary:
        viewer.show_summary(entries)
    elif args.errors:
        viewer.show_errors(entries)
    elif args.operations:
        viewer.show_operations(entries)
    else:
        viewer.show_summary(entries)
        print()
        viewer.show_operations(entries)
        if any(e.level in ['ERROR', 'CRITICAL'] for e in entries):
            viewer.show_errors(entries)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())