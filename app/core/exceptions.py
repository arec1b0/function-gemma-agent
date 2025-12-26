class AgentException(Exception):
    """Base exception for the Agent application."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ModelLoadError(AgentException):
    """Raised when the LLM fails to load."""
    pass

class ToolExecutionError(AgentException):
    """Raised when an external tool execution fails."""
    pass

class InvalidSchemaError(AgentException):
    """Raised when the provided tool schema is invalid."""
    pass