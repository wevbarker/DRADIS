"""
Paper analysis module using Gemini AI for DRADIS
"""
import google.generativeai as genai
import requests
import pypdf as PyPDF2
from io import BytesIO
from typing import Dict, List, Optional
import time
import json

from .config import GEMINI_API_KEY, RATE_LIMIT_DELAY
from .database import DradisDB

class PaperAnalyzer:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')  # Use quota-friendly model
        self.db = DradisDB()
        
    def extract_pdf_text(self, pdf_url: str) -> Optional[str]:
        """Extract text content from PDF"""
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            pdf_file = BytesIO(response.content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            # Extract text from first 10 pages (to avoid token limits)
            for page_num in range(min(10, len(reader.pages))):
                page = reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            return text.strip()
            
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return None
    
    def analyze_paper_relevance(self, paper: Dict, user_profile: Dict) -> Dict:
        """Analyze a paper's relevance to user's research using Gemini"""
        try:
            # Prepare context about user's research
            user_context = self._build_user_context(user_profile)
            
            # Get paper content (abstract + PDF if available)
            paper_content = self._get_paper_content(paper)
            
            # Construct analysis prompt
            prompt = f"""
            You are an expert theoretical physicist analyzing research papers for relevance.
            
            USER RESEARCH PROFILE:
            {user_context}
            
            PAPER TO ANALYZE:
            Title: {paper['title']}
            Authors: {', '.join(paper['authors']) if isinstance(paper['authors'], list) else paper['authors']}
            Categories: {', '.join(paper['categories']) if isinstance(paper['categories'], list) else paper['categories']}
            Abstract: {paper['abstract']}
            
            {f"Full paper content (excerpt): {paper_content[:8000]}..." if paper_content else ""}
            
            ANALYSIS TASK:
            Analyze this paper's relevance to the user's research. Provide:
            
            1. RELEVANCE SCORE: Rate from 0.0 to 1.0 how relevant this paper is
            2. KEY CONCEPTS: List main physics concepts/topics in the paper
            3. RELEVANCE REASONING: Explain why this paper is/isn't relevant
            4. COLLABORATION POTENTIAL: Could this work complement the user's research?
            5. CITATION OPPORTUNITY: Should the user contact authors about citing their work?
            6. SUMMARY: Brief technical summary of the paper's main contributions
            
            Respond in JSON format:
            {{
                "relevance_score": 0.0-1.0,
                "key_concepts": ["concept1", "concept2", ...],
                "relevance_reasoning": "explanation",
                "collaboration_potential": "high/medium/low",
                "citation_opportunity": "yes/no/maybe",
                "summary": "technical summary",
                "flagged": true/false
            }}
            """
            
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            # Parse response
            try:
                analysis = json.loads(response.text)
                # Ensure flagged field is set based on relevance score
                if 'flagged' not in analysis:
                    analysis['flagged'] = analysis.get('relevance_score', 0) >= 0.7
                return analysis
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                return self._parse_fallback_response(response.text)
            
        except Exception as e:
            print(f"Error analyzing paper {paper['id']}: {e}")
            return {
                'relevance_score': 0.0,
                'key_concepts': [],
                'relevance_reasoning': f'Analysis failed: {str(e)}',
                'collaboration_potential': 'unknown',
                'citation_opportunity': 'unknown',
                'summary': 'Analysis failed',
                'flagged': False
            }
    
    def _build_user_context(self, user_profile: Dict) -> str:
        """Build context string about user's research"""
        context_parts = []
        
        if user_profile.get('research_keywords'):
            context_parts.append(f"Research Keywords: {', '.join(user_profile['research_keywords'])}")
        
        if user_profile.get('research_topics'):
            context_parts.append(f"Research Topics: {', '.join(user_profile['research_topics'])}")
        
        if user_profile.get('previous_papers'):
            context_parts.append(f"Previous Papers: {user_profile['previous_papers'][:3]}")  # Limit to first 3
        
        return "\n".join(context_parts) if context_parts else "Limited profile information available"
    
    def _get_paper_content(self, paper: Dict) -> Optional[str]:
        """Get full paper content if PDF is available"""
        if paper.get('pdf_url'):
            return self.extract_pdf_text(paper['pdf_url'])
        return None
    
    def _parse_fallback_response(self, response_text: str) -> Dict:
        """Fallback parsing when JSON parsing fails"""
        # Simple regex-based parsing as fallback
        import re
        
        score_match = re.search(r'relevance_score["\s:]*([0-9.]+)', response_text, re.IGNORECASE)
        relevance_score = float(score_match.group(1)) if score_match else 0.0
        
        concepts_match = re.search(r'key_concepts["\s:]*\[(.*?)\]', response_text, re.IGNORECASE | re.DOTALL)
        key_concepts = []
        if concepts_match:
            concepts_text = concepts_match.group(1)
            key_concepts = [c.strip(' "\'') for c in concepts_text.split(',')]
        
        return {
            'relevance_score': relevance_score,
            'key_concepts': key_concepts,
            'relevance_reasoning': 'Parsed from malformed response',
            'collaboration_potential': 'unknown',
            'citation_opportunity': 'unknown',
            'summary': response_text[:500] + '...' if len(response_text) > 500 else response_text,
            'flagged': relevance_score >= 0.7
        }
    
    def analyze_pending_papers(self) -> int:
        """Analyze all unprocessed papers in the database"""
        # Get user profile
        user_profile = self.db.get_user_profile()
        if not user_profile:
            print("No user profile found. Please set up user profile first.")
            return 0
        
        # Get unprocessed papers
        papers = self.db.get_unprocessed_papers()
        print(f"Found {len(papers)} papers to analyze")
        
        analyzed_count = 0
        for paper in papers:
            try:
                print(f"Analyzing paper: {paper['title'][:50]}...")
                
                # Analyze paper
                analysis = self.analyze_paper_relevance(paper, user_profile)
                
                # Save analysis
                self.db.save_paper_analysis(paper['id'], analysis)
                self.db.mark_paper_processed(paper['id'])
                
                analyzed_count += 1
                
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)
                
            except Exception as e:
                print(f"Error analyzing paper {paper['id']}: {e}")
                continue
        
        print(f"Analyzed {analyzed_count} papers")
        return analyzed_count
    
    def get_paper_summary(self, paper_id: str) -> Optional[str]:
        """Get a detailed summary of a specific paper"""
        try:
            # This would fetch the paper and generate a detailed summary
            # Implementation would be similar to analyze_paper_relevance
            # but focused on generating a comprehensive summary
            pass
        except Exception as e:
            print(f"Error getting paper summary: {e}")
            return None