#!/bin/bash
# Run DRADIS test suite
echo "🧪 Running DRADIS Test Suite"
echo "============================="

echo "📋 Running Unit Tests..."
PYTHONPATH=. python -m pytest tests/test_config.py tests/test_database.py tests/test_friends_manager.py tests/test_relevance_engine.py -v

echo ""
echo "🔗 Running Integration Tests..."
echo "Note: Integration tests require proper configuration (.env file)"
echo "- test_mutt.py: Email functionality test"
echo "- test_name_matching.py: Friend name matching test"

echo ""
echo "✅ Test suite complete!"
echo ""
echo "To run integration tests manually:"
echo "  python tests/test_mutt.py"
echo "  python tests/test_name_matching.py"