import logging
import requests
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import trafilatura

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class WebsiteCrawler:
    def __init__(self, max_depth=3, max_pages=50, request_delay=1):
        """
        Initialize the WebsiteCrawler.
        
        Args:
            max_depth (int): Maximum depth to crawl
            max_pages (int): Maximum number of pages to crawl
            request_delay (float): Delay between requests in seconds
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.request_delay = request_delay
        self.visited_urls = set()
        self.pages = []  # List to store crawled pages
        
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
    
    def crawl_page(self, url, depth, base_url):
        """Crawl a single page and extract content"""
        if depth > self.max_depth or url in self.visited_urls or len(self.pages) >= self.max_pages:
            return
        
        logger.info(f"Crawling: {url} (depth: {depth})")
        self.visited_urls.add(url)
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Extract text content
            text_content = self.extract_text_content(url, response.text)
            
            # Add page to the list if content was extracted
            if text_content:
                self.pages.append({
                    'url': url,
                    'title': self._extract_title(response.text),
                    'content': text_content
                })
                logger.debug(f"Added page: {url}")
            
            # Extract links
            links = self.extract_links(base_url, response.text)
            
            # Add delay to avoid overwhelming the server
            time.sleep(self.request_delay)
            
            # Recursively crawl linked pages
            for link in links:
                if len(self.pages) >= self.max_pages:
                    logger.info(f"Reached maximum number of pages ({self.max_pages})")
                    break
                self.crawl_page(link, depth + 1, base_url)
            
        except requests.RequestException as e:
            logger.error(f"Error requesting {url}: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
    
    def _extract_title(self, html_content):
        """Extract title from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.text if title_tag else "No Title"
    
    def crawl(self, start_url):
        """Start the crawling process from a given URL"""
        self.visited_urls = set()
        self.pages = []
        
        # Validate the start URL
        try:
            response = requests.head(start_url, timeout=5)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error validating start URL {start_url}: {str(e)}")
            raise ValueError(f"Invalid start URL: {start_url}")
        
        # Start crawling
        logger.info(f"Starting crawl from {start_url} with max depth {self.max_depth} and max pages {self.max_pages}")
        self.crawl_page(start_url, 1, start_url)
        logger.info(f"Crawling completed. Crawled {len(self.pages)} pages.")
        
        return self.pages
