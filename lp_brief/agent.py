import os
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from lp_brief import agent_instructions


# MCPToolset instance using StreamableHTTPConnectionParams for remote MCP
tavily_toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp.tavily.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('TAVILY_API_KEY')}"
        }
    )
)

research_agent = LlmAgent(
    name="research_agent",
    model="gemini-2.5-flash",
    instruction=agent_instructions.RESEARCH_AGENT_INSTRUCTION,
    tools=[tavily_toolset],  # Pass MCPToolset directly, not .get_tools()
    description="Research agent that finds unfiltered truth about VC funds using Tavily search"
)
    

research_tool = AgentTool(agent=research_agent)
    
root_agent = LlmAgent(
    name="lp_briefing_orchestrator",
    model="gemini-2.5-pro",
    instruction=agent_instructions.ORCHESTRATOR_AGENT_INSTRUCTION,
    tools=[research_tool],
    description="Portfolio manager that synthesizes research into LP-specific briefings"
)
