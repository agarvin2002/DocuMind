"""
Unit tests for the agent prompt templates in generation/prompts.py.
"""

import pytest

from generation.prompts import AGENT_PROMPTS, get_agent_prompt

_EXPECTED_KEYS = {
    "complexity_classifier",
    "query_decomposition",
    "sub_answer",
    "synthesis",
    "comparison",
    "contradiction_detection",
}


class TestAgentPrompts:
    def test_all_expected_keys_are_present(self):
        assert _EXPECTED_KEYS == set(AGENT_PROMPTS.keys())

    def test_get_agent_prompt_returns_string_for_each_key(self):
        for key in _EXPECTED_KEYS:
            result = get_agent_prompt(key)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_agent_prompt_raises_value_error_for_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown agent prompt key"):
            get_agent_prompt("nonexistent_key")

    def test_query_decomposition_prompt_contains_placeholder(self):
        # The query_decomposition prompt has an {n} placeholder for sub-question count
        prompt = get_agent_prompt("query_decomposition")
        assert "{n}" in prompt
        # Verify it formats correctly
        formatted = prompt.format(n=3)
        assert "3" in formatted

    def test_all_prompts_mention_documind_or_have_role(self):
        # Every prompt should establish a role for the LLM
        for key, prompt in AGENT_PROMPTS.items():
            assert any(word in prompt.lower() for word in ("you are", "documind")), (
                f"Prompt '{key}' does not establish an LLM role"
            )
