import pytest

from core.exceptions import DocuMindError
from evaluation.exceptions import (
    BaselineError,
    DatasetLoadError,
    EvaluationError,
    MetricComputeError,
)


class TestEvaluationError:
    def test_is_subclass_of_documind_error(self):
        assert issubclass(EvaluationError, DocuMindError)

    def test_http_status_code(self):
        assert EvaluationError.http_status_code == 500

    def test_instantiation_with_message(self):
        exc = EvaluationError("something went wrong")
        assert exc.message == "something went wrong"

    def test_instantiation_without_message_uses_default(self):
        exc = EvaluationError()
        assert exc.message == EvaluationError.default_message


class TestDatasetLoadError:
    def test_is_subclass_of_evaluation_error(self):
        assert issubclass(DatasetLoadError, EvaluationError)

    def test_is_subclass_of_documind_error(self):
        assert issubclass(DatasetLoadError, DocuMindError)

    def test_http_status_code(self):
        assert DatasetLoadError.http_status_code == 422

    def test_instantiation_with_message(self):
        exc = DatasetLoadError("qa_pairs.json not found")
        assert exc.message == "qa_pairs.json not found"

    def test_can_be_caught_as_evaluation_error(self):
        with pytest.raises(EvaluationError):
            raise DatasetLoadError("missing file")


class TestMetricComputeError:
    def test_is_subclass_of_evaluation_error(self):
        assert issubclass(MetricComputeError, EvaluationError)

    def test_is_subclass_of_documind_error(self):
        assert issubclass(MetricComputeError, DocuMindError)

    def test_http_status_code(self):
        assert MetricComputeError.http_status_code == 502

    def test_instantiation_with_message(self):
        exc = MetricComputeError("RAGAS judge LLM timed out")
        assert exc.message == "RAGAS judge LLM timed out"

    def test_can_be_caught_as_evaluation_error(self):
        with pytest.raises(EvaluationError):
            raise MetricComputeError("LLM failed")


class TestBaselineError:
    def test_is_subclass_of_evaluation_error(self):
        assert issubclass(BaselineError, EvaluationError)

    def test_is_subclass_of_documind_error(self):
        assert issubclass(BaselineError, DocuMindError)

    def test_http_status_code(self):
        assert BaselineError.http_status_code == 500

    def test_instantiation_with_message(self):
        exc = BaselineError("baseline retrieval failed")
        assert exc.message == "baseline retrieval failed"

    def test_can_be_caught_as_evaluation_error(self):
        with pytest.raises(EvaluationError):
            raise BaselineError("baseline crashed")
