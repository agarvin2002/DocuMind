import json

import pytest

from evaluation.datasets import EvalDatasetLoader, EvalSample
from evaluation.exceptions import DatasetLoadError


@pytest.fixture
def valid_dataset(tmp_path):
    data = {
        "version": "1.0",
        "samples": [
            {
                "question": "What is RAG?",
                "ground_truth": "RAG stands for Retrieval Augmented Generation.",
                "document_id": "",
                "document_title": "ai_concepts",
                "tags": ["factual"],
            },
            {
                "question": "What is the rate limit?",
                "ground_truth": "100 requests per day.",
                "document_id": "abc-123",
                "document_title": "product_spec",
                "tags": ["factual", "comparison"],
            },
        ],
    }
    p = tmp_path / "qa_pairs.json"
    p.write_text(json.dumps(data))
    return str(p)


@pytest.fixture
def loader():
    return EvalDatasetLoader()


class TestEvalDatasetLoaderValidLoad:
    def test_returns_list_of_eval_samples(self, loader, valid_dataset):
        samples = loader.load(valid_dataset)
        assert isinstance(samples, list)
        assert all(isinstance(s, EvalSample) for s in samples)

    def test_returns_correct_count(self, loader, valid_dataset):
        samples = loader.load(valid_dataset)
        assert len(samples) == 2

    def test_sample_fields_are_populated(self, loader, valid_dataset):
        samples = loader.load(valid_dataset)
        s = samples[0]
        assert s.question == "What is RAG?"
        assert s.ground_truth == "RAG stands for Retrieval Augmented Generation."
        assert s.document_title == "ai_concepts"
        assert s.tags == ("factual",)

    def test_tags_stored_as_tuple(self, loader, valid_dataset):
        samples = loader.load(valid_dataset)
        assert isinstance(samples[1].tags, tuple)

    def test_sample_is_immutable(self, loader, valid_dataset):
        samples = loader.load(valid_dataset)
        with pytest.raises((AttributeError, TypeError)):
            samples[0].question = "changed"  # type: ignore[misc]


class TestEvalDatasetLoaderErrors:
    def test_missing_file_raises_dataset_load_error(self, loader, tmp_path):
        with pytest.raises(DatasetLoadError, match="not found"):
            loader.load(str(tmp_path / "nonexistent.json"))

    def test_malformed_json_raises_dataset_load_error(self, loader, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        with pytest.raises(DatasetLoadError, match="invalid JSON"):
            loader.load(str(bad))

    def test_wrong_version_raises_dataset_load_error(self, loader, tmp_path):
        data = {"version": "2.0", "samples": []}
        p = tmp_path / "qa.json"
        p.write_text(json.dumps(data))
        with pytest.raises(DatasetLoadError, match="Unsupported dataset version"):
            loader.load(str(p))

    def test_empty_samples_raises_dataset_load_error(self, loader, tmp_path):
        data = {"version": "1.0", "samples": []}
        p = tmp_path / "qa.json"
        p.write_text(json.dumps(data))
        with pytest.raises(DatasetLoadError, match="no samples"):
            loader.load(str(p))

    def test_missing_required_field_raises_dataset_load_error(self, loader, tmp_path):
        data = {
            "version": "1.0",
            "samples": [{"question": "q?", "ground_truth": "gt"}],  # missing fields
        }
        p = tmp_path / "qa.json"
        p.write_text(json.dumps(data))
        with pytest.raises(DatasetLoadError, match="missing required fields"):
            loader.load(str(p))

    def test_empty_question_raises_dataset_load_error(self, loader, tmp_path):
        data = {
            "version": "1.0",
            "samples": [
                {
                    "question": "   ",
                    "ground_truth": "some answer",
                    "document_id": "",
                    "document_title": "doc",
                    "tags": [],
                }
            ],
        }
        p = tmp_path / "qa.json"
        p.write_text(json.dumps(data))
        with pytest.raises(DatasetLoadError, match="empty question"):
            loader.load(str(p))

    def test_empty_ground_truth_raises_dataset_load_error(self, loader, tmp_path):
        data = {
            "version": "1.0",
            "samples": [
                {
                    "question": "What is X?",
                    "ground_truth": "",
                    "document_id": "",
                    "document_title": "doc",
                    "tags": [],
                }
            ],
        }
        p = tmp_path / "qa.json"
        p.write_text(json.dumps(data))
        with pytest.raises(DatasetLoadError, match="empty ground_truth"):
            loader.load(str(p))
