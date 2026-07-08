"""omnispy CLI entry point.

Usage:
    python -m omnispy "抓 @elonmusk 最近 5 条推文"     # LLM agent
    python -m omnispy search 香港                        # 直接搜索推文
    python -m omnispy search 香港 --since 2026-07-05    # 指定日期
    python -m omnispy search 香港 --until 2026-07-06 --limit 10
"""

import time

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


if __name__ == "__main__":
    app()
