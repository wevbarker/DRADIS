#!/bin/bash
# Convenience script to activate DRADIS environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if venv exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "🔧 Virtual environment not found. Creating it now..."
    python -m venv "$SCRIPT_DIR/venv"
    
    # Activate and install dependencies
    source "$SCRIPT_DIR/venv/bin/activate"
    
    echo "📦 Installing Python packages..."
    pip install google-generativeai arxiv schedule
    
    echo "✅ Virtual environment created and packages installed!"
else
    # Just activate
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "🚀 DRADIS environment activated!"
fi

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "   Copy .env.example to .env and add your API keys:"
    echo "   cp .env.example .env"
fi

# Show status
echo ""
echo "📍 Working directory: $SCRIPT_DIR"
echo "🐍 Python: $(which python)"
echo ""
echo "Quick commands:"
echo "  python dradis.py setup     - Set up your profile"
echo "  python dradis.py harvest   - Run daily harvest"
echo "  python dradis.py show      - Show flagged papers"
echo "  python dradis.py status    - Check system status"
echo "  deactivate                 - Exit virtual environment"
echo ""