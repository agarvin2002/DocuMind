from analysis.exceptions import (
    AgentError,
    AnalysisJobNotFoundError,
    PlanningError,
    RetrievalAgentError,
    SynthesisError,
)
from core.exceptions import DocuMindError, NotFoundError


class TestAnalysisExceptions:
    def test_agent_error_is_documind_error(self):
        assert issubclass(AgentError, DocuMindError)
        assert AgentError.http_status_code == 500

    def test_planning_error_is_agent_error(self):
        assert issubclass(PlanningError, AgentError)
        assert PlanningError.http_status_code == 422

    def test_retrieval_agent_error_is_agent_error(self):
        assert issubclass(RetrievalAgentError, AgentError)
        assert RetrievalAgentError.http_status_code == 502

    def test_synthesis_error_is_agent_error(self):
        assert issubclass(SynthesisError, AgentError)
        assert SynthesisError.http_status_code == 502

    def test_analysis_job_not_found_is_not_found_error(self):
        assert issubclass(AnalysisJobNotFoundError, NotFoundError)
        assert AnalysisJobNotFoundError.http_status_code == 404

    def test_exceptions_are_instantiable(self):
        assert str(AgentError()) == AgentError.default_message
        assert str(PlanningError()) == PlanningError.default_message
        assert str(AnalysisJobNotFoundError()) == AnalysisJobNotFoundError.default_message


class TestTaskNameConstants:
    def test_run_analysis_job_constant_exists(self):
        from core.task_names import RUN_ANALYSIS_JOB
        assert RUN_ANALYSIS_JOB == "analysis.tasks.run_analysis_job"

    def test_ingest_document_constant_unchanged(self):
        from core.task_names import INGEST_DOCUMENT
        assert INGEST_DOCUMENT == "documents.tasks.ingest_document"
