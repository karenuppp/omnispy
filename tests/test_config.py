"""Tests for omnispy.config.Settings."""

from omnispy.config import Settings, get_settings


ENV_VARS = (
    "X_COOKIE",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "HTTP_HOST",
    "HTTP_PORT",
)


def _isolated_env(monkeypatch):
    """Strip all omnispy env vars so tests don't pick up the host shell."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_when_only_cookie_required(monkeypatch):
    _isolated_env(monkeypatch)
    s = Settings(_env_file=None, x_cookie="auth_token=abc; ct0=def")
    assert s.x_cookie == "auth_token=abc; ct0=def"
    assert s.llm_base_url == "http://localhost:1234/v1"
    assert s.llm_model == "gemma-4-e4b"
    assert s.llm_api_key == "lmstudio"
    assert s.http_host == "127.0.0.1"
    assert s.http_port == 8000


def test_overrides_via_constructor(monkeypatch):
    _isolated_env(monkeypatch)
    s = Settings(
        _env_file=None,
        x_cookie="x",
        llm_model="llama-3.1-8b",
        http_port=9000,
    )
    assert s.llm_model == "llama-3.1-8b"
    assert s.http_port == 9000


def test_overrides_via_env_vars(monkeypatch):
    _isolated_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "deepseek-r1:7b")
    monkeypatch.setenv("HTTP_PORT", "8765")
    s = Settings(_env_file=None, x_cookie="x")
    assert s.llm_model == "deepseek-r1:7b"
    assert s.http_port == 8765


def test_get_settings_is_cached():
    a = get_settings()
    b = get_settings()
    assert a is b