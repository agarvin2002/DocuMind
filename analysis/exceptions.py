from core.exceptions import DocuMindError, NotFoundError


class AgentError(DocuMindError):
    default_message = "Agent execution failed."
    http_status_code = 500


class PlanningError(AgentError):
    default_message = "Failed to decompose query into sub-questions."
    http_status_code = 422


class RetrievalAgentError(AgentError):
    default_message = "Agent retrieval step failed."
    http_status_code = 502


class SynthesisError(AgentError):
    default_message = "Agent synthesis step failed."
    http_status_code = 502


class AnalysisJobNotFoundError(NotFoundError):
    default_message = "Analysis job not found."
    http_status_code = 404
