"""Interactive X cookie fetcher.

Launches a non-headless Playwright browser window (Scrapling's own Chromium,
NOT your local browser).  You log into X manually, then *auth_token* and *ct0*
are saved to ``.env`` automatically.

Usage::

    python -m omnispy get-cookies
"""

import sys
from pathlib import Path
from typing import Optional

from scrapling.fetchers import StealthySession


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (where .env lives)."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / ".env").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def fetch_x_cookies(timeout_seconds: int = 300) -> dict[str, str]:
    """Launch a non-headless browser, let user log into X, grab cookies.

    Args:
        timeout_seconds: Max time to wait for the browser to open (default 5 min).

    Returns:
        Dict with ``auth_token`` and ``ct0`` keys.

    Raises:
        RuntimeError: On failure (cookies missing, browser error, etc.).
    """
    cookies: dict[str, str] = {}

    def _login_flow(page):
        nonlocal cookies

        page.set_default_timeout(30_000)

        # Navigate fresh — this handles the initial load
        page.goto("https://x.com/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)  # let JS redirect settle

        if "login" not in page.url:
            print("✅ 检测到已登录状态，直接获取 cookies …")
        else:
            print("=" * 60)
            print("  X Cookie 获取工具")
            print("=" * 60)
            print()
            print("一个独立的浏览器窗口已经打开。")
            print("这是 Playwright 自带的 Chromium，和你的本机浏览器完全隔离。")
            print()
            print("请在该窗口中登录 X（输入邮箱/用户名和密码）。")
            print("登录**完成**后，回到此终端按 Enter 键。")
            print()
            input("按 Enter 继续 …")

        # Extract essential cookies from the browser context
        for c in page.context.cookies():
            if c["name"] in ("auth_token", "ct0"):
                cookies[c["name"]] = c["value"]

        if "auth_token" not in cookies or "ct0" not in cookies:
            missing = [k for k in ("auth_token", "ct0") if k not in cookies]
            raise RuntimeError(
                f"未能获取到: {', '.join(missing)}。请确认已成功登录 X。"
            )

        print(f"✅ 成功获取 auth_token 和 ct0")

    try:
        with StealthySession(headless=False) as session:
            session.fetch(
                "https://x.com/login",
                page_action=_login_flow,
                network_idle=False,
                timeout=timeout_seconds * 1000,
                disable_resources=False,  # keep CSS/JS for login page UX
            )
    except Exception as exc:
        raise RuntimeError(f"浏览器操作失败: {exc}") from exc

    return cookies


def write_cookies_to_env(
    cookies: dict[str, str],
    env_path: Optional[Path] = None,
) -> Path:
    """Write ``X_COOKIE`` to ``.env``, preserving existing content.

    Args:
        cookies:  Dict with ``auth_token`` and ``ct0`` keys.
        env_path: Path to ``.env``.  Auto-detected from project root if ``None``.

    Returns:
        Path to the modified ``.env`` file.
    """
    if env_path is None:
        env_path = _find_project_root() / ".env"

    cookie_str = f'auth_token={cookies["auth_token"]}; ct0={cookies["ct0"]}'
    new_line = f'X_COOKIE="{cookie_str}"'

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        replaced = False
        new_lines: list[str] = []
        for line in lines:
            if line.strip().startswith("X_COOKIE") and not replaced:
                new_lines.append(new_line + "\n")
                replaced = True
            else:
                new_lines.append(line)

        if not replaced:
            trailing = "" if new_lines[-1].endswith("\n") else "\n"
            new_lines.append(trailing + new_line + "\n")

        env_path.write_text("".join(new_lines), encoding="utf-8")
    else:
        env_path.write_text(new_line + "\n", encoding="utf-8")

    return env_path
