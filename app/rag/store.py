import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from app.utils.logger import log

class VectorStore:
    """
    ChromaDB-based vector store for RAG implementation.
    Handles document storage, indexing, and retrieval.
    """
    
    def __init__(self, 
                 collection_name: str = "k8s_knowledge",
                 persist_directory: str = "./data/chroma",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize the vector store.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
            embedding_model: Sentence transformer model name
        """
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        log.info(f"Loaded embedding model: {embedding_model}")
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        log.info(f"Initialized vector store with {self.collection.count()} documents")
    
    def add_documents(self, documents: List[Dict[str, Any]], batch_size: int = 100):
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents with 'content', 'metadata', and optional 'id'
            batch_size: Number of documents to process at once
        """
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            ids = []
            contents = []
            metadatas = []
            
            for doc in batch:
                # Generate ID if not provided
                doc_id = doc.get('id', f"doc_{i}_{len(ids)}")
                ids.append(doc_id)
                contents.append(doc['content'])
                metadatas.append(doc.get('metadata', {}))
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(contents, convert_to_tensor=False)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=contents,
                metadatas=metadatas,
                embeddings=embeddings.tolist()
            )
            
            log.info(f"Added batch of {len(batch)} documents to vector store")
        
        log.info(f"Total documents in store: {self.collection.count()}")
    
    def load_from_directory(self, directory: str, file_pattern: str = "*.md"):
        """
        Load documents from a directory into the vector store.
        
        Args:
            directory: Directory containing documents
            file_pattern: Pattern to match files (default: *.md)
        """
        docs_path = Path(directory)
        if not docs_path.exists():
            log.warning(f"Directory {directory} does not exist")
            return
        
        documents = []
        for file_path in docs_path.glob(file_pattern):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Split content into chunks
            chunks = self._chunk_document(content, chunk_size=1000, overlap=200)
            
            for i, chunk in enumerate(chunks):
                documents.append({
                    'id': f"{file_path.stem}_{i}",
                    'content': chunk,
                    'metadata': {
                        'source': str(file_path),
                        'chunk_index': i,
                        'total_chunks': len(chunks)
                    }
                })
        
        if documents:
            self.add_documents(documents)
            log.info(f"Loaded {len(documents)} chunks from {directory}")
    
    def _chunk_document(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split document into overlapping chunks.
        
        Args:
            content: Document content
            chunk_size: Maximum chunk size
            overlap: Overlap between chunks
            
        Returns:
            List of document chunks
        """
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            
            # Try to break at sentence or paragraph
            if end < len(content):
                # Look for sentence end
                sentence_end = content.rfind('.', start, end)
                if sentence_end > start + chunk_size // 2:
                    end = sentence_end + 1
                else:
                    # Look for paragraph end
                    para_end = content.rfind('\n\n', start, end)
                    if para_end > start + chunk_size // 2:
                        end = para_end + 2
            
            chunks.append(content[start:end].strip())
            start = end - overlap
            
            if start >= len(content):
                break
        
        return chunks
    
    def search(self, query: str, top_k: int = 3, filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of relevant documents with scores
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query], convert_to_tensor=False)
        
        # Search in collection
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            where=filter_dict
        )
        
        # Format results
        documents = []
        for i in range(len(results['ids'][0])):
            documents.append({
                'id': results['ids'][0][i],
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'score': results['distances'][0][i]
            })
        
        log.info(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
        return documents
    
    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document if found, None otherwise
        """
        results = self.collection.get(ids=[doc_id])
        
        if results['ids']:
            return {
                'id': results['ids'][0],
                'content': results['documents'][0],
                'metadata': results['metadatas'][0]
            }
        return None
    
    def delete_collection(self):
        """Delete the entire collection."""
        self.client.delete_collection(self.collection_name)
        log.info(f"Deleted collection: {self.collection_name}")

# Global vector store instance
vector_store = VectorStore()
