"""omnispy CLI entry point.

Usage:
    python -m omnispy "抓 @elonmusk 最近 5 条推文"
"""

import typer

from omnispy.agents.router import run

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


if __name__ == "__main__":
    app()