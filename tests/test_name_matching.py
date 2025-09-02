#!/usr/bin/env python3
"""
Test the improved name matching logic
"""
import sys
sys.path.insert(0, 'src')

from friends_manager import FriendsManager

# Test the name matching
fm = FriendsManager('friends.yaml')

# Test cases from our actual scenario
test_cases = [
    ("Lasenby, A.N.", "Anthony Lasenby"),
    ("Hobson, M.P.", "Michael Hobson"), 
    ("Handley, W.J.", "Will Handley"),
    ("Zell, Sebastian", "Sebastian Zell"),
    ("Marzo, Carlo", "Carlo Marzo"),
    ("Barker, W.", "Will Barker"),  # Should not match (excluded)
    ("Smith, J.", "Anthony Lasenby"),  # Should not match (different person)
]

print("🧪 Testing Name Matching Logic")
print("=" * 50)

for friend_name, arxiv_name in test_cases:
    similarity = fm.name_similarity(friend_name, arxiv_name)
    match = "✅ MATCH" if similarity >= fm.config.get('name_match_threshold', 0.85) else "❌ NO MATCH"
    
    print(f"{friend_name:20} vs {arxiv_name:20} -> {similarity:.3f} {match}")
    
    # Show component extraction
    comp1 = fm.extract_name_components(friend_name)
    comp2 = fm.extract_name_components(arxiv_name)
    print(f"  {comp1}")
    print(f"  {comp2}")
    print()