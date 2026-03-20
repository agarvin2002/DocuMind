import uuid

import pytest

from analysis.models import AnalysisJob


@pytest.mark.django_db
class TestAnalysisJobModel:
    def test_default_status_is_pending(self):
        job = AnalysisJob.objects.create(
            workflow_type=AnalysisJob.WorkflowType.MULTI_HOP,
            input_data={"question": "test", "document_ids": []},
        )
        assert job.status == AnalysisJob.Status.PENDING

    def test_uuid_primary_key_is_auto_generated(self):
        job = AnalysisJob.objects.create(
            workflow_type=AnalysisJob.WorkflowType.SIMPLE,
            input_data={},
        )
        assert isinstance(job.id, uuid.UUID)

    def test_workflow_type_choices_are_valid(self):
        valid_types = {c[0] for c in AnalysisJob.WorkflowType.choices}
        assert valid_types == {"multi_hop", "comparison", "contradiction", "simple"}

    def test_result_data_is_null_by_default(self):
        job = AnalysisJob.objects.create(
            workflow_type=AnalysisJob.WorkflowType.COMPARISON,
            input_data={},
        )
        assert job.result_data is None

    def test_str_representation(self):
        job = AnalysisJob(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            workflow_type=AnalysisJob.WorkflowType.MULTI_HOP,
            status=AnalysisJob.Status.PENDING,
        )
        result = str(job)
        assert "multi_hop" in result
        assert "pending" in result
