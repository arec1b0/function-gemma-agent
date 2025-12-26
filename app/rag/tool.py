from typing import Dict, Any
from app.infrastructure.tools.base import BaseTool
from app.rag.retriever import knowledge_retriever
from app.utils.logger import log

class SearchKnowledgeBaseTool(BaseTool):
    """
    Tool for searching the internal knowledge base using RAG.
    Allows the agent to look up information from documentation.
    """
    
    name = "search_knowledge_base"
    description = "Search the internal knowledge base for information about Kubernetes, runbooks, and procedures"
    
    def __init__(self):
        super().__init__()
        self.retriever = knowledge_retriever
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get the parameters for this tool."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up in the knowledge base"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to retrieve (default: 3)",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    
    def execute(self, query: str, top_k: int = 3) -> str:
        """
        Execute the knowledge base search.
        
        Args:
            query: The search query
            top_k: Number of results to return
            
        Returns:
            Retrieved context with sources
        """
        log.info(f"Searching knowledge base with query: {query}")
        
        try:
            # Retrieve context with sources
            result = self.retriever.retrieve_with_sources(query, top_k=top_k)
            
            # Format the response
            response = f"Found the following information:\n\n{result['context']}\n\n"
            
            if result['sources']:
                response += "Sources:\n"
                for i, source in enumerate(result['sources']):
                    response += f"{i+1}. {source['source']} (relevance: {1 - source['score']:.2f})\n"
            
            return response
            
        except Exception as e:
            error_msg = f"Error searching knowledge base: {str(e)}"
            log.error(error_msg)
            return error_msg

# Register the tool
from app.infrastructure.tools import registry
registry.register_tool(SearchKnowledgeBaseTool())
