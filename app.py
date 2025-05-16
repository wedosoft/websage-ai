import os
import logging
import uuid
from flask import Flask, render_template, request, jsonify, session
from crawler import WebsiteCrawler
from rag import RAGSystem
from models import db, Website, Page, PageChunk, ChatSession, ChatMessage

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database
db.init_app(app)

# Initialize RAG system
rag_system = RAGSystem()

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

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
        # Create crawler and start crawling with a timeout to avoid worker timeout
        crawler = WebsiteCrawler(max_depth=max_depth, max_pages=max_pages, timeout=25)
        pages = crawler.crawl(start_url)
        
        # Store website info in database
        website = Website(
            url=start_url,
            title=pages[0]['title'] if pages else start_url,
            max_depth=max_depth,
            max_pages=max_pages,
            pages_count=len(pages)
        )
        db.session.add(website)
        db.session.commit()
        
        # Store each crawled page
        for page_data in pages:
            page = Page(
                url=page_data['url'],
                title=page_data['title'],
                content=page_data['content'],
                website_id=website.id
            )
            db.session.add(page)
        db.session.commit()
        
        # Index the pages in the RAG system
        rag_system.index_documents(pages)
        
        # Save crawler state to session
        session['crawled_url'] = start_url
        session['pages_count'] = len(pages)
        session['website_id'] = website.id
        
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
    
    try:
        # Check if we have documents to query
        has_docs = rag_system.has_documents()
        
        if not has_docs:
            # Try to load from database if RAG system doesn't have documents
            website_id = session.get('website_id')
            
            if website_id:
                # Get pages from the database
                pages = Page.query.filter_by(website_id=website_id).all()
                
                if pages:
                    # Format pages for RAG system
                    formatted_pages = []
                    for page in pages:
                        formatted_pages.append({
                            'url': page.url,
                            'title': page.title,
                            'content': page.content
                        })
                    
                    # Index the pages in the RAG system
                    rag_system.index_documents(formatted_pages)
                    has_docs = True
        
        if not has_docs:
            return jsonify({
                'success': False, 
                'error': 'No website has been crawled yet. Please crawl a website first.'
            }), 400
        
        # Get session ID or create a new one
        chat_session_id = session.get('chat_session_id')
        website_id = session.get('website_id')
        
        # Make sure we have a website ID
        if not website_id:
            # Try to get the most recent website
            latest_website = Website.query.order_by(Website.crawl_date.desc()).first()
            if latest_website:
                website_id = latest_website.id
                session['website_id'] = website_id
            else:
                return jsonify({
                    'success': False, 
                    'error': 'No website data available. Please crawl a website first.'
                }), 400
        
        # Create or get chat session
        chat_session = None
        if chat_session_id:
            chat_session = ChatSession.query.filter_by(session_id=chat_session_id).first()
        
        if not chat_session:
            # Create new session
            session_id = str(uuid.uuid4())
            chat_session = ChatSession(
                session_id=session_id,
                website_id=website_id
            )
            db.session.add(chat_session)
            db.session.commit()
            session['chat_session_id'] = session_id
        
        # Add user message to database
        user_message = ChatMessage(
            role='user',
            content=query,
            session_id=chat_session.id
        )
        db.session.add(user_message)
        db.session.commit()
        
        # Generate response using RAG
        response = rag_system.generate_response(query)
        
        # Store assistant response
        assistant_message = ChatMessage(
            role='assistant',
            content=response,
            session_id=chat_session.id
        )
        db.session.add(assistant_message)
        db.session.commit()
        
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/status')
def status():
    """Get the current status of the system"""
    crawled_url = session.get('crawled_url', None)
    pages_count = session.get('pages_count', 0)
    
    # Check database status
    has_websites = False
    try:
        has_websites = Website.query.count() > 0
    except Exception as e:
        logger.error(f"Error checking website count: {str(e)}")
    
    return jsonify({
        'crawled_url': crawled_url,
        'pages_count': pages_count,
        'has_documents': rag_system.has_documents() or has_websites
    })

@app.route('/history', methods=['GET'])
def chat_history():
    """Get chat history for the current session"""
    chat_session_id = session.get('chat_session_id')
    
    if not chat_session_id:
        return jsonify({
            'success': False,
            'error': 'No active chat session'
        }), 404
    
    try:
        chat_session = ChatSession.query.filter_by(session_id=chat_session_id).first()
        
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Chat session not found'
            }), 404
        
        # Get messages
        messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.timestamp).all()
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            })
        
        return jsonify({
            'success': True,
            'messages': formatted_messages
        })
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/websites', methods=['GET'])
def get_websites():
    """Get list of crawled websites"""
    try:
        websites = Website.query.order_by(Website.crawl_date.desc()).all()
        
        # Format websites
        formatted_websites = []
        for website in websites:
            formatted_websites.append({
                'id': website.id,
                'url': website.url,
                'title': website.title,
                'crawl_date': website.crawl_date.isoformat(),
                'pages_count': website.pages_count
            })
        
        return jsonify({
            'success': True,
            'websites': formatted_websites
        })
    except Exception as e:
        logger.error(f"Error retrieving websites: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)