"""omnispy CLI entry point.

Usage:
    python -m omnispy "抓 @elonmusk 最近 5 条推文"     # LLM agent
    python -m omnispy search 香港                        # 直接搜索推文
    python -m omnispy search 香港 --since 2026-07-05    # 指定日期
    python -m omnispy search 香港 --until 2026-07-06 --limit 10
"""

import json
import time
from pathlib import Path

import typer

from omnispy.agents.router import run
from server.service import _multi_search

app = typer.Typer(help="omnispy: multi-platform social media scraping agent.")


@app.command()
def main(
    query: str = typer.Argument(
        ...,
        help="Natural language query, e.g. '抓 @elonmusk 最近 5 条推文'.",
    ),
):
    """Route a query to the matching platform agent and print the result."""
    typer.echo(run(query))


@app.command()
def search(
    keywords: str = typer.Argument(..., help="Search keywords, comma-separated."),
    since: str = typer.Option(None, help="Start date YYYY-MM-DD."),
    until: str = typer.Option(None, help="End date YYYY-MM-DD."),
    limit: int = typer.Option(20, help="Max tweets to return."),
    sort: str = typer.Option("latest", help="top or latest."),
):
    """Search X (Twitter) using multi-route search (4 routes per keyword)."""
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    typer.echo(f"搜索关键词: {kw_list}, 每条路由限 {limit} 条, 4 路并发 ...", err=True)
    t0 = time.time()
    results = _multi_search(keywords=kw_list, since=since, until=until, limit_per_route=limit)
    results = results[:limit]
    elapsed = time.time() - t0
    typer.echo(f"耗时 {elapsed:.0f}s, 实得 {len(results)} 条\n", err=True)

    typer.echo(f"\n找到 {len(results)} 条推文（关键词: {keywords}）\n")
    for i, t in enumerate(results, 1):
        typer.echo(f"{i:>3}. @{t['author']}  {t.get('time', '?')}")
        typer.echo(f"     {t['text'][:120]}{'…' if len(t['text']) > 120 else ''}")
        if t.get("url"):
            typer.echo(f"     {t['url']}")
        typer.echo()

    return results


@app.command()
def get_cookies():
    """Launch a browser to log into X and save cookies to .env."""
    from omnispy.platforms.x.get_cookies import fetch_x_cookies, write_cookies_to_env

    try:
        cookies = fetch_x_cookies()
    except RuntimeError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(code=1)

    env_path = write_cookies_to_env(cookies)
    typer.echo(f"✅ Cookies 已保存到 {env_path}")
    typer.echo("运行以下命令验证：")
    typer.echo("  uv run python -m omnispy timeline \"test\" --limit 1")


@app.command()
def timeline(
    handles: str = typer.Argument(..., help="X usernames, comma-separated, without @."),
    limit: int = typer.Option(5, help="Max tweets per user."),
    workers: int = typer.Option(3, help="Parallel browser instances for multi-user fetch."),
    output: Path = typer.Option(None, help="Output JSON file path (e.g. results.json)."),
):
    """Fetch the most recent posts from one or more X user timelines."""
    user_list = [h.strip().lstrip("@") for h in handles.split(",") if h.strip()]
    if not user_list:
        typer.echo("错误：未提供有效的用户名。", err=True)
        return []

    from server.service import run_manual_search

    t0 = time.time()
    results = run_manual_search("user", users=",".join(user_list), limit=limit, max_workers=workers)
    elapsed = time.time() - t0

    # Per-user status
    ok_users: set[str] = set()
    for t in results:
        h = t.get("handle") or ""
        if h:
            ok_users.add(h)
    for handle in user_list:
        if handle in ok_users:
            count = sum(1 for t in results if t.get("handle") == handle)
            typer.echo(f"  ✅ @{handle}: {count} 条", err=True)
        else:
            typer.echo(f"  ⚠️ @{handle}: 未获取到推文（可能用户不存在/无推文/抓取失败）", err=True)

    typer.echo(f"\n耗时 {elapsed:.0f}s, 共 {len(results)} 条推文\n", err=True)
    for i, t in enumerate(results, 1):
        h = t.get("handle", "")
        label = f"@{h}" if h else t.get("author", "?")
        typer.echo(f"{i:>3}. {label}  {t.get('time', '?')}")
        typer.echo(f"     {t['text'][:120]}{'…' if len(t['text']) > 120 else ''}")
        if t.get("url"):
            typer.echo(f"     {t['url']}")
        typer.echo()

    if output:
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        typer.echo(f"✅ 结果已保存到 {output}\n", err=True)

    return results


if __name__ == "__main__":
    app()
