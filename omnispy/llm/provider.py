"""Local LLM provider configuration for LightAgent.

Works with any OpenAI-compatible `/v1` endpoint — LM Studio on :1234 by
default, but Ollama, vLLM, llama.cpp, etc. all use the same wire format.
Just point `LLM_BASE_URL` and `LLM_MODEL` at whichever you have running.
"""

from omnispy.config import settings


def provider() -> dict:
    """Return the keyword arguments LightAgent expects for a local model."""
    return {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
    }