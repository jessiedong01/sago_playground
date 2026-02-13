"""
LP Briefing Agent - Research and synthesis for LP-GP interactions.

This package provides an AI agent that researches venture funds and 
synthesizes findings into comprehensive briefing documents for LPs.
"""

from . import agent
from .core import instructions
from .tools import TAVILY_TOOLS, format_brief_to_pdf

__all__ = [
    "agent",
    "instructions",
    "TAVILY_TOOLS",
    "format_brief_to_pdf",
]