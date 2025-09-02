#!/usr/bin/env python3
"""
DRADIS - Automated arXiv Research Discovery and Analysis System
Entry point script
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.dradis import main

if __name__ == '__main__':
    main()