"""
TavilyToolbox - A comprehensive async wrapper for the Tavily Python SDK.

This module provides a clean interface to Tavily's advanced search capabilities
including web search, deep research, content extraction, site mapping, and crawling.
"""

import os
import json
import asyncio
from typing import Optional
from dataclasses import dataclass

# #region agent log
def _debug_print(tag: str, msg: str, data: dict = None):
    import sys
    print(f"\n[DEBUG {tag}] {msg}", file=sys.stderr, flush=True)
    if data:
        for k, v in data.items():
            print(f"  {k}: {str(v)[:200]}", file=sys.stderr, flush=True)
# #endregion

from tavily import (
    AsyncTavilyClient,
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)


@dataclass
class TavilyResult:
    """Structured result from Tavily operations."""
    success: bool
    data: str  # Markdown or JSON string for LLM consumption
    error: Optional[str] = None


class TavilyToolbox:
    """
    Async toolbox providing full access to Tavily's research capabilities.
    
    Use cases:
    - web_search: Quick factual queries, recent news, surface-level info
    - deep_research: Complex multi-step analysis requiring synthesis
    - extract_content: When you have specific URLs to parse
    - map_site: Discover structure of a domain before crawling
    - crawl_site: Systematically gather data based on intent
    
    Example:
        toolbox = TavilyToolbox()
        result = await toolbox.web_search("Sequoia Capital latest fund size")
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Tavily toolbox.
        
        Args:
            api_key: Tavily API key. Falls back to TAVILY_API_KEY env var.
        
        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        # #region agent log
        _debug_print("INIT", "API key check", {"api_key_present": bool(self._api_key), "api_key_length": len(self._api_key) if self._api_key else 0})
        # #endregion
        if not self._api_key:
            raise ValueError(
                "Tavily API key required. Set TAVILY_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._client = AsyncTavilyClient(api_key=self._api_key)
    
    async def web_search(
        self,
        query: str,
        depth: str = "advanced",
        max_results: int = 5,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
    ) -> TavilyResult:
        """
        Perform a web search for quick facts and recent information.
        
        Best for:
        - Current news and announcements
        - Quick factual lookups
        - Surface-level research on topics
        - Finding recent articles about a subject
        
        Args:
            query: The search query (be specific for better results).
            depth: "basic" for speed, "advanced" for comprehensive results.
            max_results: Number of results to return (1-20).
            include_domains: Optional list of domains to search within.
            exclude_domains: Optional list of domains to exclude.
        
        Returns:
            TavilyResult with markdown-formatted search results.
        """
        # #region agent log
        _debug_print("WEB_SEARCH", f"Called with query: {query[:80]}...")
        # #endregion
        try:
            response = await self._client.search(
                query=query,
                search_depth=depth,
                max_results=max_results,
                include_domains=include_domains or [],
                exclude_domains=exclude_domains or [],
                include_answer=True,
                include_raw_content=False,
            )
            # #region agent log
            _debug_print("WEB_SEARCH", "Got API response", {"response_keys": list(response.keys()) if isinstance(response, dict) else "not_dict", "num_results": len(response.get("results", []))})
            # #endregion
            
            # Format results as clean markdown for LLM consumption
            markdown = self._format_search_results(query, response)
            # #region agent log
            _debug_print("WEB_SEARCH", f"Formatted markdown length: {len(markdown)}")
            # #endregion
            return TavilyResult(success=True, data=markdown)
            
        except (BadRequestError, InvalidAPIKeyError, UsageLimitExceededError) as e:
            # #region agent log
            _debug_print("WEB_SEARCH", f"API ERROR: {type(e).__name__}: {e}")
            # #endregion
            return self._handle_error("web_search", e)
        except Exception as e:
            # #region agent log
            _debug_print("WEB_SEARCH", f"UNEXPECTED ERROR: {type(e).__name__}: {e}")
            # #endregion
            return TavilyResult(
                success=False,
                data="",
                error=f"Unexpected error in web_search: {str(e)}"
            )
    
    async def deep_research(
        self,
        query: str,
        max_depth: int = 3,
        max_breadth: int = 3,
    ) -> TavilyResult:
        """
        Conduct autonomous multi-step research for complex topics.
        
        Best for:
        - Deep dives requiring multiple searches
        - Topics needing synthesis from various sources
        - Comprehensive background research
        - When you need a full report, not just facts
        
        This uses Tavily's research model which autonomously:
        1. Plans the research approach
        2. Executes multiple searches
        3. Synthesizes findings into a coherent report
        
        Args:
            query: The research question or topic.
            max_depth: How deep to go in follow-up queries (1-5).
            max_breadth: How many parallel paths to explore (1-5).
        
        Returns:
            TavilyResult with a comprehensive research report in markdown.
        """
        # #region agent log
        _debug_print("DEEP_RESEARCH", f"Called with query: {query[:80]}...")
        # #endregion
        try:
            response = await self._client.research(
                query=query,
                model="pro",
                max_depth=max_depth,
                max_breadth=max_breadth,
            )
            # #region agent log
            _debug_print("DEEP_RESEARCH", "Got API response", {"response_keys": list(response.keys()) if isinstance(response, dict) else "not_dict"})
            # #endregion
            
            # The research endpoint returns a structured report
            markdown = self._format_research_report(query, response)
            # #region agent log
            _debug_print("DEEP_RESEARCH", f"Formatted markdown length: {len(markdown)}")
            # #endregion
            return TavilyResult(success=True, data=markdown)
            
        except (BadRequestError, InvalidAPIKeyError, UsageLimitExceededError) as e:
            # #region agent log
            _debug_print("DEEP_RESEARCH", f"API ERROR: {type(e).__name__}: {e}")
            # #endregion
            return self._handle_error("deep_research", e)
        except Exception as e:
            # #region agent log
            _debug_print("DEEP_RESEARCH", f"UNEXPECTED ERROR: {type(e).__name__}: {e}")
            # #endregion
            return TavilyResult(
                success=False,
                data="",
                error=f"Unexpected error in deep_research: {str(e)}"
            )
    
    async def extract_content(
        self,
        urls: list[str],
        query: Optional[str] = None,
    ) -> TavilyResult:
        """
        Extract and parse content from specific URLs.
        
        Best for:
        - When you already have URLs from search results
        - Parsing complex pages (PDFs, JavaScript-heavy sites)
        - Extracting structured data from known sources
        - Getting full article text from news sites
        
        Args:
            urls: List of URLs to extract content from (max 10).
            query: Optional focus query to filter relevant content.
        
        Returns:
            TavilyResult with extracted content in markdown format.
        """
        if not urls:
            return TavilyResult(
                success=False,
                data="",
                error="No URLs provided for extraction"
            )
        
        # Limit to 10 URLs per API constraints
        urls = urls[:10]
        
        try:
            response = await self._client.extract(
                urls=urls,
                extract_depth="advanced",  # Better for complex sites
                include_images=False,
            )
            
            markdown = self._format_extraction_results(urls, response, query)
            return TavilyResult(success=True, data=markdown)
            
        except (BadRequestError, InvalidAPIKeyError, UsageLimitExceededError) as e:
            return self._handle_error("extract_content", e)
        except Exception as e:
            return TavilyResult(
                success=False,
                data="",
                error=f"Unexpected error in extract_content: {str(e)}"
            )
    
    async def map_site(
        self,
        url: str,
        max_depth: int = 2,
    ) -> TavilyResult:
        """
        Discover the structure and pages of a domain.
        
        Best for:
        - Exploring a site before crawling
        - Understanding site organization
        - Finding specific sections (team pages, portfolio, news)
        - Building a crawl strategy
        
        Args:
            url: The base URL of the site to map.
            max_depth: How deep to crawl the site structure (1-3).
        
        Returns:
            TavilyResult with site map in structured format.
        """
        try:
            response = await self._client.map(
                url=url,
                max_depth=max_depth,
            )
            
            markdown = self._format_site_map(url, response)
            return TavilyResult(success=True, data=markdown)
            
        except (BadRequestError, InvalidAPIKeyError, UsageLimitExceededError) as e:
            return self._handle_error("map_site", e)
        except Exception as e:
            return TavilyResult(
                success=False,
                data="",
                error=f"Unexpected error in map_site: {str(e)}"
            )
    
    async def crawl_site(
        self,
        url: str,
        instructions: str,
        max_pages: int = 10,
    ) -> TavilyResult:
        """
        Systematically gather data from a domain based on natural language intent.
        
        Best for:
        - Collecting team information from an "About" section
        - Gathering all portfolio companies from a VC site
        - Extracting press releases or news archives
        - Any task requiring structured data from multiple pages
        
        Args:
            url: The starting URL for the crawl.
            instructions: Natural language description of what data to gather.
                Example: "Find all team members with their roles and backgrounds"
            max_pages: Maximum pages to crawl (1-50).
        
        Returns:
            TavilyResult with crawled data structured per instructions.
        """
        try:
            response = await self._client.crawl(
                url=url,
                instructions=instructions,
                max_pages=max_pages,
            )
            
            markdown = self._format_crawl_results(url, instructions, response)
            return TavilyResult(success=True, data=markdown)
            
        except (BadRequestError, InvalidAPIKeyError, UsageLimitExceededError) as e:
            return self._handle_error("crawl_site", e)
        except Exception as e:
            return TavilyResult(
                success=False,
                data="",
                error=f"Unexpected error in crawl_site: {str(e)}"
            )
    
    # -------------------------------------------------------------------------
    # Formatting helpers - Convert raw API responses to clean markdown
    # -------------------------------------------------------------------------
    
    def _format_search_results(self, query: str, response: dict) -> str:
        """Format search results as markdown."""
        lines = [
            f"## Web Search Results",
            f"**Query:** {query}",
            "",
        ]
        
        # Include the AI-generated answer if available
        if response.get("answer"):
            lines.extend([
                "### Summary",
                response["answer"],
                "",
            ])
        
        # Format individual results
        results = response.get("results", [])
        if results:
            lines.append("### Sources")
            lines.append("")
            for i, result in enumerate(results, 1):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                content = result.get("content", "")
                score = result.get("score", 0)
                
                lines.extend([
                    f"#### {i}. {title}",
                    f"**URL:** {url}",
                    f"**Relevance:** {score:.2f}",
                    "",
                    content,
                    "",
                    "---",
                    "",
                ])
        
        return "\n".join(lines)
    
    def _format_research_report(self, query: str, response: dict) -> str:
        """Format deep research report as markdown."""
        lines = [
            f"## Deep Research Report",
            f"**Research Question:** {query}",
            "",
        ]
        
        # Handle different response structures from the research API
        if isinstance(response, dict):
            if "report" in response:
                lines.append(response["report"])
            elif "content" in response:
                lines.append(response["content"])
            elif "answer" in response:
                lines.append(response["answer"])
            else:
                # Fallback: dump the response as formatted JSON
                lines.append("### Research Findings")
                lines.append("```json")
                lines.append(json.dumps(response, indent=2, default=str))
                lines.append("```")
        elif isinstance(response, str):
            lines.append(response)
        
        # Include sources if available
        sources = response.get("sources", []) if isinstance(response, dict) else []
        if sources:
            lines.extend(["", "### Sources Consulted", ""])
            for source in sources:
                if isinstance(source, dict):
                    title = source.get("title", "Source")
                    url = source.get("url", "")
                    lines.append(f"- [{title}]({url})")
                else:
                    lines.append(f"- {source}")
        
        return "\n".join(lines)
    
    def _format_extraction_results(
        self, urls: list[str], response: dict, query: Optional[str]
    ) -> str:
        """Format content extraction results as markdown."""
        lines = [
            "## Content Extraction Results",
            f"**URLs Processed:** {len(urls)}",
        ]
        
        if query:
            lines.append(f"**Focus Query:** {query}")
        
        lines.extend(["", "---", ""])
        
        results = response.get("results", [])
        if results:
            for result in results:
                url = result.get("url", "Unknown URL")
                raw_content = result.get("raw_content", "")
                
                lines.extend([
                    f"### {url}",
                    "",
                    raw_content if raw_content else "_No content extracted_",
                    "",
                    "---",
                    "",
                ])
        else:
            lines.append("_No content could be extracted from the provided URLs._")
        
        return "\n".join(lines)
    
    def _format_site_map(self, url: str, response: dict) -> str:
        """Format site map as markdown."""
        lines = [
            "## Site Map",
            f"**Domain:** {url}",
            "",
            "### Discovered Pages",
            "",
        ]
        
        # Handle different response formats
        pages = response.get("urls", response.get("pages", []))
        
        if isinstance(pages, list):
            for page in pages:
                if isinstance(page, dict):
                    page_url = page.get("url", "")
                    title = page.get("title", "Untitled")
                    lines.append(f"- [{title}]({page_url})")
                else:
                    lines.append(f"- {page}")
        elif isinstance(pages, dict):
            for category, urls in pages.items():
                lines.append(f"#### {category}")
                for u in urls:
                    lines.append(f"  - {u}")
                lines.append("")
        
        if not pages:
            lines.append("_No pages discovered. The site may block crawling._")
        
        return "\n".join(lines)
    
    def _format_crawl_results(
        self, url: str, instructions: str, response: dict
    ) -> str:
        """Format crawl results as markdown."""
        lines = [
            "## Site Crawl Results",
            f"**Starting URL:** {url}",
            f"**Instructions:** {instructions}",
            "",
            "---",
            "",
        ]
        
        # The crawl endpoint typically returns structured data based on instructions
        if isinstance(response, dict):
            if "data" in response:
                data = response["data"]
                if isinstance(data, list):
                    lines.append("### Extracted Data")
                    lines.append("")
                    for item in data:
                        if isinstance(item, dict):
                            for key, value in item.items():
                                lines.append(f"**{key}:** {value}")
                            lines.append("")
                        else:
                            lines.append(f"- {item}")
                else:
                    lines.append(str(data))
            elif "results" in response:
                for result in response["results"]:
                    page_url = result.get("url", "")
                    content = result.get("content", result.get("raw_content", ""))
                    lines.extend([
                        f"### {page_url}",
                        "",
                        content,
                        "",
                        "---",
                        "",
                    ])
            else:
                lines.append("### Raw Response")
                lines.append("```json")
                lines.append(json.dumps(response, indent=2, default=str))
                lines.append("```")
        else:
            lines.append(str(response))
        
        return "\n".join(lines)
    
    def _handle_error(self, method: str, error: Exception) -> TavilyResult:
        """Handle Tavily API errors with helpful messages."""
        error_msg = str(error)
        
        # Handle specific error types
        if isinstance(error, UsageLimitExceededError):
            return TavilyResult(
                success=False,
                data="",
                error=f"Rate limit exceeded in {method}. Please wait before retrying."
            )
        
        if isinstance(error, InvalidAPIKeyError):
            return TavilyResult(
                success=False,
                data="",
                error=f"Authentication failed in {method}. Check your TAVILY_API_KEY."
            )
        
        if isinstance(error, BadRequestError):
            return TavilyResult(
                success=False,
                data="",
                error=f"Bad request in {method}: {error_msg}"
            )
        
        # Generic error
        return TavilyResult(
            success=False,
            data="",
            error=f"Tavily API error in {method}: {error_msg}"
        )


# -------------------------------------------------------------------------
# ADK Tool Wrappers - Create functions that can be used as Google ADK tools
# -------------------------------------------------------------------------

# Global toolbox instance (initialized lazily)
_toolbox: Optional[TavilyToolbox] = None


def _get_toolbox() -> TavilyToolbox:
    """Get or create the global TavilyToolbox instance."""
    global _toolbox
    if _toolbox is None:
        _toolbox = TavilyToolbox()
    return _toolbox


async def tavily_web_search(
    query: str,
    depth: str = "advanced",
    max_results: int = 5,
) -> str:
    """
    Search the web for current information and news.
    
    Use this for:
    - Recent news and announcements about funds, companies, or people
    - Quick factual lookups (fund sizes, founding dates, etc.)
    - Finding articles and press coverage
    - Surface-level research on any topic
    
    Args:
        query: What to search for. Be specific for better results.
        depth: "basic" for quick search, "advanced" for thorough results.
        max_results: Number of results (1-20).
    
    Returns:
        Markdown-formatted search results with sources.
    """
    # #region agent log
    _debug_print("TOOL_WEB_SEARCH", f">>> ENTRY: {query[:60]}...")
    # #endregion
    toolbox = _get_toolbox()
    result = await toolbox.web_search(query, depth, max_results)
    # #region agent log
    _debug_print("TOOL_WEB_SEARCH", f"<<< EXIT: success={result.success}, data_len={len(result.data)}, error={result.error}")
    if result.data:
        _debug_print("TOOL_WEB_SEARCH", f"    PREVIEW: {result.data[:150]}...")
    # #endregion
    if result.success:
        return result.data
    return f"**Search Error:** {result.error}"


async def tavily_deep_research(query: str) -> str:
    """
    Conduct comprehensive multi-step research on complex topics.
    
    Use this when you need:
    - Deep background research requiring multiple searches
    - Synthesis of information from many sources
    - A comprehensive report on a complex topic
    - Analysis that goes beyond surface-level facts
    
    This is more thorough but slower than web_search.
    
    Args:
        query: The research question or topic to investigate.
    
    Returns:
        A comprehensive research report in markdown format.
    """
    # #region agent log
    _debug_print("TOOL_DEEP_RESEARCH", f">>> ENTRY: {query[:60]}...")
    # #endregion
    toolbox = _get_toolbox()
    result = await toolbox.deep_research(query)
    # #region agent log
    _debug_print("TOOL_DEEP_RESEARCH", f"<<< EXIT: success={result.success}, data_len={len(result.data)}, error={result.error}")
    if result.data:
        _debug_print("TOOL_DEEP_RESEARCH", f"    PREVIEW: {result.data[:150]}...")
    # #endregion
    if result.success:
        return result.data
    return f"**Research Error:** {result.error}"


async def tavily_extract_content(
    urls: list[str],
    query: Optional[str] = None,
) -> str:
    """
    Extract and parse content from specific URLs.
    
    Use this when you:
    - Already have URLs from a previous search
    - Need to parse content from complex sites (JavaScript, PDFs)
    - Want the full text of articles or documents
    - Need structured extraction from known sources
    
    Args:
        urls: List of URLs to extract (max 10).
        query: Optional focus query to filter relevant content.
    
    Returns:
        Extracted content in markdown format.
    """
    toolbox = _get_toolbox()
    result = await toolbox.extract_content(urls, query)
    if result.success:
        return result.data
    return f"**Extraction Error:** {result.error}"


async def tavily_map_site(url: str) -> str:
    """
    Discover the structure and pages of a website.
    
    Use this to:
    - Explore a site before crawling it
    - Find specific sections (team pages, portfolio, news)
    - Understand how a site is organized
    - Plan a targeted data gathering strategy
    
    Args:
        url: The base URL of the site to map.
    
    Returns:
        Site structure with discovered pages.
    """
    toolbox = _get_toolbox()
    result = await toolbox.map_site(url)
    if result.success:
        return result.data
    return f"**Mapping Error:** {result.error}"


async def tavily_crawl_site(url: str, instructions: str) -> str:
    """
    Systematically gather data from a website based on natural language intent.
    
    Use this when you need to:
    - Collect team bios from an "About" page
    - Gather all portfolio companies from a VC site
    - Extract press releases or news archives
    - Get structured data from multiple pages on one domain
    
    Args:
        url: The starting URL for the crawl.
        instructions: What data to gather, in natural language.
            Examples:
            - "Find all team members with their roles and backgrounds"
            - "List all portfolio companies with investment stage and sector"
            - "Extract all press releases from 2024"
    
    Returns:
        Structured data matching the instructions.
    """
    toolbox = _get_toolbox()
    result = await toolbox.crawl_site(url, instructions)
    if result.success:
        return result.data
    return f"**Crawl Error:** {result.error}"


# Export the ADK-compatible tool functions
TAVILY_TOOLS = [
    tavily_web_search,
    tavily_deep_research,
    tavily_extract_content,
    tavily_map_site,
    tavily_crawl_site,
]
