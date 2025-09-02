"""
Automated profile builder for DRADIS
Crawls author's papers from INSPIRE, ORCID, and arXiv to build research profile
"""
import requests
import time
import json
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import re

import google.generativeai as genai
from .config import GEMINI_API_KEY, RATE_LIMIT_DELAY
from .database import DradisDB

class ProfileBuilder:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY required for profile synthesis")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')  # Use faster, quota-friendly model
        self.db = DradisDB()
        
        # API endpoints
        self.inspire_base = "https://inspirehep.net/api/literature"
        self.orcid_base = "https://pub.orcid.org/v3.0"
        self.arxiv_base = "http://export.arxiv.org/api/query"
        
        # Rate limiting
        self.last_request = {}
    
    def _rate_limit(self, api_name: str) -> None:
        """Rate limiting for different APIs"""
        limits = {
            'inspire': 1.0,  # 15 requests per 5 seconds = ~3 seconds between
            'orcid': 0.5,    # More lenient
            'arxiv': 2.0,    # Conservative for arXiv
            'gemini': 1.0    # Rate limit Gemini calls
        }
        
        if api_name in self.last_request:
            elapsed = time.time() - self.last_request[api_name]
            wait_time = limits.get(api_name, 1.0) - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
        
        self.last_request[api_name] = time.time()
    
    def _get_inspire_bai(self, inspire_id: str) -> Optional[str]:
        """Get BAI (author identifier) from numeric INSPIRE author ID"""
        try:
            self._rate_limit('inspire')
            
            url = f"https://inspirehep.net/api/authors/{inspire_id}"
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # Look for INSPIRE BAI in the IDs
            for id_entry in data.get('metadata', {}).get('ids', []):
                if id_entry.get('schema') == 'INSPIRE BAI':
                    return id_entry.get('value')
            
            return None
            
        except Exception as e:
            print(f"Error fetching INSPIRE BAI: {e}")
            return None
    
    def fetch_inspire_papers(self, inspire_id: str) -> List[Dict]:
        """Fetch papers from INSPIRE using INSPIRE ID"""
        papers = []
        
        try:
            self._rate_limit('inspire')
            
            # Search by INSPIRE ID - handle different formats
            if inspire_id.startswith('INSPIRE-'):
                query = f"authors.ids.value:{inspire_id}"
            elif inspire_id.isdigit():
                # Numeric INSPIRE author record ID - fetch BAI first
                bai = self._get_inspire_bai(inspire_id)
                if bai:
                    query = f"author:{bai}"
                else:
                    print(f"❌ Could not fetch BAI for INSPIRE ID {inspire_id}")
                    return papers
            else:
                # Try author BAI format
                query = f"author:{inspire_id}"
            params = {
                'q': query,
                'size': 1000,  # Maximum results
                'sort': 'mostrecent'
            }
            
            response = requests.get(self.inspire_base, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            for hit in data.get('hits', {}).get('hits', []):
                metadata = hit.get('metadata', {})
                paper = self._parse_inspire_paper(metadata)
                if paper:
                    papers.append(paper)
            
            print(f"✅ Found {len(papers)} papers from INSPIRE")
            
        except Exception as e:
            print(f"❌ Error fetching INSPIRE papers: {e}")
        
        return papers
    
    def _parse_inspire_paper(self, metadata: Dict) -> Optional[Dict]:
        """Parse INSPIRE paper metadata"""
        try:
            # Extract basic info
            title = ""
            if 'titles' in metadata and metadata['titles']:
                title = metadata['titles'][0].get('title', '')
            
            abstract = ""
            if 'abstracts' in metadata and metadata['abstracts']:
                abstract = metadata['abstracts'][0].get('value', '')
            
            # Authors
            authors = []
            if 'authors' in metadata:
                for author in metadata['authors']:
                    name = author.get('full_name', '')
                    if name:
                        authors.append(name)
            
            # arXiv ID if available
            arxiv_id = None
            if 'arxiv_eprints' in metadata and metadata['arxiv_eprints']:
                arxiv_id = metadata['arxiv_eprints'][0].get('value')
            
            # Publication date
            pub_date = ""
            if 'publication_info' in metadata and metadata['publication_info']:
                pub_date = metadata['publication_info'][0].get('year', '')
            elif 'preprint_date' in metadata:
                pub_date = metadata['preprint_date']
            
            # Categories
            categories = []
            if 'arxiv_eprints' in metadata:
                for eprint in metadata['arxiv_eprints']:
                    if 'categories' in eprint:
                        categories.extend(eprint['categories'])
            
            return {
                'title': title,
                'abstract': abstract,
                'authors': authors,
                'arxiv_id': arxiv_id,
                'publication_date': str(pub_date),
                'categories': categories,
                'source': 'INSPIRE'
            }
            
        except Exception as e:
            print(f"Error parsing INSPIRE paper: {e}")
            return None
    
    def fetch_orcid_works(self, orcid_id: str) -> List[Dict]:
        """Fetch works from ORCID using ORCID ID"""
        papers = []
        
        try:
            # Clean ORCID ID format
            if not orcid_id.startswith('0000-'):
                print("❌ Invalid ORCID format")
                return papers
            
            self._rate_limit('orcid')
            
            # Get works list
            url = f"{self.orcid_base}/{orcid_id}/works"
            headers = {'Accept': 'application/json'}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Get details for each work
            work_groups = data.get('group', [])
            if work_groups:
                for work_group in work_groups:
                    work_summaries = work_group.get('work-summary', [])
                    if work_summaries:
                        for work_summary in work_summaries:
                            put_code = work_summary.get('put-code')
                            if put_code:
                                paper = self._fetch_orcid_work_details(orcid_id, put_code)
                                if paper:
                                    papers.append(paper)
            
            print(f"✅ Found {len(papers)} works from ORCID")
            
        except Exception as e:
            print(f"❌ Error fetching ORCID works: {e}")
        
        return papers
    
    def _fetch_orcid_work_details(self, orcid_id: str, put_code: str) -> Optional[Dict]:
        """Fetch detailed work information from ORCID"""
        try:
            self._rate_limit('orcid')
            
            url = f"{self.orcid_base}/{orcid_id}/work/{put_code}"
            headers = {'Accept': 'application/json'}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract work details
            title = ""
            if 'title' in data and data['title']:
                title = data['title'].get('title', {}).get('value', '')
            
            # Journal/publication info
            journal = ""
            if 'journal-title' in data and data['journal-title']:
                journal = data['journal-title'].get('value', '')
            
            # Publication date
            pub_date = ""
            if 'publication-date' in data and data['publication-date']:
                date_info = data['publication-date']
                year = date_info.get('year', {}).get('value', '')
                month = date_info.get('month', {}).get('value', '')
                if year:
                    if month and month.isdigit():
                        pub_date = f"{year}-{int(month):02d}"
                    else:
                        pub_date = year
            
            # External identifiers (DOI, arXiv, etc.)
            identifiers = {}
            if 'external-ids' in data and data['external-ids']:
                external_ids = data['external-ids'].get('external-id', [])
                if external_ids:
                    for ext_id in external_ids:
                        if ext_id:  # Check if ext_id is not None
                            id_type = ext_id.get('external-id-type')
                            id_value = ext_id.get('external-id-value')
                            if id_type and id_value:
                                identifiers[id_type] = id_value
            
            return {
                'title': title,
                'journal': journal,
                'publication_date': pub_date,
                'identifiers': identifiers,
                'source': 'ORCID'
            }
            
        except Exception as e:
            print(f"Error fetching ORCID work details: {e}")
            return None
    
    def search_arxiv_by_author(self, author_name: str) -> List[Dict]:
        """Search arXiv by author name"""
        papers = []
        
        try:
            self._rate_limit('arxiv')
            
            # Clean author name for search
            clean_name = re.sub(r'[^\w\s]', '', author_name).strip()
            
            params = {
                'search_query': f'au:"{clean_name}"',
                'max_results': 200,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            response = requests.get(self.arxiv_base, params=params)
            response.raise_for_status()
            
            # Parse XML response (simplified - would need proper XML parsing)
            # For now, return empty list
            # TODO: Implement XML parsing for arXiv results
            
            print(f"✅ arXiv search completed for {author_name}")
            
        except Exception as e:
            print(f"❌ Error searching arXiv: {e}")
        
        return papers
    
    def synthesize_research_profile(self, papers: List[Dict]) -> Dict:
        """Use Gemini to synthesize research profile from papers"""
        try:
            self._rate_limit('gemini')
            
            # Prepare paper data for analysis
            paper_summaries = []
            for i, paper in enumerate(papers[:20]):  # Limit to avoid token limits
                summary = f"{i+1}. Title: {paper.get('title', 'N/A')}\n"
                if paper.get('abstract'):
                    summary += f"   Abstract: {paper['abstract'][:200]}...\n"
                if paper.get('categories'):
                    summary += f"   Categories: {', '.join(paper['categories'])}\n"
                if paper.get('journal'):
                    summary += f"   Journal: {paper['journal']}\n"
                summary += f"   Date: {paper.get('publication_date', 'N/A')}\n\n"
                paper_summaries.append(summary)
            
            papers_text = '\n'.join(paper_summaries)
            
            prompt = f"""
            You are an expert in theoretical physics research analysis. Analyze the following collection of papers by a theoretical physicist and extract their research profile.
            
            PAPERS:
            {papers_text}
            
            Based on these papers, provide a comprehensive research profile analysis in JSON format:
            
            {{
                "primary_research_areas": ["area1", "area2", "area3"],
                "research_keywords": ["keyword1", "keyword2", ...],
                "research_topics": ["topic1", "topic2", ...],
                "expertise_level": {{
                    "string_theory": "expert/intermediate/basic",
                    "quantum_field_theory": "expert/intermediate/basic",
                    "general_relativity": "expert/intermediate/basic",
                    "cosmology": "expert/intermediate/basic",
                    "particle_physics": "expert/intermediate/basic"
                }},
                "research_evolution": "brief description of how research has evolved",
                "collaboration_patterns": "typical collaboration types",
                "current_focus": "what seems to be the most recent focus",
                "research_summary": "2-3 sentence summary of this physicist's research"
            }}
            
            Focus on extracting specific physics concepts, theoretical frameworks, and methodologies. Be precise with terminology.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            try:
                profile_data = json.loads(response.text)
                return profile_data
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                return self._parse_profile_fallback(response.text)
                
        except Exception as e:
            print(f"❌ Error synthesizing research profile: {e}")
            return self._create_default_profile(papers)
    
    def _parse_profile_fallback(self, response_text: str) -> Dict:
        """Fallback parsing when JSON parsing fails"""
        # Simple extraction using regex
        keywords = re.findall(r'"([^"]*)"', response_text)
        
        return {
            "primary_research_areas": keywords[:5],
            "research_keywords": keywords[5:15],
            "research_topics": keywords[:10],
            "expertise_level": {},
            "research_evolution": "Could not parse research evolution",
            "collaboration_patterns": "Could not parse collaboration patterns", 
            "current_focus": "Could not parse current focus",
            "research_summary": response_text[:200] + "..."
        }
    
    def _create_default_profile(self, papers: List[Dict]) -> Dict:
        """Create a basic profile if AI synthesis fails"""
        # Extract categories from papers
        all_categories = []
        for paper in papers:
            if paper.get('categories'):
                all_categories.extend(paper['categories'])
        
        # Count category frequency
        from collections import Counter
        category_counts = Counter(all_categories)
        
        return {
            "primary_research_areas": list(category_counts.keys())[:5],
            "research_keywords": list(category_counts.keys()),
            "research_topics": list(category_counts.keys()),
            "expertise_level": {},
            "research_evolution": "Profile generated from paper categories",
            "collaboration_patterns": "Unknown",
            "current_focus": list(category_counts.keys())[0] if category_counts else "Unknown",
            "research_summary": f"Researcher with {len(papers)} publications across various physics topics"
        }
    
    def build_profile_from_ids(self, inspire_id: str = None, orcid_id: str = None, 
                              author_name: str = None) -> Dict:
        """Main method to build profile from various IDs"""
        print("🔧 Building automated research profile...")
        
        all_papers = []
        
        # Fetch from INSPIRE
        if inspire_id:
            print(f"📚 Fetching papers from INSPIRE ID: {inspire_id}")
            inspire_papers = self.fetch_inspire_papers(inspire_id)
            all_papers.extend(inspire_papers)
        
        # Fetch from ORCID
        if orcid_id:
            print(f"📄 Fetching works from ORCID ID: {orcid_id}")
            orcid_papers = self.fetch_orcid_works(orcid_id)
            all_papers.extend(orcid_papers)
        
        # Search arXiv by name
        if author_name:
            print(f"🔍 Searching arXiv for author: {author_name}")
            arxiv_papers = self.search_arxiv_by_author(author_name)
            all_papers.extend(arxiv_papers)
        
        print(f"📊 Total papers collected: {len(all_papers)}")
        
        if not all_papers:
            print("❌ No papers found. Cannot build profile.")
            return None
        
        # Deduplicate papers by title
        seen_titles = set()
        unique_papers = []
        for paper in all_papers:
            title = paper.get('title', '').strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_papers.append(paper)
        
        print(f"📝 Unique papers after deduplication: {len(unique_papers)}")
        
        # Synthesize profile using AI
        print("🧠 Synthesizing research profile with AI...")
        profile = self.synthesize_research_profile(unique_papers)
        
        # Add paper data to profile
        profile['paper_count'] = len(unique_papers)
        profile['papers_sample'] = unique_papers[:10]  # Store sample for reference
        
        return profile
    
    def save_profile_to_database(self, profile: Dict, user_info: Dict) -> None:
        """Save the synthesized profile to database"""
        try:
            profile_data = {
                'orcid': user_info.get('orcid'),
                'inspire_id': user_info.get('inspire_id'),
                'google_scholar': user_info.get('google_scholar'),
                'email': user_info.get('email'),
                'research_keywords': profile.get('research_keywords', []),
                'research_topics': profile.get('research_topics', []),
                'previous_papers': [p.get('title', '') for p in profile.get('papers_sample', [])]
            }
            
            self.db.update_user_profile(profile_data)
            print("✅ Profile saved to database!")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving profile: {e}")
            return False