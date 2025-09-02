"""
Relevance scoring and matching algorithm for DRADIS
"""
from typing import Dict, List, Tuple
import numpy as np
from collections import Counter
import re
import json
from datetime import datetime

from .database import DradisDB
from .friends_manager import FriendsManager

class RelevanceEngine:
    def __init__(self) -> None:
        self.db = DradisDB()
        self.friends_manager = FriendsManager()
        
        # Physics topic weights for theoretical physics
        self.topic_weights = {
            'string theory': 1.0,
            'quantum field theory': 1.0,
            'general relativity': 1.0,
            'cosmology': 1.0,
            'black holes': 0.9,
            'supersymmetry': 0.9,
            'extra dimensions': 0.8,
            'quantum gravity': 1.0,
            'holographic principle': 0.9,
            'conformal field theory': 0.9,
            'gauge theory': 0.8,
            'dark matter': 0.7,
            'dark energy': 0.7,
            'inflation': 0.8,
            'AdS/CFT': 0.9,
            'supergravity': 0.8,
            'M-theory': 0.9,
            'braneworld': 0.7
        }
    
    def calculate_keyword_similarity(self, paper: Dict, user_profile: Dict) -> float:
        """Calculate keyword-based similarity score"""
        if not user_profile.get('research_keywords'):
            return 0.0
        
        user_keywords = [kw.lower() for kw in user_profile['research_keywords']]
        
        # Combine paper title and abstract for keyword matching
        paper_text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
        
        # Simple keyword matching with weights
        matches = 0
        total_weight = 0
        
        for keyword in user_keywords:
            weight = self.topic_weights.get(keyword, 0.5)
            total_weight += weight
            
            if keyword in paper_text:
                matches += weight
        
        return matches / total_weight if total_weight > 0 else 0.0
    
    def calculate_category_similarity(self, paper: Dict, user_profile: Dict) -> float:
        """Calculate category-based similarity score"""
        paper_categories = paper.get('categories', [])
        if isinstance(paper_categories, str):
            paper_categories = json.loads(paper_categories)
        
        # Define category mappings and weights
        category_mapping = {
            'hep-th': ['string theory', 'quantum field theory', 'supersymmetry', 'gauge theory'],
            'gr-qc': ['general relativity', 'quantum gravity', 'black holes', 'cosmology'],
            'astro-ph.CO': ['cosmology', 'dark matter', 'dark energy', 'inflation'],
            'hep-ph': ['particle physics', 'phenomenology'],
            'cond-mat': ['condensed matter', 'statistical mechanics'],
            'math-ph': ['mathematical physics']
        }
        
        user_keywords = [kw.lower() for kw in user_profile.get('research_keywords', [])]
        
        score = 0.0
        for category in paper_categories:
            if category in category_mapping:
                category_topics = category_mapping[category]
                for topic in category_topics:
                    if any(topic in keyword or keyword in topic for keyword in user_keywords):
                        score += 0.3  # Base category match score
        
        return min(score, 1.0)  # Cap at 1.0
    
    def calculate_author_similarity(self, paper: Dict, user_profile: Dict) -> float:
        """Calculate author-based similarity (collaboration networks)"""
        # This is a placeholder for more sophisticated author network analysis
        # Could be enhanced with INSPIRE/ORCID data
        return 0.0
    
    def calculate_citation_potential(self, paper: Dict, user_profile: Dict) -> float:
        """Calculate potential for citing user's work"""
        user_papers = user_profile.get('previous_papers', [])
        if not user_papers:
            return 0.0
        
        paper_text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
        
        # Look for overlapping concepts with user's previous work
        overlap_score = 0.0
        
        # This is simplified - in practice, would analyze user's paper abstracts/titles
        for user_paper in user_papers[:5]:  # Limit to recent papers
            if isinstance(user_paper, dict):
                user_paper_text = (user_paper.get('title', '') + ' ' + 
                                 user_paper.get('abstract', '')).lower()
                
                # Simple word overlap calculation
                paper_words = set(re.findall(r'\w+', paper_text))
                user_words = set(re.findall(r'\w+', user_paper_text))
                
                if len(user_words) > 0:
                    overlap = len(paper_words & user_words) / len(user_words)
                    overlap_score = max(overlap_score, overlap)
        
        return min(overlap_score, 1.0)
    
    def calculate_recency_score(self, paper: Dict) -> float:
        """Calculate recency score (newer papers get higher scores)"""
        try:
            published_date = datetime.fromisoformat(paper.get('published', '').replace('Z', '+00:00'))
            days_old = (datetime.now(published_date.tzinfo) - published_date).days
            
            # Exponential decay: papers lose relevance over time
            return np.exp(-days_old / 30.0)  # Half-life of ~20 days
            
        except:
            return 0.5  # Default for unparseable dates
    
    def calculate_composite_score(self, paper: Dict, user_profile: Dict, 
                                gemini_analysis: Dict = None) -> Dict:
        """Calculate composite relevance score using multiple factors"""
        
        # Base similarity scores
        keyword_sim = self.calculate_keyword_similarity(paper, user_profile)
        category_sim = self.calculate_category_similarity(paper, user_profile)
        author_sim = self.calculate_author_similarity(paper, user_profile)
        citation_potential = self.calculate_citation_potential(paper, user_profile)
        recency = self.calculate_recency_score(paper)
        
        # Weights for different factors
        weights = {
            'keyword': 0.3,
            'category': 0.2,
            'author': 0.1,
            'citation': 0.2,
            'recency': 0.1,
            'ai_analysis': 0.1
        }
        
        # Include AI analysis if available
        ai_score = 0.0
        if gemini_analysis and 'relevance_score' in gemini_analysis:
            ai_score = gemini_analysis['relevance_score']
            # Boost weight of AI analysis if it's confident
            if ai_score > 0.8 or ai_score < 0.2:
                weights['ai_analysis'] = 0.3
                weights = {k: v * 0.875 if k != 'ai_analysis' else v for k, v in weights.items()}
        
        # Calculate weighted composite score
        composite_score = (
            weights['keyword'] * keyword_sim +
            weights['category'] * category_sim +
            weights['author'] * author_sim +
            weights['citation'] * citation_potential +
            weights['recency'] * recency +
            weights['ai_analysis'] * ai_score
        )
        
        # Apply friend boost if this paper is by a friend
        friend_boost = self.friends_manager.get_friend_boost(paper)
        composite_score = min(composite_score + friend_boost, 1.0)
        
        return {
            'composite_score': composite_score,
            'keyword_similarity': keyword_sim,
            'category_similarity': category_sim,
            'author_similarity': author_sim,
            'citation_potential': citation_potential,
            'recency_score': recency,
            'ai_analysis_score': ai_score,
            'friend_boost': friend_boost,
            'is_friend_paper': friend_boost > 0,
            'flagged': composite_score >= 0.6  # Lower threshold than AI-only
        }
    
    def rank_papers(self, papers: List[Dict], user_profile: Dict) -> List[Tuple[Dict, float]]:
        """Rank papers by relevance score"""
        scored_papers = []
        
        for paper in papers:
            # Get any existing AI analysis
            analysis = None  # Would fetch from database if available
            
            scores = self.calculate_composite_score(paper, user_profile, analysis)
            scored_papers.append((paper, scores['composite_score'], scores))
        
        # Sort by score (highest first)
        scored_papers.sort(key=lambda x: x[1], reverse=True)
        
        return scored_papers
    
    def update_user_feedback(self, paper_id: str, user_rating: float, feedback: str = None):
        """Update relevance model based on user feedback"""
        # This would be used for machine learning improvements
        # Store user ratings and feedback to improve the model over time
        pass
    
    def get_trending_topics(self, days: int = 7) -> List[Dict]:
        """Analyze trending topics in recent papers"""
        # This would analyze recent papers to identify trending research areas
        pass