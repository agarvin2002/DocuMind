"""generation/constants.py — Named constants for the generation layer."""

# Token estimation heuristic (English text ≈ 4 characters per token)
CHARS_PER_TOKEN: int = 4

# Maximum characters to include in a citation quote field
CITATION_QUOTE_MAX_CHARS: int = 200

# Ollama requires a non-empty api_key in the OpenAI SDK — the value is ignored by Ollama
OLLAMA_DUMMY_API_KEY: str = "ollama"
