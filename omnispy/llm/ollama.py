"""Ollama provider configuration for LightAgent.

Ollama serves an OpenAI-compatible `/v1` endpoint. LightAgent accepts the
`model`, `api_key`, and `base_url` triple directly; this module just
centralizes construction so agent modules don't repeat it.
"""

from omnispy.config import settings


def ollama_provider() -> dict:
    """Return the keyword arguments LightAgent expects for an Ollama-backed model."""
    return {
        "model": settings.ollama_model,
        "api_key": settings.ollama_api_key,
        "base_url": settings.ollama_base_url,
    }