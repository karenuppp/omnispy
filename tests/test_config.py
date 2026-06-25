"""Tests for omnispy.config.Settings."""

from omnispy.config import Settings, get_settings


ENV_VARS = (
    "X_COOKIE",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_API_KEY",
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
    assert s.ollama_base_url == "http://localhost:11434/v1"
    assert s.ollama_model == "qwen2.5:7b"
    assert s.ollama_api_key == "ollama"
    assert s.http_host == "127.0.0.1"
    assert s.http_port == 8000


def test_overrides_via_constructor(monkeypatch):
    _isolated_env(monkeypatch)
    s = Settings(
        _env_file=None,
        x_cookie="x",
        ollama_model="qwen2.5:14b",
        http_port=9000,
    )
    assert s.ollama_model == "qwen2.5:14b"
    assert s.http_port == 9000


def test_overrides_via_env_vars(monkeypatch):
    _isolated_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_MODEL", "deepseek-r1:7b")
    monkeypatch.setenv("HTTP_PORT", "8765")
    s = Settings(_env_file=None, x_cookie="x")
    assert s.ollama_model == "deepseek-r1:7b"
    assert s.http_port == 8765


def test_get_settings_is_cached():
    a = get_settings()
    b = get_settings()
    assert a is b