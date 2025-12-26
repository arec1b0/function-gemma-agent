from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """
    Abstract interface for Language Model providers.
    Defines the contract that any LLM implementation must follow.
    """
    
    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], tools_schema: List[Dict[str, Any]]) -> str:
        """
        Generate a response from the language model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            tools_schema: List of tool schemas available to the model
            
        Returns:
            Generated text response from the model
        """
        pass
