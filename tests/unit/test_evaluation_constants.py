from evaluation import constants


class TestMetricThresholds:
    def test_faithfulness_threshold_is_float(self):
        assert isinstance(constants.FAITHFULNESS_THRESHOLD, float)

    def test_faithfulness_threshold_value(self):
        assert constants.FAITHFULNESS_THRESHOLD == 0.85

    def test_answer_relevancy_threshold_is_float(self):
        assert isinstance(constants.ANSWER_RELEVANCY_THRESHOLD, float)

    def test_answer_relevancy_threshold_value(self):
        assert constants.ANSWER_RELEVANCY_THRESHOLD == 0.80

    def test_context_recall_threshold_is_float(self):
        assert isinstance(constants.CONTEXT_RECALL_THRESHOLD, float)

    def test_context_recall_threshold_value(self):
        assert constants.CONTEXT_RECALL_THRESHOLD == 0.75

    def test_baseline_improvement_min_pct_is_float(self):
        assert isinstance(constants.BASELINE_IMPROVEMENT_MIN_PCT, float)

    def test_baseline_improvement_min_pct_value(self):
        assert constants.BASELINE_IMPROVEMENT_MIN_PCT == 20.0


class TestDatasetConfig:
    def test_eval_dataset_path_is_str(self):
        assert isinstance(constants.EVAL_DATASET_PATH, str)

    def test_eval_dataset_path_ends_with_json(self):
        assert constants.EVAL_DATASET_PATH.endswith(".json")

    def test_eval_dataset_size_is_int(self):
        assert isinstance(constants.EVAL_DATASET_SIZE, int)

    def test_eval_dataset_size_value(self):
        assert constants.EVAL_DATASET_SIZE == 50


class TestCacheConfig:
    def test_eval_cache_prefix_is_str(self):
        assert isinstance(constants.EVAL_CACHE_PREFIX, str)

    def test_eval_cache_prefix_starts_with_documind(self):
        assert constants.EVAL_CACHE_PREFIX.startswith("documind:")

    def test_eval_cache_ttl_is_int(self):
        assert isinstance(constants.EVAL_CACHE_TTL, int)

    def test_eval_cache_ttl_is_positive(self):
        assert constants.EVAL_CACHE_TTL > 0


class TestRagasConfig:
    def test_ragas_llm_model_is_str(self):
        assert isinstance(constants.RAGAS_LLM_MODEL, str)

    def test_ragas_judge_temperature_is_float(self):
        assert isinstance(constants.RAGAS_JUDGE_TEMPERATURE, float)

    def test_ragas_judge_temperature_is_zero(self):
        # Must be deterministic for reproducible scoring
        assert constants.RAGAS_JUDGE_TEMPERATURE == 0.0

    def test_ragas_judge_max_tokens_is_int(self):
        assert isinstance(constants.RAGAS_JUDGE_MAX_TOKENS, int)


class TestRetrievalConfig:
    def test_eval_system_k_is_int(self):
        assert isinstance(constants.EVAL_SYSTEM_K, int)

    def test_eval_baseline_k_is_int(self):
        assert isinstance(constants.EVAL_BASELINE_K, int)

    def test_system_and_baseline_k_are_equal(self):
        # Both systems must use the same k — otherwise the comparison is unfair
        assert constants.EVAL_SYSTEM_K == constants.EVAL_BASELINE_K


class TestConcurrencyConfig:
    def test_eval_max_workers_is_int(self):
        assert isinstance(constants.EVAL_MAX_WORKERS, int)

    def test_eval_max_workers_is_positive(self):
        assert constants.EVAL_MAX_WORKERS > 0
