import os
import logging
import json
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self):
        """Initialize the RAG system with ChromaDB and OpenAI"""
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.openai_api_key)
        
        # Set up ChromaDB
        self.chroma_client = chromadb.Client()
        
        # Use OpenAI's embeddings
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.openai_api_key,
            model_name="text-embedding-ada-002"
        )
        
        # Create or get the collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="website_content",
            embedding_function=self.openai_ef
        )
        
        self.has_indexed = False
    
    def _chunk_text(self, text, chunk_size=1000, overlap=100):
        """Split text into overlapping chunks"""
        if not text:
            return []
            
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if len(chunk) > 200:  # Ignore very small chunks
                chunks.append(chunk)
        return chunks
    
    def index_documents(self, pages):
        """Index website pages into ChromaDB"""
        # Clear existing data by getting all IDs and deleting them
        try:
            collection_count = self.collection.count()
            if collection_count > 0:
                # Get all IDs to delete them properly
                results = self.collection.query(
                    query_texts=[""],  # Empty query to get all
                    n_results=collection_count
                )
                if results and 'ids' in results and results['ids']:
                    ids_to_delete = results['ids'][0]
                    if ids_to_delete:
                        self.collection.delete(ids=ids_to_delete)
                    else:
                        # Alternate approach - recreate collection
                        self.collection = self.chroma_client.get_or_create_collection(
                            name="website_content",
                            embedding_function=self.openai_ef
                        )
        except Exception as e:
            logger.warning(f"Error clearing previous data: {str(e)}")
            # Recreate collection as fallback
            self.collection = self.chroma_client.get_or_create_collection(
                name="website_content",
                embedding_function=self.openai_ef
            )
        
        documents = []
        metadatas = []
        ids = []
        
        doc_id = 0
        
        for page in pages:
            url = page['url']
            title = page['title']
            content = page['content']
            
            # Chunk the content
            chunks = self._chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                doc_id += 1
                chunk_id = f"doc_{doc_id}"
                
                documents.append(chunk)
                metadatas.append({
                    "url": url,
                    "title": title,
                    "chunk_index": i
                })
                ids.append(chunk_id)
        
        # Add documents to the collection in batches (if any)
        if documents:
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                end_idx = min(i + batch_size, len(documents))
                self.collection.add(
                    documents=documents[i:end_idx],
                    metadatas=metadatas[i:end_idx],
                    ids=ids[i:end_idx]
                )
                
            logger.info(f"Indexed {len(documents)} chunks from {len(pages)} pages")
            self.has_indexed = True
        else:
            logger.warning("No documents to index")
            self.has_indexed = False
    
    def has_documents(self):
        """Check if documents have been indexed"""
        return self.has_indexed and self.collection.count() > 0
    
    def retrieve_relevant_content(self, query, n_results=5):
        """Retrieve relevant content for a given query"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        contexts = []
        for doc, meta in zip(documents, metadatas):
            contexts.append({
                "content": doc,
                "url": meta["url"],
                "title": meta["title"]
            })
            
        return contexts
    
    def generate_response(self, query):
        """Generate a response for the query using RAG"""
        # Retrieve relevant contexts
        contexts = self.retrieve_relevant_content(query)
        
        if not contexts:
            return "I don't have enough information to answer that question based on the website content."
        
        # Prepare context for the model
        context_text = ""
        sources = []
        
        for i, ctx in enumerate(contexts):
            context_text += f"\nContext {i+1}:\n{ctx['content']}\n"
            if ctx['url'] not in sources:
                sources.append(ctx['url'])
        
        # Build the prompt
        system_prompt = """You are a helpful AI assistant that answers questions based on the website content provided. 
        Use ONLY the provided context to answer the question. If the information is not in the context, 
        say that you don't have enough information to answer the question. If you use information from the context,
        cite the source URL at the end of your response."""
        
        user_prompt = f"Question: {query}\n\nHere is the context from the website:{context_text}"
        
        try:
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content
            
            # Add sources if not already included in the response
            source_text = "\n\nSources:\n" + "\n".join(sources)
            if "Sources:" not in ai_response:
                ai_response += source_text
                
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return f"Error generating response: {str(e)}"
