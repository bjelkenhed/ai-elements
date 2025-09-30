import asyncio
import os
from agentic_blocks.agent import Agent
from agno.tools import tool
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))


@tool
def add(a: float, b: float) -> float:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b


@tool
def multiply(a: float, b: float) -> float:
    """Multiplies a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b


system_prompt = "You are a helpful assistant that can add numbers. Always use the add and multiply tool if you can."

agent = Agent(system_prompt=system_prompt, tools=[add, multiply])


async def run_agent():
    async for response in agent.run_stream_sse(
        "Add 2 and 2 and multiply the result by 5"
    ):
        print(response)


if __name__ == "__main__":
    asyncio.run(run_agent())
