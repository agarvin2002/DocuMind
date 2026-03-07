"""Analysis app — custom exceptions."""

from core.exceptions import DocuMindError


class AgentError(DocuMindError):
    """Raised when an agent workflow fails."""
    default_message = "Agent execution failed."


class PlanningError(AgentError):
    """Raised when the query planner cannot decompose a question."""
    default_message = "Failed to plan query execution."
