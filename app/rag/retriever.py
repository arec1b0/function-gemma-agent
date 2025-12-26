from typing import List, Dict, Any, Optional
from app.rag.store import vector_store
from app.utils.logger import log

class KnowledgeRetriever:
    """
    Retrieval component for RAG pipeline.
    Handles query processing and context formatting.
    """
    
    def __init__(self, max_context_length: int = 2000):
        """
        Initialize the retriever.
        
        Args:
            max_context_length: Maximum length of retrieved context
        """
        self.max_context_length = max_context_length
    
    def retrieve_context(self, 
                        query: str, 
                        top_k: int = 3, 
                        filter_dict: Optional[Dict] = None) -> str:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: The search query
            top_k: Number of documents to retrieve
            filter_dict: Optional metadata filters
            
        Returns:
            Formatted context string
        """
        # Search for relevant documents
        documents = vector_store.search(query, top_k=top_k, filter_dict=filter_dict)
        
        if not documents:
            log.warning(f"No documents found for query: {query}")
            return "No relevant information found in the knowledge base."
        
        # Format context
        context_parts = []
        current_length = 0
        
        for i, doc in enumerate(documents):
            # Truncate content if needed
            content = doc['content']
            if current_length + len(content) > self.max_context_length:
                remaining = self.max_context_length - current_length - 50  # Leave room for truncation notice
                content = content[:remaining] + "...\n[Content truncated]"
            
            context_parts.append(
                f"[Source {i+1}]: {content}\n"
                f"(Relevance: {1 - doc['score']:.2f}, Source: {doc['metadata'].get('source', 'Unknown')})"
            )
            current_length += len(content)
            
            if current_length >= self.max_context_length:
                break
        
        context = "\n\n".join(context_parts)
        
        log.info(f"Retrieved context for query: {query[:50]}..., "
                f"documents: {len(documents)}, context length: {len(context)}")
        
        return context
    
    def retrieve_with_sources(self, 
                             query: str, 
                             top_k: int = 3) -> Dict[str, Any]:
        """
        Retrieve context with source information.
        
        Args:
            query: The search query
            top_k: Number of documents to retrieve
            
        Returns:
            Dictionary with context and sources
        """
        documents = vector_store.search(query, top_k=top_k)
        
        if not documents:
            return {
                'context': 'No relevant information found.',
                'sources': []
            }
        
        # Build context
        context_parts = []
        sources = []
        
        for i, doc in enumerate(documents):
            context_parts.append(f"[Document {i+1}]: {doc['content']}")
            
            sources.append({
                'id': doc['id'],
                'source': doc['metadata'].get('source', 'Unknown'),
                'score': doc['score']
            })
        
        return {
            'context': '\n\n'.join(context_parts),
            'sources': sources
        }
    
    def search_by_source(self, 
                        query: str, 
                        source: str, 
                        top_k: int = 3) -> str:
        """
        Search within a specific source document.
        
        Args:
            query: The search query
            source: Source file or identifier
            top_k: Number of results
            
        Returns:
            Formatted context from the specific source
        """
        filter_dict = {'source': source}
        return self.retrieve_context(query, top_k=top_k, filter_dict=filter_dict)
    
    def get_relevant_snippets(self, 
                             query: str, 
                             snippet_size: int = 300) -> List[str]:
        """
        Get short relevant snippets for quick reference.
        
        Args:
            query: The search query
            snippet_size: Maximum size of each snippet
            
        Returns:
            List of text snippets
        """
        documents = vector_store.search(query, top_k=5)
        
        snippets = []
        for doc in documents:
            content = doc['content']
            
            # Find most relevant part (simple keyword matching for now)
            query_words = query.lower().split()
            best_start = 0
            best_score = 0
            
            for i in range(len(content) - snippet_size):
                snippet = content[i:i + snippet_size]
                score = sum(1 for word in query_words if word in snippet.lower())
                
                if score > best_score:
                    best_score = score
                    best_start = i
            
            snippet = content[best_start:best_start + snippet_size]
            if best_start > 0:
                snippet = "..." + snippet
            if best_start + snippet_size < len(content):
                snippet = snippet + "..."
            
            snippets.append(snippet)
        
        return snippets

# Global retriever instance
knowledge_retriever = KnowledgeRetriever()
