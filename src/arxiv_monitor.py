"""
arXiv monitoring module for DRADIS
Handles daily fetching of papers from RSS feeds and arXiv API
"""
import feedparser
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from .config import ARXIV_RSS_FEEDS, ARXIV_API_BASE, RATE_LIMIT_DELAY
from .database import DradisDB
from .logger import get_logger

class ArxivMonitor:
    def __init__(self, skip_replacements: bool = True, dev_mode: bool = False) -> None:
        self.logger = get_logger(dev_mode=dev_mode)
        self.logger.operation_start("ArxivMonitor initialization", 
                                  skip_replacements=skip_replacements)
        
        self.db = DradisDB()
        self.skip_replacements = skip_replacements
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DRADIS/1.0 (Physics Research Assistant)'
        })
        
        self.logger.info("ArxivMonitor initialized", 
                       skip_replacements=skip_replacements,
                       configured_feeds=len(ARXIV_RSS_FEEDS))
        self.logger.operation_end("ArxivMonitor initialization")
    
    def fetch_rss_feeds(self) -> List[Dict]:
        """Fetch papers from all configured RSS feeds"""
        operation_start_time = time.time()
        self.logger.operation_start("RSS feeds fetching", 
                                  feed_count=len(ARXIV_RSS_FEEDS),
                                  skip_replacements=self.skip_replacements)
        
        all_papers = []
        successful_feeds = 0
        failed_feeds = 0
        
        for i, (category, rss_url) in enumerate(ARXIV_RSS_FEEDS.items()):
            feed_start_time = time.time()
            try:
                self.logger.info("Fetching RSS feed", 
                               category=category,
                               feed_number=i+1,
                               total_feeds=len(ARXIV_RSS_FEEDS),
                               url=rss_url)
                
                print(f"Fetching papers from {category}...")
                feed = feedparser.parse(rss_url)
                
                if hasattr(feed, 'status') and feed.status != 200:
                    self.logger.warning("RSS feed returned non-200 status", 
                                      category=category,
                                      status_code=feed.status)
                
                parsed_papers = 0
                skipped_papers = 0
                
                for entry in feed.entries:
                    paper = self._parse_rss_entry(entry, category)
                    if paper:
                        all_papers.append(paper)
                        parsed_papers += 1
                        self.logger.debug("Paper parsed from RSS", 
                                        category=category,
                                        paper_id=paper.get('id', 'unknown'),
                                        title=paper.get('title', 'unknown')[:50])
                    else:
                        skipped_papers += 1
                
                feed_time = time.time() - feed_start_time
                successful_feeds += 1
                
                self.logger.info("RSS feed processed", 
                               category=category,
                               papers_found=len(feed.entries),
                               papers_parsed=parsed_papers,
                               papers_skipped=skipped_papers,
                               processing_time=f"{feed_time:.2f}s")
                
                # Progress logging
                self.logger.progress("RSS feed fetching", i+1, len(ARXIV_RSS_FEEDS))
                
                # Rate limiting
                if RATE_LIMIT_DELAY > 0:
                    self.logger.debug("Rate limiting delay", 
                                    category=category,
                                    delay=f"{RATE_LIMIT_DELAY}s")
                    time.sleep(RATE_LIMIT_DELAY)
                
            except Exception as e:
                failed_feeds += 1
                self.logger.error("RSS feed fetching failed", 
                                category=category,
                                url=rss_url,
                                error=str(e),
                                exc_info=True)
                print(f"Error fetching RSS feed for {category}: {e}")
        
        total_time = time.time() - operation_start_time
        success_rate = successful_feeds / len(ARXIV_RSS_FEEDS) * 100 if ARXIV_RSS_FEEDS else 0
        
        self.logger.operation_end("RSS feeds fetching",
                                success=failed_feeds == 0,
                                total_feeds=len(ARXIV_RSS_FEEDS),
                                successful_feeds=successful_feeds,
                                failed_feeds=failed_feeds,
                                success_rate=f"{success_rate:.1f}%",
                                total_papers_found=len(all_papers),
                                total_time=f"{total_time:.2f}s")
        
        return all_papers
    
    def _parse_rss_entry(self, entry, category: str) -> Dict:
        """Parse an RSS entry into a standardized paper dict"""
        try:
            # Skip replacements - only process new papers (if enabled)
            if self.skip_replacements and hasattr(entry, 'summary') and 'Announce Type: replace' in entry.summary:
                title_preview = entry.title[:50] if hasattr(entry, 'title') else 'unknown'
                self.logger.debug("Skipping replacement paper", 
                                category=category,
                                title=title_preview)
                print(f"⏭️  Skipping replacement: {title_preview}...")
                return None
                
            # Extract arXiv ID from the link or ID
            arxiv_id = None
            id_source = None
            
            if hasattr(entry, 'id'):
                # ID format: oai:arXiv.org:2401.00001v1 or http://arxiv.org/abs/2401.00001v1
                if 'oai:arXiv.org:' in entry.id:
                    arxiv_id = entry.id.replace('oai:arXiv.org:', '')
                    id_source = 'oai_id'
                else:
                    arxiv_id = entry.id.split('/')[-1]
                    id_source = 'id_url'
            elif hasattr(entry, 'link'):
                arxiv_id = entry.link.split('/')[-1]
                id_source = 'link'
            
            if not arxiv_id:
                self.logger.warning("Could not extract arXiv ID from RSS entry", 
                                  category=category,
                                  has_id=hasattr(entry, 'id'),
                                  has_link=hasattr(entry, 'link'))
                return None
            
            # Clean up arXiv ID (remove version suffix for database key)
            clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
            
            self.logger.debug("Extracted arXiv ID", 
                            category=category,
                            raw_id=arxiv_id,
                            clean_id=clean_id,
                            id_source=id_source)
            
            # Parse authors
            authors = []
            if hasattr(entry, 'authors'):
                authors = [author.name for author in entry.authors]
            elif hasattr(entry, 'author'):
                # Simple string format
                authors = [entry.author]
            
            # Build paper dict
            paper = {
                'id': clean_id,
                'title': entry.title.replace('\n', ' ').strip(),
                'authors': authors,
                'abstract': entry.summary.replace('\n', ' ').strip() if hasattr(entry, 'summary') else '',
                'categories': [category],
                'published': entry.published if hasattr(entry, 'published') else datetime.now().isoformat(),
                'updated': entry.updated if hasattr(entry, 'updated') else None,
                'pdf_url': f"https://arxiv.org/pdf/{clean_id}.pdf",
                'arxiv_url': f"https://arxiv.org/abs/{clean_id}"
            }
            
            self.logger.debug("Successfully parsed RSS entry", 
                            category=category,
                            paper_id=clean_id,
                            title=paper['title'][:50],
                            author_count=len(authors),
                            has_abstract=bool(paper['abstract']))
            
            return paper
            
        except Exception as e:
            self.logger.error("RSS entry parsing failed", 
                            category=category,
                            error=str(e),
                            has_title=hasattr(entry, 'title'),
                            has_summary=hasattr(entry, 'summary'),
                            has_id=hasattr(entry, 'id'),
                            exc_info=True)
            print(f"Error parsing RSS entry: {e}")
            return None
    
    def fetch_paper_details(self, arxiv_ids: List[str]) -> List[Dict]:
        """Fetch detailed paper information using arXiv API"""
        operation_start_time = time.time()
        self.logger.operation_start("ArXiv API paper details fetch", 
                                  paper_count=len(arxiv_ids),
                                  batch_size=20)
        
        papers = []
        successful_batches = 0
        failed_batches = 0
        
        # Process in batches to avoid URL length limits
        batch_size = 20
        total_batches = (len(arxiv_ids) + batch_size - 1) // batch_size
        
        for i in range(0, len(arxiv_ids), batch_size):
            batch_num = i // batch_size + 1
            batch = arxiv_ids[i:i + batch_size]
            batch_start_time = time.time()
            
            try:
                self.logger.info("Fetching paper details batch", 
                               batch_number=batch_num,
                               total_batches=total_batches,
                               batch_size=len(batch))
                
                # Construct API query
                params = {
                    'id_list': ','.join(batch),
                    'max_results': batch_size
                }
                
                url = f"{ARXIV_API_BASE}?{urlencode(params)}"
                self.logger.debug("Making arXiv API request", 
                                batch_number=batch_num,
                                url=url,
                                paper_ids=batch)
                
                response = self.session.get(url)
                response.raise_for_status()
                
                api_time = time.time() - batch_start_time
                self.logger.debug("ArXiv API response received", 
                                batch_number=batch_num,
                                status_code=response.status_code,
                                response_size=len(response.content),
                                api_time=f"{api_time:.3f}s")
                
                # Parse XML response
                root = ET.fromstring(response.content)
                namespace = {'atom': 'http://www.w3.org/2005/Atom',
                           'arxiv': 'http://arxiv.org/schemas/atom'}
                
                batch_papers = 0
                for entry in root.findall('atom:entry', namespace):
                    paper = self._parse_api_entry(entry, namespace)
                    if paper:
                        papers.append(paper)
                        batch_papers += 1
                        self.logger.debug("Paper parsed from API", 
                                        batch_number=batch_num,
                                        paper_id=paper.get('id', 'unknown'),
                                        title=paper.get('title', 'unknown')[:50])
                
                batch_time = time.time() - batch_start_time
                successful_batches += 1
                
                self.logger.info("API batch processed", 
                               batch_number=batch_num,
                               papers_requested=len(batch),
                               papers_received=batch_papers,
                               batch_time=f"{batch_time:.2f}s")
                
                # Progress logging
                self.logger.progress("API paper details fetch", batch_num, total_batches)
                
                # Rate limiting
                if RATE_LIMIT_DELAY > 0:
                    self.logger.debug("API rate limiting delay", 
                                    batch_number=batch_num,
                                    delay=f"{RATE_LIMIT_DELAY}s")
                    time.sleep(RATE_LIMIT_DELAY)
                
            except requests.exceptions.RequestException as e:
                failed_batches += 1
                self.logger.error("ArXiv API request failed", 
                                batch_number=batch_num,
                                paper_ids=batch,
                                error=str(e),
                                exc_info=True)
                print(f"Error fetching paper details for batch {i}: {e}")
                
            except ET.ParseError as e:
                failed_batches += 1
                self.logger.error("ArXiv API response parsing failed", 
                                batch_number=batch_num,
                                error=str(e),
                                response_preview=response.content[:500] if 'response' in locals() else None,
                                exc_info=True)
                print(f"Error parsing API response for batch {i}: {e}")
                
            except Exception as e:
                failed_batches += 1
                self.logger.error("Unexpected error in API batch processing", 
                                batch_number=batch_num,
                                error=str(e),
                                exc_info=True)
                print(f"Error fetching paper details for batch {i}: {e}")
        
        total_time = time.time() - operation_start_time
        success_rate = successful_batches / total_batches * 100 if total_batches > 0 else 0
        
        self.logger.operation_end("ArXiv API paper details fetch",
                                success=failed_batches == 0,
                                total_batches=total_batches,
                                successful_batches=successful_batches,
                                failed_batches=failed_batches,
                                success_rate=f"{success_rate:.1f}%",
                                papers_requested=len(arxiv_ids),
                                papers_received=len(papers),
                                total_time=f"{total_time:.2f}s")
        
        return papers
    
    def _parse_api_entry(self, entry, namespace: Dict) -> Dict:
        """Parse an arXiv API entry into a standardized paper dict"""
        try:
            # Extract arXiv ID
            id_elem = entry.find('atom:id', namespace)
            if id_elem is None:
                self.logger.warning("No ID element found in API entry")
                return None
                
            arxiv_id = id_elem.text.split('/')[-1]
            clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
            
            self.logger.debug("Parsing API entry", 
                            raw_id=arxiv_id,
                            clean_id=clean_id)
            
            # Title and abstract
            title_elem = entry.find('atom:title', namespace)
            abstract_elem = entry.find('atom:summary', namespace)
            
            if title_elem is None:
                self.logger.warning("No title element found in API entry", paper_id=clean_id)
                return None
                
            title = title_elem.text.replace('\n', ' ').strip()
            abstract = abstract_elem.text.replace('\n', ' ').strip() if abstract_elem is not None else ''
            
            # Authors
            authors = []
            for author in entry.findall('atom:author', namespace):
                name = author.find('atom:name', namespace)
                if name is not None:
                    authors.append(name.text)
            
            self.logger.debug("Parsed authors", 
                            paper_id=clean_id,
                            author_count=len(authors))
            
            # Categories
            categories = []
            for category in entry.findall('atom:category', namespace):
                term = category.get('term')
                if term:
                    categories.append(term)
            
            self.logger.debug("Parsed categories", 
                            paper_id=clean_id,
                            categories=categories)
            
            # Dates
            published = entry.find('atom:published', namespace)
            updated = entry.find('atom:updated', namespace)
            
            # Links
            pdf_url = None
            arxiv_url = None
            links_found = 0
            
            for link in entry.findall('atom:link', namespace):
                links_found += 1
                if link.get('title') == 'pdf':
                    pdf_url = link.get('href')
                elif link.get('rel') == 'alternate':
                    arxiv_url = link.get('href')
            
            self.logger.debug("Parsed links", 
                            paper_id=clean_id,
                            links_found=links_found,
                            has_pdf_url=pdf_url is not None,
                            has_arxiv_url=arxiv_url is not None)
            
            paper = {
                'id': clean_id,
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'categories': categories,
                'published': published.text if published is not None else datetime.now().isoformat(),
                'updated': updated.text if updated is not None else None,
                'pdf_url': pdf_url or f"https://arxiv.org/pdf/{clean_id}.pdf",
                'arxiv_url': arxiv_url or f"https://arxiv.org/abs/{clean_id}"
            }
            
            self.logger.debug("Successfully parsed API entry", 
                            paper_id=clean_id,
                            title=title[:50],
                            category_count=len(categories),
                            has_abstract=bool(abstract))
            
            return paper
            
        except Exception as e:
            self.logger.error("API entry parsing failed", 
                            error=str(e),
                            exc_info=True)
            print(f"Error parsing API entry: {e}")
            return None
    
    def fetch_papers_by_date(self, target_date: str) -> List[Dict]:
        """Fetch papers submitted on a specific date using arXiv API"""
        self.logger.info("Starting API date search", target_date=target_date)
        
        # Format date for arXiv API (YYYYMMDD format)
        try:
            # Parse various date formats
            if len(target_date) == 10 and '-' in target_date:  # YYYY-MM-DD
                date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            elif len(target_date) == 8:  # YYYYMMDD
                date_obj = datetime.strptime(target_date, '%Y%m%d')
            else:
                raise ValueError(f"Invalid date format: {target_date}")
                
            # Format for arXiv API
            arxiv_date = date_obj.strftime('%Y%m%d')
            self.logger.info("Parsed target date", 
                           input_date=target_date,
                           arxiv_date=arxiv_date)
            
        except ValueError as e:
            self.logger.error("Date parsing failed", 
                            target_date=target_date, 
                            error=str(e))
            print(f"Error: Invalid date format '{target_date}'. Use YYYY-MM-DD or YYYYMMDD")
            return []
        
        all_papers = []
        categories = list(ARXIV_RSS_FEEDS.keys())
        
        for category in categories:
            self.logger.info("Fetching API papers", 
                           category=category,
                           date=arxiv_date)
            print(f"Fetching {category} papers for {target_date}...")
            
            # Build search query for specific date and category
            search_query = f"submittedDate:{arxiv_date}* AND cat:{category}"
            
            params = {
                'search_query': search_query,
                'start': 0,
                'max_results': 1000,  # Generous limit
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            try:
                response = self.session.get(ARXIV_API_BASE, params=params, timeout=30)
                response.raise_for_status()
                
                # Parse XML response
                root = ET.fromstring(response.content)
                namespace = {'atom': 'http://www.w3.org/2005/Atom',
                           'arxiv': 'http://arxiv.org/schemas/atom'}
                
                entries = root.findall('atom:entry', namespace)
                category_papers = []
                
                for entry in entries:
                    paper = self._parse_api_entry(entry, namespace)
                    if paper:
                        category_papers.append(paper)
                        
                self.logger.info("API category processed", 
                               category=category,
                               papers_found=len(category_papers))
                all_papers.extend(category_papers)
                
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)
                
            except Exception as e:
                self.logger.error("API fetch failed", 
                                category=category,
                                error=str(e),
                                exc_info=True)
                print(f"Error fetching {category}: {e}")
                continue
        
        self.logger.info("API date search completed", 
                       target_date=target_date,
                       total_papers=len(all_papers))
        return all_papers
    
    def daily_harvest(self, target_date: str = None) -> int:
        """Run daily paper harvesting process"""
        harvest_start_time = time.time()
        current_time = datetime.now()
        
        self.logger.operation_start("Daily paper harvest", 
                                  timestamp=current_time.isoformat())
        
        print(f"Starting daily harvest at {current_time}")
        
        try:
            # Choose data source based on target_date
            if target_date:
                # Historical date: use API search
                self.logger.info("Starting API harvesting", target_date=target_date)
                papers = self.fetch_papers_by_date(target_date)
                print(f"Fetching papers for date: {target_date}")
            else:
                # Today's papers: use RSS feeds
                self.logger.info("Starting RSS feed harvesting")
                papers = self.fetch_rss_feeds()
            
            self.logger.info("Paper fetching completed", 
                           papers_found=len(papers))
            print(f"Found {len(papers)} papers")
            
            # Store papers in database
            self.logger.info("Starting database storage")
            new_papers = 0
            duplicate_papers = 0
            failed_papers = 0
            
            for i, paper in enumerate(papers):
                try:
                    if self.db.add_paper(paper):
                        new_papers += 1
                        self.logger.debug("New paper added to database", 
                                        paper_id=paper.get('id', 'unknown'),
                                        title=paper.get('title', 'unknown')[:50])
                    else:
                        duplicate_papers += 1
                        self.logger.debug("Duplicate paper skipped", 
                                        paper_id=paper.get('id', 'unknown'))
                        
                    # Progress logging every 10 papers
                    if (i + 1) % 10 == 0 or (i + 1) == len(papers):
                        self.logger.progress("Database storage", i + 1, len(papers))
                        
                except Exception as e:
                    failed_papers += 1
                    self.logger.error("Failed to add paper to database", 
                                    paper_id=paper.get('id', 'unknown'),
                                    error=str(e),
                                    exc_info=True)
            
            harvest_time = time.time() - harvest_start_time
            
            self.logger.operation_end("Daily paper harvest",
                                    success=True,
                                    papers_found=len(papers),
                                    new_papers=new_papers,
                                    duplicate_papers=duplicate_papers,
                                    failed_papers=failed_papers,
                                    harvest_time=f"{harvest_time:.2f}s")
            
            print(f"Added {new_papers} new papers to database")
            return new_papers
            
        except Exception as e:
            self.logger.error("Daily harvest failed", 
                            error=str(e),
                            exc_info=True)
            self.logger.operation_end("Daily paper harvest", 
                                    success=False, 
                                    error=str(e))
            raise
    
    def search_papers(self, query: str, max_results: int = 100) -> List[Dict]:
        """Search for papers using arXiv API"""
        search_start_time = time.time()
        self.logger.operation_start("ArXiv paper search", 
                                  query=query,
                                  max_results=max_results)
        
        try:
            params = {
                'search_query': query,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            url = f"{ARXIV_API_BASE}?{urlencode(params)}"
            
            self.logger.info("Making arXiv search API request", 
                           query=query,
                           max_results=max_results,
                           url=url)
            
            response = self.session.get(url)
            response.raise_for_status()
            
            api_time = time.time() - search_start_time
            self.logger.debug("ArXiv search API response received", 
                            status_code=response.status_code,
                            response_size=len(response.content),
                            api_time=f"{api_time:.3f}s")
            
            # Parse XML response
            root = ET.fromstring(response.content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom',
                        'arxiv': 'http://arxiv.org/schemas/atom'}
            
            papers = []
            entries_found = len(root.findall('atom:entry', namespace))
            
            self.logger.debug("Parsing search results", entries_found=entries_found)
            
            for i, entry in enumerate(root.findall('atom:entry', namespace)):
                paper = self._parse_api_entry(entry, namespace)
                if paper:
                    papers.append(paper)
                    self.logger.debug("Search result parsed", 
                                    result_number=i+1,
                                    paper_id=paper.get('id', 'unknown'),
                                    title=paper.get('title', 'unknown')[:50])
            
            search_time = time.time() - search_start_time
            
            self.logger.operation_end("ArXiv paper search",
                                    success=True,
                                    query=query,
                                    entries_found=entries_found,
                                    papers_parsed=len(papers),
                                    search_time=f"{search_time:.2f}s")
            
            return papers
            
        except requests.exceptions.RequestException as e:
            self.logger.error("ArXiv search API request failed", 
                            query=query,
                            error=str(e),
                            exc_info=True)
            self.logger.operation_end("ArXiv paper search", success=False, error=str(e))
            print(f"Error searching papers: {e}")
            return []
            
        except ET.ParseError as e:
            self.logger.error("ArXiv search response parsing failed", 
                            query=query,
                            error=str(e),
                            response_preview=response.content[:500] if 'response' in locals() else None,
                            exc_info=True)
            self.logger.operation_end("ArXiv paper search", success=False, error=str(e))
            print(f"Error parsing search response: {e}")
            return []
            
        except Exception as e:
            self.logger.error("Unexpected error in paper search", 
                            query=query,
                            error=str(e),
                            exc_info=True)
            self.logger.operation_end("ArXiv paper search", success=False, error=str(e))
            print(f"Error searching papers: {e}")
            return []