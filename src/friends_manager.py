#!/usr/bin/env python3
"""
Friends management system for DRADIS
Handles loading friend configurations and detecting friend papers
Now uses consolidated .env configuration instead of separate YAML file
"""
import json
from typing import List, Dict, Optional, Set
from difflib import SequenceMatcher
import re
from .config import FRIENDS_DATA

class FriendsManager:
    def __init__(self) -> None:
        self.friends = []
        self.config = {}
        self.load_friends()
    
    def load_friends(self):
        """Load friends configuration from consolidated config"""
        try:
            self.friends = FRIENDS_DATA.get('friends', [])
            self.config = FRIENDS_DATA.get('metadata', {})
            
            # Set default config values
            self.config.setdefault('name_match_threshold', 0.85)
            self.config.setdefault('auto_flag_friend_papers', True)
            self.config.setdefault('separate_friend_notifications', False)
            self.config.setdefault('friend_relevance_boost', 0.3)
            
            print(f"📚 Loaded {len(self.friends)} friends from configuration")
            
        except Exception as e:
            print(f"❌ Error loading friends configuration: {e}")
            self.friends = []
            self.config = {}
    
    def normalize_name(self, name: str) -> str:
        """Normalize author name for comparison"""
        # Remove common prefixes/suffixes and normalize spacing
        name = re.sub(r'\b(Dr|Prof|Professor|PhD|Ph\.D\.)\b\.?', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name.strip())
        return name.lower()
    
    def extract_name_components(self, name: str) -> Dict:
        """Extract surname and initials from a name in various formats"""
        name = self.normalize_name(name)
        
        # Handle "Surname, F.I." format (INSPIRE format)
        if ',' in name:
            parts = name.split(',', 1)
            surname = parts[0].strip()
            given_part = parts[1].strip()
            
            # Extract initials from "F.I." or "F. I." or "Frederick Ian"
            initials = []
            for part in given_part.replace('.', ' ').split():
                if part.strip():
                    initials.append(part.strip()[0])
        
        # Handle "Firstname Middlename Surname" format (arXiv format)  
        else:
            parts = name.split()
            if len(parts) >= 2:
                surname = parts[-1]  # Last part is surname
                initials = [part[0] for part in parts[:-1] if part]  # First letters of all other parts
            else:
                surname = name
                initials = []
        
        return {
            'surname': surname,
            'initials': initials,
            'full_name': name
        }
    
    def name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using smart matching"""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        # Direct match
        if norm1 == norm2:
            return 1.0
        
        # Extract components from both names
        comp1 = self.extract_name_components(name1)
        comp2 = self.extract_name_components(name2)
        
        # Must have matching surnames
        surname_match = SequenceMatcher(None, comp1['surname'], comp2['surname']).ratio()
        if surname_match < 0.85:  # Surnames must be very similar
            return 0.0
        
        # Check initial matching
        initials1 = set(comp1['initials'])
        initials2 = set(comp2['initials'])
        
        if initials1 and initials2:
            # At least one initial must match
            if initials1 & initials2:  # Intersection - common initials
                # Strong match: same surname + matching initials
                return 0.95 if surname_match > 0.95 else 0.90
            else:
                # Surname matches but no common initials
                return 0.3
        
        # Fallback to full name fuzzy matching
        full_match = SequenceMatcher(None, norm1, norm2).ratio()
        
        # If surnames match well but we can't compare initials, be more generous
        if surname_match > 0.9:
            return max(full_match, 0.7)
        
        return full_match
    
    def detect_friend_authors(self, paper: Dict) -> List[Dict]:
        """Detect which authors in a paper are friends"""
        if not paper.get('authors'):
            return []
        
        paper_authors = paper['authors']
        if isinstance(paper_authors, str):
            try:
                paper_authors = json.loads(paper_authors)
            except:
                paper_authors = [paper_authors]
        
        detected_friends = []
        threshold = self.config.get('name_match_threshold', 0.85)
        
        for friend in self.friends:
            friend_name = friend.get('name', '')
            if not friend_name:
                continue
            
            # Check each author in the paper
            for author in paper_authors:
                similarity = self.name_similarity(friend_name, author)
                
                if similarity >= threshold:
                    detected_friends.append({
                        'friend': friend,
                        'author_name': author,
                        'similarity': similarity
                    })
                    break  # Don't match the same friend multiple times
        
        return detected_friends
    
    def is_friend_paper(self, paper: Dict) -> bool:
        """Check if paper has any friend authors"""
        return len(self.detect_friend_authors(paper)) > 0
    
    def get_friend_boost(self, paper: Dict) -> float:
        """Get relevance boost for friend papers"""
        if self.is_friend_paper(paper):
            return self.config.get('friend_relevance_boost', 0.3)
        return 0.0
    
    def add_friend(self, name: str, inspire_id: str = None, orcid: str = None, 
                   institution: str = None, notes: str = None):
        """Add a new friend to the configuration"""
        friend = {
            'name': name,
            'inspire_id': inspire_id,
            'orcid': orcid,
            'institution': institution,
            'notes': notes
        }
        
        # Remove None values
        friend = {k: v for k, v in friend.items() if v is not None}
        
        self.friends.append(friend)
        self.save_friends()
        print(f"✅ Added friend: {name}")
    
    def remove_friend(self, name: str) -> bool:
        """Remove a friend by name"""
        for i, friend in enumerate(self.friends):
            if self.name_similarity(friend.get('name', ''), name) > 0.9:
                removed_friend = self.friends.pop(i)
                self.save_friends()
                print(f"✅ Removed friend: {removed_friend.get('name')}")
                return True
        
        print(f"❌ Friend not found: {name}")
        return False
    
    def list_friends(self):
        """List all configured friends"""
        if not self.friends:
            print("No friends configured.")
            return
        
        print("📚 Configured Friends:")
        print("=" * 50)
        
        for i, friend in enumerate(self.friends, 1):
            print(f"{i}. {friend.get('name', 'Unknown')}")
            if friend.get('institution'):
                print(f"   Institution: {friend['institution']}")
            if friend.get('inspire_id'):
                print(f"   INSPIRE ID: {friend['inspire_id']}")
            if friend.get('orcid'):
                print(f"   ORCID: {friend['orcid']}")
            if friend.get('notes'):
                print(f"   Notes: {friend['notes']}")
            print()
    
    def save_friends(self):
        """Save friends configuration back to YAML file"""
        try:
            data = {
                'friends': self.friends,
                'config': self.config
            }
            
            with open(self.friends_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
        except Exception as e:
            print(f"❌ Error saving friends configuration: {e}")
    
    def get_friend_papers_summary(self, papers: List[Dict]) -> Dict:
        """Get summary of friend papers from a list"""
        friend_papers = []
        friend_names = set()
        
        for paper in papers:
            detected_friends = self.detect_friend_authors(paper)
            if detected_friends:
                friend_paper = paper.copy()
                friend_paper['detected_friends'] = detected_friends
                friend_papers.append(friend_paper)
                
                for detection in detected_friends:
                    friend_names.add(detection['friend']['name'])
        
        return {
            'friend_papers': friend_papers,
            'friend_count': len(friend_names),
            'paper_count': len(friend_papers),
            'friend_names': list(friend_names)
        }


if __name__ == '__main__':
    # Test the friends manager
    fm = FriendsManager()
    fm.list_friends()