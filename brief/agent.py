"""
LP Briefing Agent - Research and synthesis for LP-GP interactions.

This agent uses the Tavily Python SDK for advanced research capabilities
including web search, deep research, content extraction, site mapping, and crawling.
"""

# Load environment variables from .env file BEFORE other imports
from pathlib import Path
from dotenv import load_dotenv
import yaml
import time

# Load .env from the lp_brief directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types

from brief.core import instructions
from brief.tools import TAVILY_TOOLS, format_brief_to_pdf
from brief.tools.pdf_reader import extract_pdf_text
from brief.tools.pdf_formatter import format_memo_to_pdf


def collect_usage_callback(callback_context, llm_response):
    """Callback to collect token usage from LLM responses."""
    print(f"DEBUG CALLBACK: Called with llm_response: {llm_response is not None}")
    
    if llm_response and llm_response.usage_metadata:
        usage = llm_response.usage_metadata
        total_tokens = getattr(usage, 'total_token_count', 0) or 0
        print(f"DEBUG CALLBACK: Found {total_tokens} tokens in response")
        
        # Accumulate in session state
        current_total = callback_context.state.get('total_tokens_used', 0)
        new_total = current_total + total_tokens
        callback_context.state['total_tokens_used'] = new_total
        print(f"DEBUG CALLBACK: Updated total tokens to {new_total}")
        
        # Set start time if not set
        if 'generation_start_time' not in callback_context.state:
            start_time = time.time()
            callback_context.state['generation_start_time'] = start_time
            print(f"DEBUG CALLBACK: Set start time to {start_time}")
    
    return llm_response


def _load_investment_thesis() -> str:
    """Load the investment thesis from thesis.yaml and format for injection."""
    thesis_path = Path(__file__).parent / "core/thesis" / "sentinel_thesis.yaml"
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
fund_full_instruction = instructions.FUND_BRIEFING_AGENT_INSTRUCTION + _load_investment_thesis()
company_full_instruction = instructions.COMPANY_BRIEFING_AGENT_INSTRUCTION + _load_investment_thesis()

# Note: Thinking planner disabled - was causing model to plan without acting
# thinking_planner = BuiltInPlanner(
#     thinking_config=types.ThinkingConfig(
#         include_thoughts=True
#     )
# )

fund_agent = LlmAgent(
    name="fund_briefing_agent",
    model="gemini-3-pro-preview",
    instruction=fund_full_instruction,
    tools=TAVILY_TOOLS + [format_brief_to_pdf],
    description="Fund briefing agent that researches VC funds and synthesizes findings into branded PDF reports",
    after_model_callback=collect_usage_callback
)

company_agent = LlmAgent(
    name="company_briefing_agent",
    model="gemini-3-pro-preview",
    instruction=company_full_instruction,
    tools=TAVILY_TOOLS + [format_brief_to_pdf],
    description="Company briefing agent that researches companies and synthesizes findings into branded PDF reports",
    after_model_callback=collect_usage_callback
)


memo_agent = LlmAgent(
    name="memo_generator_agent",
    model="gemini-3-pro-preview",
    instruction=instructions.MEMO_AGENT_INSTRUCTION,
    tools=[extract_pdf_text, format_memo_to_pdf],
    description="Memo generator agent that reads PDF briefs and creates concise executive summaries",
    after_model_callback=collect_usage_callback
)

root_agent = LlmAgent(
    name="orchestrator_agent",
    model="gemini-3-pro-preview",
    instruction="""You are an orchestrator agent that handles LP briefing requests.

If the user provides a PDF file path (typically ending in .pdf), you are the memo generator:
- Call extract_pdf_text with the PDF path to read the brief
- Summarize the key points into a concise 1-2 page executive memo
- Call format_memo_to_pdf to generate the final PDF

Otherwise, for fund or company names:
- Determine whether it's a fund or company
- Use Tavily tools to research and gather information
- Generate comprehensive briefing document text
- Call format_brief_to_pdf to generate the final PDF

Your workflow depends on the input type.""",
    tools= TAVILY_TOOLS + [extract_pdf_text, format_memo_to_pdf, format_brief_to_pdf],
    sub_agents=[fund_agent, company_agent, memo_agent],
    after_model_callback=collect_usage_callback
)