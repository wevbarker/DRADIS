#!/bin/bash
# DRADIS Live Monitor Script

# Function to display stats
show_stats() {
    # Get processing stats
    TOTAL=$(sqlite3 dradis.db "SELECT COUNT(*) FROM papers" 2>/dev/null || echo "0")
    PROCESSED=$(sqlite3 dradis.db "SELECT COUNT(*) FROM papers WHERE processed = 1" 2>/dev/null || echo "0")
    
    if [ "$TOTAL" -gt 0 ]; then
        PERCENT=$(echo "scale=1; $PROCESSED * 100 / $TOTAL" | bc)
    else
        PERCENT="0.0"
    fi
    
    # Get flagged papers
    FLAGGED=$(sqlite3 dradis.db "SELECT COUNT(*) FROM paper_analysis WHERE flagged = 1" 2>/dev/null || echo "0")
    
    # Get avg relevance
    AVG_SCORE=$(sqlite3 dradis.db "SELECT printf('%.3f', AVG(relevance_score)) FROM paper_analysis" 2>/dev/null || echo "0.000")
    
    # Get max relevance 
    MAX_SCORE=$(sqlite3 dradis.db "SELECT printf('%.3f', MAX(relevance_score)) FROM paper_analysis" 2>/dev/null || echo "0.000")
    
    # Clear screen and show header
    clear
    echo "🔄 DRADIS Live Monitor - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "================================================"
    echo ""
    echo "📊 Progress: $PROCESSED / $TOTAL papers (${PERCENT}%)"
    echo "🚩 Flagged: $FLAGGED papers"
    echo "📈 Avg Score: $AVG_SCORE"
    echo "🎯 Max Score: $MAX_SCORE"
    echo ""
    echo "Recent papers processed:"
    echo "------------------------"
    sqlite3 dradis.db "SELECT printf('  %.55s... (%.2f)', p.title, pa.relevance_score) FROM papers p JOIN paper_analysis pa ON p.id = pa.paper_id ORDER BY pa.analysis_date DESC LIMIT 3" 2>/dev/null || echo "  No analyses yet"
    echo ""
    echo "Press Ctrl+C to stop"
}

# Trap Ctrl+C to exit cleanly
trap 'echo -e "\n\n👋 Monitor stopped"; exit 0' INT

# Initial display
show_stats

# Main loop
while true; do
    sleep 30
    show_stats
done