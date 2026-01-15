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
ASSETS_DIR = MODULE_DIR / "assets"
TEMPLATE_DIR = MODULE_DIR
OUTPUT_DIR = MODULE_DIR / "output"

# Default logo path
LOGO_PATH = ASSETS_DIR / "sago_header.png"


def _extract_fund_name(brief_content: str) -> Optional[str]:
    """Extract fund name from brief content if present."""
    # Look for "# Brief: [Fund Name]" pattern
    match = re.search(r'^#\s*Brief:\s*(.+)$', brief_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # Alternative: look for first H1
    match = re.search(r'^#\s+(.+)$', brief_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    return None


def _sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    # Remove or replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    safe = re.sub(r'\s+', '_', safe)
    return safe[:50]  # Limit length


def _enhance_section_headers(html_content: str) -> str:
    """Wrap section headers (h2) with branded styling div."""
    # Pattern to match h2 tags and wrap them in section-header div
    pattern = r'<h2([^>]*)>(.*?)</h2>'
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


def _convert_markdown_to_html(brief_content: str) -> str:
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
    html = _enhance_section_headers(html)
    html = _style_flags(html)
    
    return html


def format_brief_to_pdf(
    brief_content: str,
    output_path: Optional[str] = None,
    fund_name: Optional[str] = None,
    prepared_for: str = "Limited partners seeking to invest in fund managers"
) -> str:
    """
    Convert a markdown LP brief to a branded PDF document.
    
    This tool takes the markdown brief produced by the orchestrator agent
    and formats it into a professional PDF using the Sago brand guide styling.
    
    Args:
        brief_content: The full markdown brief content from the orchestrator.
        output_path: Optional path for the output PDF. If not provided, 
                    saves to lp_brief/output/ with auto-generated filename.
        fund_name: Optional fund name for the title. If not provided,
                  attempts to extract from the brief content.
        prepared_for: The recipient description for the brief header.
                     Defaults to "Limited partners seeking to invest in fund managers".
    
    Returns:
        The absolute path to the generated PDF file.
    
    Example:
        >>> path = format_brief_to_pdf(brief_content, fund_name="Sequoia Capital Fund XVI")
        >>> print(f"PDF saved to: {path}")
    """
    # Extract fund name if not provided
    if not fund_name:
        fund_name = _extract_fund_name(brief_content) or "Fund Brief"
    
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
        title=f"LP Brief: {fund_name}",
        fund_name=fund_name,
        prepared_for=prepared_for,
        date=current_date,
        content=html_body,
        logo_path=logo_path
    )
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate output path if not provided
    if not output_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = _sanitize_filename(fund_name)
        output_path = str(OUTPUT_DIR / f"brief_{safe_name}_{date_str}.pdf")
    
    # Convert to absolute path
    output_path = str(Path(output_path).absolute())
    
    # Generate PDF using WeasyPrint
    # Set base_url to assets directory so images resolve correctly
    HTML(
        string=html,
        base_url=str(ASSETS_DIR.absolute())
    ).write_pdf(output_path)
    
    return output_path


# Tool metadata for ADK registration
format_brief_to_pdf.__doc__ = """
Convert a markdown LP brief to a branded PDF document.

This tool takes the markdown brief produced by the orchestrator agent
and formats it into a professional PDF using the Sago brand guide styling.

Args:
    brief_content: The full markdown brief content from the orchestrator.
    output_path: Optional path for the output PDF. If not provided, 
                saves to lp_brief/output/ with auto-generated filename.
    fund_name: Optional fund name for the title. If not provided,
              attempts to extract from the brief content.
    prepared_for: The recipient description for the brief header.
                 Defaults to "Limited partners seeking to invest in fund managers".

Returns:
    The absolute path to the generated PDF file.
"""
