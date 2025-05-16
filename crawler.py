import logging
import requests
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import trafilatura
import queue
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class WebsiteCrawler:
    def __init__(self, max_depth=3, max_pages=50, request_delay=1, timeout=30):
        """
        Initialize the WebsiteCrawler.
        
        Args:
            max_depth (int): Maximum depth to crawl
            max_pages (int): Maximum number of pages to crawl
            request_delay (float): Delay between requests in seconds
            timeout (int): Timeout for the crawling process in seconds
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.request_delay = request_delay
        self.timeout = timeout
        self.visited_urls = set()
        self.pages = []  # List to store crawled pages
        self.url_queue = queue.Queue()
        self.lock = threading.Lock()
        
    def is_valid_url(self, url, base_domain):
        """Check if URL is valid and belongs to the same domain"""
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_domain)
        
        # Check if the URL is from the same domain
        return bool(parsed_url.netloc) and parsed_url.netloc == parsed_base.netloc
    
    def extract_text_content(self, url, html_content):
        """Extract clean text content from HTML"""
        try:
            # Use trafilatura for content extraction
            text = trafilatura.extract(html_content)
            
            # Fallback to BeautifulSoup if trafilatura returns None
            if text is None:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                
                # Get text
                text = soup.get_text(separator=' ', strip=True)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {url}: {str(e)}")
            return ""
    
    def extract_links(self, base_url, html_content):
        """Extract all links from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        base_domain = urlparse(base_url).netloc
        
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            
            # Validate URL
            if self.is_valid_url(full_url, base_url):
                # Remove fragments and query parameters
                parsed_url = urlparse(full_url)
                clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                links.append(clean_url)
        
        return links
    
    def process_page(self, url, depth, base_url):
        """Process a single page by extracting its content and links"""
        if len(self.pages) >= self.max_pages:
            return
        
        try:
            # Add more robust error handling for network issues
            try:
                # Set a lower timeout and add headers to mimic a real browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                }
                response = requests.get(url, timeout=8, headers=headers, allow_redirects=True)
                response.raise_for_status()
            except requests.exceptions.SSLError:
                logger.warning(f"SSL Error for {url}, trying without verification")
                response = requests.get(url, timeout=8, headers=headers, verify=False, allow_redirects=True)
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Error requesting {url}: {str(e)}")
                return
            
            # Extract text content
            text_content = self.extract_text_content(url, response.text)
            
            # Add page to the list even if content is minimal
            title = self._extract_title(response.text) or "Untitled Page"
            content = text_content or f"Unable to extract text content from {url}"
            
            with self.lock:
                self.pages.append({
                    'url': url,
                    'title': title,
                    'content': content
                })
                logger.debug(f"Added page: {url}")
            
            # Extract links if we're not at max depth
            if depth < self.max_depth:
                try:
                    links = self.extract_links(base_url, response.text)
                    
                    # Add links to queue with duplicate checking
                    link_count = 0
                    for link in links:
                        if link_count >= 50:  # Limit links per page to avoid overloading
                            break
                            
                        if link not in self.visited_urls and len(self.pages) < self.max_pages:
                            with self.lock:
                                if link not in self.visited_urls:
                                    self.visited_urls.add(link)
                                    self.url_queue.put((link, depth + 1, base_url))
                                    link_count += 1
                except Exception as e:
                    logger.error(f"Error extracting links from {url}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
    
    def _extract_title(self, html_content):
        """Extract title from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.text if title_tag else "No Title"
    
    def crawl_worker(self):
        """Worker function to process URLs from the queue"""
        while not self.url_queue.empty() and len(self.pages) < self.max_pages:
            try:
                url, depth, base_url = self.url_queue.get(block=False)
                self.process_page(url, depth, base_url)
                # Add delay to avoid overwhelming the server
                time.sleep(self.request_delay)
                self.url_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error in crawler worker: {str(e)}")
                self.url_queue.task_done()
    
    def crawl(self, start_url):
        """Start the crawling process from a given URL"""
        self.visited_urls = set()
        self.pages = []
        self.url_queue = queue.Queue()
        
        # Add start URL to queue without validation (will be validated in process_page)
        self.visited_urls.add(start_url)
        self.url_queue.put((start_url, 1, start_url))
        
        # Start crawling with breadth-first approach (safer than recursive DFS)
        logger.info(f"Starting crawl from {start_url} with max depth {self.max_depth} and max pages {self.max_pages}")
        
        # Process pages until queue is empty or max pages reached
        start_time = time.time()
        
        try:
            # Process the start URL first to ensure we get at least some content
            url, depth, base_url = self.url_queue.get()
            try:
                self.process_page(url, depth, base_url)
            except Exception as e:
                logger.error(f"Error processing start URL {url}: {str(e)}")
                # If start URL fails completely, add a minimal page with just the URL
                self.pages.append({
                    'url': start_url,
                    'title': "Failed to load page",
                    'content': f"Unable to crawl this page. Error: {str(e)}"
                })
            
            # Process the rest of the queue with timeout protection
            while not self.url_queue.empty() and len(self.pages) < self.max_pages:
                # Check timeout
                if time.time() - start_time > self.timeout:
                    logger.warning(f"Crawling timed out after {self.timeout} seconds")
                    break
                    
                # Process next URL
                self.crawl_worker()
                
            logger.info(f"Crawling completed. Crawled {len(self.pages)} pages.")
        except Exception as e:
            logger.error(f"Error during crawl: {str(e)}")
            # Ensure we return at least the minimal data if everything fails
            if not self.pages:
                self.pages.append({
                    'url': start_url,
                    'title': "Crawl failed",
                    'content': f"Unable to crawl this website. Error: {str(e)}"
                })
        
        # Always return some pages, even if empty
        if not self.pages:
            self.pages.append({
                'url': start_url,
                'title': "No content found",
                'content': "No content could be extracted from this website."
            })
            
        return self.pages
