"""
PDF Reader Tool - Extracts text content from PDF files.

Uses PyPDF2 for reliable text extraction from PDF documents.
"""

from pathlib import Path
from typing import Optional
import PyPDF2


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text content from a PDF file.
    
    This tool reads a PDF file and extracts all readable text content,
    concatenating text from all pages.
    
    Args:
        pdf_path: Absolute path to the PDF file to read.
    
    Returns:
        The extracted text content from the PDF.
    
    Raises:
        FileNotFoundError: If the PDF file does not exist.
        PyPDF2.errors.PdfReadError: If the PDF cannot be read.
    
    Example:
        >>> text = extract_pdf_text("/path/to/brief.pdf")
        >>> print(text[:200])  # First 200 characters
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        text_content = []
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text.strip():
                text_content.append(text)
        
        return '\n\n'.join(text_content)


# Tool metadata for ADK registration
extract_pdf_text.__doc__ = """
Extract text content from a PDF file.

This tool reads a PDF file and extracts all readable text content,
concatenating text from all pages.

Args:
    pdf_path: Absolute path to the PDF file to read.

Returns:
    The extracted text content from the PDF.
"""