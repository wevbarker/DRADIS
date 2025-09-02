#!/bin/bash
# DRADIS Simple Monitor

echo "🔄 DRADIS Monitor - Updates every 10 seconds (Ctrl+C to stop)"
echo ""

while true; do
    # Get stats in one line
    STATS=$(sqlite3 dradis.db "SELECT 'Progress: ' || COUNT(CASE WHEN processed = 1 THEN 1 END) || '/' || COUNT(*) || ' (' || ROUND(COUNT(CASE WHEN processed = 1 THEN 1 END) * 100.0 / COUNT(*), 1) || '%) | Flagged: ' || (SELECT COUNT(*) FROM paper_analysis WHERE flagged = 1) || ' | Max score: ' || COALESCE((SELECT ROUND(MAX(relevance_score), 2) FROM paper_analysis), '0.00')" FROM papers 2>/dev/null || echo "Database not accessible")
    
    # Print with carriage return to update same line
    echo -ne "\r$STATS                    "
    
    sleep 10
done