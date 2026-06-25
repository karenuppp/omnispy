"""Router agent + LightSwarm assembly.

The router is itself a LightAgent whose only job is to identify the target
platform from a natural-language query and delegate to the matching
specialist. Specialists are registered into a LightSwarm; the swarm handles
the delegation hop.
"""

from LightAgent import LightAgent, LightSwarm

from omnispy.llm.ollama import ollama_provider

from .x_agent import build_x_agent


ROUTER_NAME = "router"

ROUTER_ROLE = f"""You are the router agent for omnispy. Identify the target
social-media platform from the user's query and delegate to the appropriate
specialist agent.

Current specialists:
- x_agent: X / Twitter user timeline crawling (fetch_x_user_tweets)

For any X / Twitter request (e.g. "抓 @xxx 的推文", "get tweets from @xxx",
"fetch @xxx's recent posts"), call the `fetch_x_user_tweets` tool yourself
via the x_agent delegation — pass the original query unchanged so the
specialist can extract the handle. Do not ask the user clarifying questions
if the handle is present.

For any platform you don't recognize, reply that omnispy does not yet
support it and list the platforms that are available.
"""


def build_router() -> LightSwarm:
    """Construct the swarm with the router + all specialist agents registered."""
    router = LightAgent(name=ROUTER_NAME, role=ROUTER_ROLE, **ollama_provider())
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