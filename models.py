import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Website(db.Model):
    """Model for storing crawled websites"""
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(500))
    crawl_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    max_depth = db.Column(db.Integer, default=3)
    max_pages = db.Column(db.Integer, default=50)
    pages_count = db.Column(db.Integer, default=0)
    
    # Relationship with pages
    pages = db.relationship('Page', backref='website', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Website {self.url}>'


class Page(db.Model):
    """Model for storing crawled pages"""
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    crawl_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Foreign key relationship
    website_id = db.Column(db.Integer, db.ForeignKey('website.id'), nullable=False)
    
    # Relationship with chunks
    chunks = db.relationship('PageChunk', backref='page', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Page {self.url}>'


class PageChunk(db.Model):
    """Model for storing page content chunks for RAG"""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer)
    embedding_id = db.Column(db.String(100))  # ID used in the vector database
    
    # Foreign key relationship
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)
    
    def __repr__(self):
        return f'<PageChunk {self.id} for page {self.page_id}>'


class ChatSession(db.Model):
    """Model for storing chat sessions"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    website_id = db.Column(db.Integer, db.ForeignKey('website.id'), nullable=False)
    
    # Relationship with messages
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<ChatSession {self.id}>'


class ChatMessage(db.Model):
    """Model for storing chat messages"""
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', or 'system'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Foreign key relationship
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    
    def __repr__(self):
        return f'<ChatMessage {self.id} by {self.role}>'