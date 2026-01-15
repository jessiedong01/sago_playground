"""
LP Briefing Agent - Research and synthesis for LP-GP interactions.

This agent uses the Tavily Python SDK for advanced research capabilities
including web search, deep research, content extraction, site mapping, and crawling.
"""

# Load environment variables from .env file BEFORE other imports
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the lp_brief directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types

from lp_brief import agent_instructions
from lp_brief.tavily_toolbox import TAVILY_TOOLS
from lp_brief.pdf_formatter import format_brief_to_pdf

# Enable thinking/reasoning for deeper analysis
thinking_planner = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(
        include_thoughts=True  # Shows the model's internal reasoning
    )
)

# Single LP Briefing Agent - handles both research and synthesis
# Tavily tools for research + PDF formatter for output
root_agent = LlmAgent(
    name="lp_briefing_agent",
    model="gemini-3-pro-preview",
    instruction=agent_instructions.LP_BRIEFING_AGENT_INSTRUCTION,
    tools=TAVILY_TOOLS + [format_brief_to_pdf],
    description="LP briefing agent that researches VC funds and synthesizes findings into branded PDF reports",
    planner=thinking_planner,
)
