"""
PDF Formatter Tool - Converts LP Brief markdown to branded PDF.

Uses markdown2 for markdown-to-HTML conversion and WeasyPrint for PDF generation.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import time

# Set library path for WeasyPrint on macOS before importing it
# WeasyPrint requires Pango/GLib which are installed via Homebrew
if sys.platform == "darwin":
    homebrew_lib = "/opt/homebrew/lib"
    if os.path.exists(homebrew_lib):
        current_path = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        if homebrew_lib not in current_path:
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{homebrew_lib}:{current_path}"

import markdown2
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


# Resolve paths relative to this module
MODULE_DIR = Path(__file__).parent
PACKAGE_DIR = MODULE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATE_DIR = PACKAGE_DIR / "templates"
OUTPUT_DIR = PACKAGE_DIR / "output"

# Default logo path
LOGO_PATH = STATIC_DIR / "sago_header.png"


def _extract_entity_name(brief_content: str) -> Optional[str]:
    """Extract entity name from brief content if present.
    
    Looks for entity name in multiple places:
    1. "## Fund Overview" or "## Company Overview" first data cell (fund name or company name)
    2. First heading/title in the content
    3. Look for fund_name or entity_name in any table
    """
    if not brief_content:
        return None
    
    # Pattern 1: Look for "# Brief: [Entity Name]" format
    match = re.search(r'^#\s*Brief:\s*(.+)$', brief_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: Look for entity name in first table (common in briefs with overview tables)
    # Briefs often have a two-column table starting with the fund/company name
    table_match = re.search(r'\|\s*([^\|]+?)\s*\|\s*[^\|]+?\s*\|', brief_content)
    if table_match:
        first_cell = table_match.group(1).strip()
        # If it looks like an entity name (not a generic header), use it
        if first_cell and not first_cell.lower() in ['key', 'name', 'value', 'information', 'details', 'overview']:
            return first_cell
    
    # Pattern 3: Look for first H1
    match = re.search(r'^#\s+([^\n#][^\n]+)$', brief_content, re.MULTILINE)
    if match:
        entity = match.group(1).strip()
        # Remove common prefixes
        entity = re.sub(r'^(Brief|Memo|Document|Report):\s*', '', entity, flags=re.IGNORECASE)
        if entity:
            return entity
    
    # Pattern 4: Look for first major heading (H2 or H3) that might contain entity name
    # Often organized as "## Fund Overview" with fund name in first row
    match = re.search(r'^##\s+(.+?)\s+Overview\s*$', brief_content, re.MULTILINE | re.IGNORECASE)
    if match:
        entity = match.group(1).strip()
        if entity and entity.lower() not in ['fund', 'company', 'entity']:
            return entity
    
    return None


def _sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    # Remove or replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = re.sub(r'\s+', '_', safe)
    return safe[:50]  # Limit length


def _enhance_section_headers(html_content: str, is_memo: bool = False) -> str:
    """Wrap section headers (h2) with branded styling div."""
    # Pattern to match h2 tags and wrap them in section-header div
    pattern = r'<h2([^>]*)>(.*?)</h2>'
    if is_memo:
        # For memos, use simpler styling without background box
        replacement = r'<h2\1>\2</h2>'
    else:
        # For full briefs, use the branded box styling
        replacement = r'<div class="section-header"><h2\1>\2</h2></div>'
    return re.sub(pattern, replacement, html_content, flags=re.IGNORECASE)


def _style_flags(html_content: str) -> str:
    """Add styling classes to red and yellow flag sections."""
    # Style "Red Flags" mentions
    html_content = re.sub(
        r'<h3([^>]*)>([^<]*Red Flag[^<]*)</h3>',
        r'<h3\1 class="red-flag">\2</h3>',
        html_content,
        flags=re.IGNORECASE
    )
    
    # Style "Yellow Flags" mentions
    html_content = re.sub(
        r'<h3([^>]*)>([^<]*Yellow Flag[^<]*)</h3>',
        r'<h3\1 class="yellow-flag">\2</h3>',
        html_content,
        flags=re.IGNORECASE
    )
    
    return html_content


def _convert_markdown_to_html(brief_content: str, is_memo: bool = False) -> str:
    """Convert markdown brief to HTML using markdown2."""
    # Use markdown2 with extras for tables, fenced code, etc.
    html = markdown2.markdown(
        brief_content,
        extras=[
            "tables",
            "fenced-code-blocks",
            "header-ids",
            "break-on-newline",
            "cuddled-lists",
        ]
    )
    
    # Post-process to add brand styling
    html = _enhance_section_headers(html, is_memo=is_memo)
    html = _style_flags(html)
    
    return html


def format_brief_to_pdf(
    brief_content: str,
    output_path: Optional[str] = None,
    entity_name: Optional[str] = None,
    prepared_for: str = "Limited partners seeking to invest in fund managers",
    tokens_used: Optional[int] = None,
    generation_time: Optional[str] = None,
    tool_context = None
) -> str:
    """
    Convert a markdown LP brief to a branded PDF document.
    
    This tool takes the markdown brief produced by the orchestrator agent
    and formats it into a professional PDF using the Sago brand guide styling.
    
    Args:
        brief_content: The full markdown brief content from the orchestrator.
        output_path: Optional path for the output PDF. If not provided, 
                    saves to lp_brief/output/ with auto-generated filename.
        entity_name: Optional entity name for the title. If not provided,
                  attempts to extract from the brief content.
        prepared_for: The recipient description for the brief header.
                     Defaults to "Limited partners seeking to invest in fund managers".
        tokens_used: Optional number of tokens used to generate the brief.
        generation_time: Optional time taken to generate the brief (e.g., "2.5 seconds").
        tool_context: Optional tool context for accessing session state.
    
    Returns:
        The absolute path to the generated PDF file.
    
    Example:
        >>> path = format_brief_to_pdf(brief_content, entity_name="Sequoia Capital Fund XVI")
        >>> print(f"PDF saved to: {path}")
    """
    # Extract entity name if not provided
    if not entity_name:
        entity_name = _extract_entity_name(brief_content) or "Entity Brief"
    
    # Get usage and time from tool_context if not provided
    if tool_context:
        # Try different paths to access session state
        state = None
        if hasattr(tool_context, 'invocation_context') and hasattr(tool_context.invocation_context, 'session'):
            state = tool_context.invocation_context.session.state
        elif hasattr(tool_context, 'session'):
            state = tool_context.session.state
        elif hasattr(tool_context, 'state'):
            state = tool_context.state
        
        if state:
            if tokens_used is None:
                tokens_used = state.get('total_tokens_used')
            if generation_time is None and 'generation_start_time' in state:
                start_time = state['generation_start_time']
                elapsed = time.time() - start_time
                generation_time = f"{elapsed:.1f} seconds"
    
    # Convert markdown to HTML
    html_body = _convert_markdown_to_html(brief_content)
    
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("brief_template.html")
    
    # Determine logo path - use absolute path for WeasyPrint
    logo_path = str(LOGO_PATH.absolute()) if LOGO_PATH.exists() else ""
    
    # Render the template
    current_date = datetime.now().strftime("%B %d, %Y")
    html = template.render(
        title=f"LP Brief: {entity_name}",
        entity_name=entity_name,
        prepared_for=prepared_for,
        date=current_date,
        content=html_body,
        logo_path=logo_path,
        tokens_used=tokens_used,
        generation_time=generation_time
    )
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate output path if not provided
    if not output_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = _sanitize_filename(entity_name)
        output_path = str(OUTPUT_DIR / f"brief_{safe_name}_{date_str}.pdf")
    
    # Convert to absolute path
    output_path = str(Path(output_path).absolute())
    
    # Generate PDF using WeasyPrint
    # Set base_url to static directory so images resolve correctly
    HTML(
        string=html,
        base_url=str(STATIC_DIR.absolute())
    ).write_pdf(output_path)
    
    return output_path


def format_memo_to_pdf(
    memo_content: str,
    output_path: Optional[str] = None,
    memo_title: str = "Executive Memo",
    entity_name: Optional[str] = None
) -> str:
    """
    Convert a markdown memo to a clean PDF document.
    
    This tool takes the markdown memo content and formats it into a clean,
    professional PDF without title page or branding headers.
    
    Args:
        memo_content: The full markdown memo content.
        output_path: Optional path for the output PDF. If not provided, 
                    saves to lp_brief/output/ with auto-generated filename.
        memo_title: Title for the memo, used in filename generation.
        entity_name: Optional entity name to display in the memo header and filename.
                    If not provided, will attempt to extract from memo_title.
    
    Returns:
        The absolute path to the generated PDF file.
    
    Example:
        >>> path = format_memo_to_pdf(memo_content, entity_name="SpaceX")
        >>> print(f"Memo PDF saved to: {path}")
    """
    # Extract entity name from memo_title if not explicitly provided
    if not entity_name:
        # Try to extract from memo_title (e.g., "SpaceX Executive Memo" -> "SpaceX")
        if memo_title and memo_title != "Executive Memo":
            # Remove common suffixes
            entity_name = re.sub(r'\s+(Executive\s+)?Memo.*$', '', memo_title, flags=re.IGNORECASE).strip()
        else:
            entity_name = "Entity Brief"
    
    # Create display title for the memo header
    display_title = f"Brief: {entity_name}" if entity_name and entity_name != "Executive Memo" else "Executive Memo"
    
    # Convert markdown to HTML
    html_body = _convert_markdown_to_html(memo_content, is_memo=True)
    
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("memo_template.html")
    
    # Render the template with display title
    html = template.render(
        title=memo_title,
        display_title=display_title,
        entity_name=entity_name,
        content=html_body
    )
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate output path if not provided
    if not output_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = _sanitize_filename(entity_name) if entity_name else _sanitize_filename(memo_title)
        output_path = str(OUTPUT_DIR / f"memo_{safe_name}_{date_str}.pdf")
    
    # Convert to absolute path
    output_path = str(Path(output_path).absolute())
    
    # Generate PDF using WeasyPrint
    HTML(string=html).write_pdf(output_path)
    
    return output_path


# Tool metadata for ADK registration
format_memo_to_pdf.__doc__ = """
Convert a markdown memo to a clean PDF document.

This tool takes the markdown memo content and formats it into a clean,
professional PDF without title page or branding headers.

Args:
    memo_content: The full markdown memo content.
    output_path: Optional path for the output PDF. If not provided, 
                saves to lp_brief/output/ with auto-generated filename.
    memo_title: Title for the memo, used in HTML title tag.
    entity_name: The company or fund name. If provided, will be displayed in the memo header
                as "Brief: entity_name" and used in the filename. If not provided, will attempt
                to extract from memo_title (recommended to pass explicitly).

Returns:
    The absolute path to the generated PDF file.
"""
