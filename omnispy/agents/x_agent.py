"""X (Twitter) specialist agent."""

from LightAgent import LightAgent

from omnispy.llm.provider import provider
from omnispy.platforms.x.tools import fetch_x_user_tweets


X_AGENT_ROLE = """You are x_agent, the X (Twitter) specialist in the omnispy swarm.

Use the `fetch_x_user_tweets` tool to retrieve tweets for the requested
username. Always pass the handle *without* the leading `@` (the tool strips
it if present). Return the raw tweet text and timestamp directly to the
caller — do not summarize, filter, or editorialize unless explicitly asked.
"""


def build_x_agent() -> LightAgent:
    return LightAgent(
        name="x_agent",
        role=X_AGENT_ROLE,
        tools=[fetch_x_user_tweets],
        **provider(),
    )