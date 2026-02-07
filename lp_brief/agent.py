"""
LP Briefing Agent - Research and synthesis for LP-GP interactions.

This agent uses the Tavily Python SDK for advanced research capabilities
including web search, deep research, content extraction, site mapping, and crawling.
"""

# Load environment variables from .env file BEFORE other imports
from pathlib import Path
from dotenv import load_dotenv
import yaml

# Load .env from the lp_brief directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types

from lp_brief.core import instructions
from lp_brief.tools import TAVILY_TOOLS, format_brief_to_pdf


def _load_lp_thesis() -> str:
    """Load the LP's investment thesis from thesis.yaml and format for injection."""
    thesis_path = Path(__file__).parent / "core" / "sentinel_thesis.yaml"
    if not thesis_path.exists():
        return ""
    
    with open(thesis_path, "r") as f:
        thesis_data = yaml.safe_load(f)
    
    # Format the thesis as readable text for the agent
    thesis_text = "\n\n## LP Investment Thesis\n\n"
    thesis_text += "Use this thesis to identify Companies of Interest in the fund's portfolio.\n\n"
    thesis_text += "```yaml\n"
    thesis_text += yaml.dump(thesis_data, default_flow_style=False, allow_unicode=True, width=100)
    thesis_text += "```\n"
    
    return thesis_text


# Build complete instruction with LP thesis appended
_full_instruction = instructions.LP_BRIEFING_AGENT_INSTRUCTION + _load_lp_thesis()

# Note: Thinking planner disabled - was causing model to plan without acting
# thinking_planner = BuiltInPlanner(
#     thinking_config=types.ThinkingConfig(
#         include_thoughts=True
#     )
# )

# Single LP Briefing Agent - handles both research and synthesis
# Tavily tools for research + PDF formatter for output
root_agent = LlmAgent(
    name="lp_briefing_agent",
    model="gemini-3-pro-preview",
    instruction=_full_instruction,
    tools=TAVILY_TOOLS + [format_brief_to_pdf],
    description="LP briefing agent that researches VC funds and synthesizes findings into branded PDF reports",
)
