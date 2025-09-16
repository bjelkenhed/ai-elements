"""
Configuration utilities for handling environment variables and API settings.
"""

import os
from typing import Dict, Optional

from dotenv import load_dotenv


def get_llm_config(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Get LLM configuration from environment variables and parameters.

    Args:
        api_key: Optional API key override
        model: Optional model override
        base_url: Optional base URL override

    Returns:
        Dict with resolved api_key, model, and base_url values

    Raises:
        ValueError: If no API key can be found and no base_url is provided
    """
    # Load environment variables from root .env.local
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
    load_dotenv(env_path)

    # Get API key - try parameter first, then environment variables
    resolved_api_key = api_key
    if not resolved_api_key:
        resolved_api_key = os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        resolved_api_key = os.getenv("OPENROUTER_API_KEY")

    # Get base URL and model from environment if not provided
    resolved_base_url = base_url or os.getenv("BASE_URL")
    resolved_model = model or os.getenv("MODEL_ID")

    # Validate configuration
    if not resolved_api_key and not resolved_base_url:
        raise ValueError(
            "API key not found. Set OPENROUTER_API_KEY or OPENAI_API_KEY environment variable or pass api_key parameter."
        )

    # Special handling for OpenRouter API keys
    if resolved_api_key and resolved_api_key.startswith("sk-or"):
        resolved_base_url = "https://openrouter.ai/api/v1"

    # Set default API key for local/custom endpoints
    if resolved_base_url and not resolved_api_key:
        resolved_api_key = "EMPTY"

    return {
        "api_key": resolved_api_key,
        "model": resolved_model,
        "base_url": resolved_base_url,
    }