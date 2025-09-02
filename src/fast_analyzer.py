"""
Fast parallel paper analyzer for DRADIS
Processes multiple papers concurrently to meet morning deadline
"""
import asyncio
import aiohttp
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from typing import List, Dict
import threading

from .config import GEMINI_API_KEY, RATE_LIMIT_DELAY
from .database import DradisDB
from .logger import get_logger

class FastPaperAnalyzer:
    def __init__(self, max_workers: int = 5, dev_mode: bool = False) -> None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY required")
        
        self.logger = get_logger(dev_mode=dev_mode)
        self.logger.operation_start("FastPaperAnalyzer initialization", max_workers=max_workers)
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.db = DradisDB()
        self.max_workers = max_workers
        self.rate_limiter = threading.Semaphore(15)  # 15 requests per 5 seconds for Gemini
        self.last_request_time = 0
        self.request_lock = threading.Lock()
        
        self.logger.operation_end("FastPaperAnalyzer initialization", max_workers=max_workers)
        
    def quick_filter(self, paper: Dict, user_profile: Dict) -> bool:
        """Quick pre-filter to skip obviously irrelevant papers"""
        if not user_profile.get('research_keywords'):
            self.logger.debug("No user research keywords, allowing all papers", paper_id=paper.get('id', 'unknown'))
            return True
        
        # Combine title and abstract
        text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
        
        # Physics relevance keywords
        physics_keywords = [
            'black hole', 'cosmology', 'gravity', 'relativity', 'spacetime',
            'quantum', 'field theory', 'gauge theory', 'string theory',
            'dark matter', 'dark energy', 'inflation', 'universe'
        ]
        
        # Check for basic physics relevance
        has_physics = any(keyword in text for keyword in physics_keywords)
        
        # Check for user-specific keywords
        user_keywords = [kw.lower() for kw in user_profile['research_keywords']]
        has_user_relevance = any(keyword in text for keyword in user_keywords)
        
        # Log filtering decision
        result = has_physics or has_user_relevance
        if not result:
            self.logger.debug("Paper filtered out - no physics/user relevance", 
                            paper_id=paper.get('id', 'unknown'),
                            title=paper.get('title', 'unknown')[:50])
        else:
            self.logger.debug("Paper passed quick filter", 
                            paper_id=paper.get('id', 'unknown'),
                            has_physics=has_physics,
                            has_user_relevance=has_user_relevance)
        
        # Skip if neither physics nor user relevant
        return result
    
    def fast_analysis_prompt(self, paper: Dict, user_profile: Dict) -> str:
        """Shorter, faster analysis prompt"""
        user_keywords = ', '.join(user_profile.get('research_keywords', [])[:5])
        
        return f"""
        User expertise: {user_keywords}
        
        Paper: "{paper['title']}"
        Abstract: {paper['abstract'][:300]}...
        
        Quick relevance analysis (respond in JSON only):
        {{
            "relevance_score": 0.0-1.0,
            "key_concepts": ["concept1", "concept2"],
            "flagged": true/false,
            "reasoning": "brief explanation"
        }}
        """
    
    def analyze_paper_batch(self, papers: List[Dict], user_profile: Dict) -> List[Dict]:
        """Analyze a batch of papers with threading"""
        batch_start_time = time.time()
        self.logger.operation_start("Paper batch analysis", 
                                  batch_size=len(papers),
                                  max_workers=self.max_workers)
        
        results = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all papers for analysis
            future_to_paper = {
                executor.submit(self.analyze_single_paper, paper, user_profile): paper 
                for paper in papers
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                processed_count += 1
                
                try:
                    analysis = future.result()
                    if analysis:
                        results.append((paper['id'], analysis))
                        score = analysis.get('relevance_score', 0)
                        
                        # Log individual paper completion (dev mode only for detailed logging)
                        self.logger.debug("Paper analysis completed",
                                        paper_id=paper['id'],
                                        title=paper['title'][:50],
                                        relevance_score=score,
                                        flagged=analysis.get('flagged', False))
                        
                        # Log high-scoring papers at info level
                        if score >= 0.7:
                            self.logger.info("High relevance paper found",
                                           paper_id=paper['id'],
                                           title=paper['title'][:50],
                                           relevance_score=score)
                        
                        print(f"✅ Analyzed: {paper['title'][:50]}... (Score: {score:.2f})")
                        
                        # Progress logging
                        self.logger.progress("Batch analysis", processed_count, len(papers))
                        
                except Exception as e:
                    self.logger.error("Paper analysis failed", 
                                    paper_id=paper.get('id', 'unknown'),
                                    error=str(e),
                                    exc_info=True)
                    print(f"❌ Error analyzing {paper['id']}: {e}")
                    continue
        
        batch_time = time.time() - batch_start_time
        success_rate = len(results) / len(papers) * 100 if papers else 0
        
        self.logger.operation_end("Paper batch analysis",
                                success=True,
                                batch_size=len(papers),
                                successful_analyses=len(results),
                                success_rate=f"{success_rate:.1f}%",
                                processing_time=f"{batch_time:.2f}s")
        
        return results
    
    def analyze_single_paper(self, paper: Dict, user_profile: Dict) -> Dict:
        """Analyze single paper with rate limiting"""
        paper_id = paper.get('id', 'unknown')
        paper_title = paper.get('title', 'unknown')[:50]
        
        try:
            self.logger.debug("Starting paper analysis", 
                            paper_id=paper_id,
                            title=paper_title)
            
            # Rate limiting
            with self.request_lock:
                current_time = time.time()
                wait_time = 0.2 - (current_time - self.last_request_time)
                if wait_time > 0:
                    self.logger.debug("Rate limiting - waiting", 
                                    paper_id=paper_id,
                                    wait_time=f"{wait_time:.3f}s")
                    time.sleep(wait_time)
                self.last_request_time = time.time()
            
            # Quick pre-filter
            if not self.quick_filter(paper, user_profile):
                self.logger.debug("Paper pre-filtered out", paper_id=paper_id)
                return {
                    'relevance_score': 0.0,
                    'key_concepts': [],
                    'flagged': False,
                    'reasoning': 'Pre-filtered as irrelevant'
                }
            
            # Generate analysis prompt
            prompt = self.fast_analysis_prompt(paper, user_profile)
            self.logger.debug("Generated analysis prompt", 
                            paper_id=paper_id,
                            prompt_length=len(prompt))
            
            # Call Gemini with rate limiting semaphore
            api_start_time = time.time()
            with self.rate_limiter:
                self.logger.debug("Making Gemini API call", paper_id=paper_id)
                response = self.model.generate_content(prompt)
                api_time = time.time() - api_start_time
                
                self.logger.debug("Gemini API response received", 
                                paper_id=paper_id,
                                api_time=f"{api_time:.3f}s",
                                response_length=len(response.text) if response.text else 0)
                
                # Parse JSON response
                try:
                    analysis = json.loads(response.text)
                    # Ensure required fields
                    analysis.setdefault('relevance_score', 0.0)
                    analysis.setdefault('key_concepts', [])
                    analysis.setdefault('flagged', analysis.get('relevance_score', 0) >= 0.7)
                    analysis.setdefault('reasoning', 'Analysis completed')
                    
                    self.logger.debug("Successfully parsed analysis response", 
                                    paper_id=paper_id,
                                    relevance_score=analysis['relevance_score'])
                    return analysis
                    
                except json.JSONDecodeError as json_error:
                    self.logger.warning("JSON parsing failed, using fallback", 
                                      paper_id=paper_id,
                                      json_error=str(json_error),
                                      response_text=response.text[:200])
                    # Fallback for malformed JSON
                    return self._parse_fallback(response.text)
                    
        except Exception as e:
            self.logger.error("Single paper analysis failed", 
                            paper_id=paper_id,
                            title=paper_title,
                            error=str(e),
                            exc_info=True)
            print(f"Error in single paper analysis: {e}")
            return {
                'relevance_score': 0.0,
                'key_concepts': [],
                'flagged': False,
                'reasoning': f'Analysis failed: {str(e)}'
            }
    
    def _parse_fallback(self, response_text: str) -> Dict:
        """Fallback parsing for malformed responses"""
        import re
        
        self.logger.debug("Using fallback response parsing", response_preview=response_text[:100])
        
        score_match = re.search(r'"relevance_score"[:\s]*([0-9.]+)', response_text)
        score = float(score_match.group(1)) if score_match else 0.0
        
        result = {
            'relevance_score': score,
            'key_concepts': [],
            'flagged': score >= 0.7,
            'reasoning': 'Parsed from malformed response'
        }
        
        self.logger.debug("Fallback parsing completed", extracted_score=score)
        return result
    
    def fast_analyze_pending_papers(self, batch_size: int = 20) -> int:
        """Fast analysis of all pending papers"""
        operation_start_time = time.time()
        self.logger.operation_start("Fast parallel analysis", batch_size=batch_size)
        print("🚀 Starting fast parallel analysis...")
        
        try:
            # Get user profile
            self.logger.info("Retrieving user profile")
            user_profile = self.db.get_user_profile()
            if not user_profile:
                self.logger.error("No user profile found - cannot proceed with analysis")
                print("❌ No user profile found")
                return 0
            
            self.logger.info("User profile retrieved", 
                           keywords_count=len(user_profile.get('research_keywords', [])))
            
            # Get unprocessed papers
            self.logger.info("Retrieving unprocessed papers")
            papers = self.db.get_unprocessed_papers()
            self.logger.info("Found papers to analyze", paper_count=len(papers))
            print(f"📄 Found {len(papers)} papers to analyze")
            
            if not papers:
                self.logger.info("No papers to analyze")
                return 0
            
            analyzed_count = 0
            total_batches = (len(papers) + batch_size - 1) // batch_size
            
            # Process in batches
            for i in range(0, len(papers), batch_size):
                batch_num = i // batch_size + 1
                batch = papers[i:i + batch_size]
                
                batch_start_time = time.time()
                self.logger.info("Starting batch processing", 
                               batch_number=batch_num,
                               total_batches=total_batches,
                               batch_size=len(batch))
                
                print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} papers)")
                
                # Analyze batch
                results = self.analyze_paper_batch(batch, user_profile)
                
                # Save results
                save_start_time = time.time()
                for paper_id, analysis in results:
                    try:
                        self.db.save_paper_analysis(paper_id, analysis)
                        self.db.mark_paper_processed(paper_id)
                        analyzed_count += 1
                        
                        self.logger.debug("Paper analysis saved", paper_id=paper_id)
                        
                    except Exception as e:
                        self.logger.error("Failed to save paper analysis", 
                                        paper_id=paper_id,
                                        error=str(e),
                                        exc_info=True)
                
                batch_time = time.time() - batch_start_time
                save_time = time.time() - save_start_time
                success_rate = len(results) / len(batch) * 100 if batch else 0
                
                self.logger.info("Batch processing completed", 
                               batch_number=batch_num,
                               successful_analyses=len(results),
                               batch_size=len(batch),
                               success_rate=f"{success_rate:.1f}%",
                               batch_time=f"{batch_time:.2f}s",
                               save_time=f"{save_time:.2f}s")
                
                print(f"✅ Batch complete: {len(results)}/{len(batch)} successful")
                
                # Overall progress
                self.logger.progress("Overall analysis", batch_num, total_batches)
            
            total_time = time.time() - operation_start_time
            success_rate = analyzed_count / len(papers) * 100 if papers else 0
            
            self.logger.operation_end("Fast parallel analysis",
                                    success=True,
                                    total_papers=len(papers),
                                    analyzed_papers=analyzed_count,
                                    success_rate=f"{success_rate:.1f}%",
                                    total_time=f"{total_time:.2f}s",
                                    papers_per_second=f"{analyzed_count/total_time:.2f}" if total_time > 0 else "N/A")
            
            print(f"\n🎉 Fast analysis complete: {analyzed_count} papers processed")
            return analyzed_count
            
        except Exception as e:
            self.logger.error("Fast analysis operation failed", 
                            error=str(e),
                            exc_info=True)
            self.logger.operation_end("Fast parallel analysis", success=False, error=str(e))
            raise