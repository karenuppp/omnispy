"""Router agent + LightSwarm assembly.

The router is itself a LightAgent whose only job is to identify the target
platform from a natural-language query and delegate to the matching
specialist. Specialists are registered into a LightSwarm; the swarm handles
the delegation hop.
"""

from LightAgent import LightAgent, LightSwarm

from omnispy.llm.provider import provider

from .x_agent import build_x_agent


ROUTER_NAME = "router"
ROUTER_INSTRUCTIONS = (
    "Router agent: identifies the target platform from user queries and "
    "delegates to the appropriate specialist agent. Does NOT handle "
    "requests directly."
)

ROUTER_ROLE = f"""You are the router agent for omnispy. Identify the target
social-media platform from the user's query and delegate to the appropriate
specialist agent.

Current specialists:
- x_agent: X / Twitter crawling (fetch_x_user_tweets + search_x_tweets)

For any X / Twitter request, delegate to x_agent with the original query.
Examples of X requests:
- Fetching a user's tweets ("抓 @xxx 的推文", "get @xxx's recent posts")
- Searching by keyword ("搜索关于香港的热帖", "find tweets about AI")
- Combined ("找 @a 和 @b 的帖", "@a 发了哪些关于 AI 的内容")

Do not ask the user clarifying questions if the platform is clear.
For any platform you don't recognize, reply that omnispy does not yet
support it and list the platforms that are available.
"""


def build_router() -> LightSwarm:
    """Construct the swarm with the router + all specialist agents registered."""
    router = LightAgent(name=ROUTER_NAME, instructions=ROUTER_INSTRUCTIONS, role=ROUTER_ROLE, **provider())
    swarm = LightSwarm()
    swarm.register_agent(router, build_x_agent())
    return swarm


def run(query: str) -> str:
    """Build a fresh swarm and route the query through it.

    A fresh swarm is built per call so settings changes (model swap, new
    specialist) take effect without restarting the process.
    """
    swarm = build_router()
    return swarm.run(agent=swarm.agents[ROUTER_NAME], query=query)