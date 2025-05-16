import os
import logging
from flask import Flask, render_template, request, jsonify, session
from crawler import WebsiteCrawler
from rag import RAGSystem

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Initialize RAG system
rag_system = RAGSystem()

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/crawl', methods=['POST'])
def crawl_website():
    """Endpoint to start crawling a website"""
    data = request.json
    start_url = data.get('url')
    max_depth = int(data.get('max_depth', 3))
    max_pages = int(data.get('max_pages', 50))
    
    if not start_url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    
    try:
        # Create crawler and start crawling
        crawler = WebsiteCrawler(max_depth=max_depth, max_pages=max_pages)
        pages = crawler.crawl(start_url)
        
        # Index the pages in the RAG system
        rag_system.index_documents(pages)
        
        # Save crawler state to session
        session['crawled_url'] = start_url
        session['pages_count'] = len(pages)
        
        return jsonify({
            'success': True, 
            'message': f'Successfully crawled {len(pages)} pages from {start_url}',
            'pages_count': len(pages)
        })
    except Exception as e:
        logger.error(f"Error crawling website: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint to handle chat interactions"""
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    if not rag_system.has_documents():
        return jsonify({
            'success': False, 
            'error': 'No website has been crawled yet. Please crawl a website first.'
        }), 400
    
    try:
        # Generate response using RAG
        response = rag_system.generate_response(query)
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/status')
def status():
    """Get the current status of the system"""
    crawled_url = session.get('crawled_url', None)
    pages_count = session.get('pages_count', 0)
    
    return jsonify({
        'crawled_url': crawled_url,
        'pages_count': pages_count,
        'has_documents': rag_system.has_documents()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
