import json
import tempfile
from pathlib import Path

from evaluation.harness import EvalResult
from evaluation.metrics import MetricResult
from evaluation.reports import (
    generate_json_report,
    generate_markdown_report,
    save_report,
)

# --- helpers ---

def _make_result(verdict: str = "PASS") -> EvalResult:
    full = MetricResult(faithfulness=0.90, answer_relevancy=0.85, context_recall=0.80, sample_count=10, passed=True)
    base = MetricResult(faithfulness=0.72, answer_relevancy=0.68, context_recall=0.61, sample_count=10, passed=False)
    return EvalResult(
        full_system=full,
        baseline=base,
        improvements_pct={"faithfulness": 25.0, "answer_relevancy": 25.0, "context_recall": 31.1},
        verdict=verdict,
        dataset_size=10,
    )


# --- generate_json_report ---

class TestGenerateJsonReport:
    def test_output_is_valid_json(self):
        result = _make_result()
        raw = generate_json_report(result)
        parsed = json.loads(raw)  # raises if invalid
        assert isinstance(parsed, dict)

    def test_contains_all_top_level_keys(self):
        result = _make_result()
        parsed = json.loads(generate_json_report(result))
        for key in ("run_at", "verdict", "dataset_size", "full_system", "baseline", "improvements_pct", "thresholds"):
            assert key in parsed, f"Missing key: {key}"

    def test_verdict_matches_result(self):
        parsed = json.loads(generate_json_report(_make_result("FAIL")))
        assert parsed["verdict"] == "FAIL"

    def test_thresholds_block_present(self):
        parsed = json.loads(generate_json_report(_make_result()))
        thresholds = parsed["thresholds"]
        assert "faithfulness_min" in thresholds
        assert "improvement_min_pct" in thresholds


# --- generate_markdown_report ---

class TestGenerateMarkdownReport:
    def test_contains_verdict(self):
        md = generate_markdown_report(_make_result("PASS"))
        assert "PASS" in md

    def test_contains_fail_verdict(self):
        md = generate_markdown_report(_make_result("FAIL"))
        assert "FAIL" in md

    def test_contains_metric_table_headers(self):
        md = generate_markdown_report(_make_result())
        assert "Faithfulness" in md
        assert "Answer Relevancy" in md
        assert "Context Recall" in md


# --- save_report ---

class TestSaveReport:
    def test_returns_two_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = save_report(_make_result(), output_dir=tmp)
            assert isinstance(json_path, Path)
            assert isinstance(md_path, Path)

    def test_files_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = save_report(_make_result(), output_dir=tmp)
            assert json_path.exists()
            assert md_path.exists()

    def test_output_dir_created_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "nested" / "reports"
            save_report(_make_result(), output_dir=str(new_dir))
            assert new_dir.exists()

    def test_json_file_content_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path, _ = save_report(_make_result(), output_dir=tmp)
            parsed = json.loads(json_path.read_text())
            assert parsed["verdict"] == "PASS"
