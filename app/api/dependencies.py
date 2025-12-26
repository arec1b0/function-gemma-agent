from typing import Generator
from app.domain.agent import AgentService, agent_service

def get_agent_service() -> Generator[AgentService, None, None]:
    """
    Dependency provider for the Agent Service.
    Allows for easy mocking during tests.
    """
    yield agent_service