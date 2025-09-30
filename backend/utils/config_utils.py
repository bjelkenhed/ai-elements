import os
from typing import Dict, Any


def get_llm_config() -> Dict[str, Any]:
    """Get LLM configuration from environment variables."""

    # Check for OpenRouter API key first
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return {
            "api_key": openrouter_key,
            "provider": "openrouter",
            "model": os.getenv("MODEL_ID", "qwen/qwen3-235b-a22b-2507")
        }

    # Fall back to OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return {
            "api_key": openai_key,
            "provider": "openai",
            "model": os.getenv("MODEL_ID", "gpt-4o")
        }

    # No API key found
    raise ValueError("No API key configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY environment variable.")