# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DRADIS is an automated research discovery and analysis system designed for theoretical physicists. The system monitors arXiv announcements in hep-th, gr-qc, and astro-ph.CO categories, analyzes papers using AI models (particularly Gemini), and flags papers relevant to the user's research by comparing against their existing work.

## Architecture

### Core Components
- **arXiv Monitor**: Daily fetching of new papers from target categories
- **Paper Processor**: Download and parse PDF content using AI models
- **Relevance Analyzer**: Compare papers against user's research profile
- **Notification System**: Flag and potentially email authors about relevant papers
- **User Profile**: Store researcher's ORCID, INSPIRE ID, Google Scholar profile, and research focus

### Data Flow
1. Daily arXiv RSS/API monitoring
2. Paper content extraction and AI analysis
3. Relevance scoring against user's research profile
4. Automated flagging and optional author contact

### Key Considerations
- Integration with arXiv API for paper metadata and PDFs
- AI model integration (Gemini) for content analysis
- Research profile management and similarity algorithms
- Rate limiting and ethical considerations for author contact
- Storage of processed papers and analysis results

## Development Guidelines

### Configuration
- All configuration is managed through environment variables in `.env`
- Copy `.env.template` to `.env` and fill in your details
- Never commit `.env` or any file containing secrets

### Testing
- Run tests with `./run_tests.sh` or `python -m pytest`
- Tests are located in the `tests/` directory
- All functions should have comprehensive test coverage

### Code Style
- Type hints are used throughout the codebase
- Follow PEP 8 style guidelines
- Functions should have clear docstrings
- Keep functions focused and single-purpose

### Deployment
- See `templates/` directory for deployment script templates
- Customize deployment scripts for your specific infrastructure
- The system can run as a systemd service or via cron

## Common Tasks

### Initial Setup
```bash
# Create virtual environment and install dependencies
./scripts/activate.sh

# Set up configuration
cp .env.template .env
# Edit .env with your details

# Initialize database and profile
python dradis.py setup
python dradis.py auto-profile
```

### Daily Operations
```bash
# Run paper harvest
python dradis.py fast-harvest

# Check system status
python dradis.py status

# Monitor database in real-time
./scripts/monitor.sh
```

### Maintenance
```bash
# View logs
./scripts/log_viewer.py

# Search for papers
python dradis.py search "quantum gravity"

# Manage friends/collaborators
python dradis.py friends
```