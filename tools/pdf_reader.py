"""PDF reader tool for extracting text from PDF contracts with page and line markers.

Uses pdfplumber for robust PDF text extraction with layout preservation.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pdfplumber
from loguru import logger

from adk.error_handling import DocumentParsingError, handle_errors
from adk.logging_config import log_tool_execution


class PDFReader:
    """PDF reader that extracts text with page and line number preservation."""
    
    def __init__(self, max_pages: int = 30):
        """Initialize PDF reader.
        
        Args:
            max_pages: Maximum number of pages to process
        """
        self.max_pages = max_pages
    
    @log_tool_execution("pdf_reader")
    @handle_errors(DocumentParsingError)
    def read_pdf(self, file_path: str) -> Dict[str, any]:
        """Extract text from PDF file with page and line markers.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary containing:
                - text: Full extracted text with markers
                - pages: List of page texts
                - page_count: Number of pages
                - metadata: PDF metadata
                
        Raises:
            DocumentParsingError: If PDF parsing fails
        """
        path = Path(file_path)
        
        if not path.exists():
            raise DocumentParsingError(f"File not found: {file_path}")
        
        if not path.suffix.lower() == '.pdf':
            raise DocumentParsingError(f"File is not a PDF: {file_path}")
        
        try:
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)
                
                if page_count > self.max_pages:
                    logger.warning(
                        f"PDF has {page_count} pages, exceeding limit of {self.max_pages}",
                        file_path=file_path
                    )
                    raise DocumentParsingError(
                        f"PDF exceeds maximum page limit ({self.max_pages} pages)"
                    )
                
                pages = []
                full_text_parts = []
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text from page
                    page_text = page.extract_text()
                    
                    if not page_text:
                        logger.warning(f"No text extracted from page {page_num}")
                        page_text = ""
                    
                    pages.append(page_text)
                    
                    # Add page marker
                    full_text_parts.append(f"[PAGE {page_num}]")
                    
                    # Add line markers
                    lines = page_text.split('\n')
                    for line_num, line in enumerate(lines, start=1):
                        if line.strip():  # Only add non-empty lines
                            full_text_parts.append(f"[LINE {line_num}] {line}")
                
                full_text = '\n'.join(full_text_parts)
                
                # Extract metadata
                metadata = pdf.metadata or {}
                
                logger.info(
                    f"Successfully extracted text from PDF",
                    file_path=file_path,
                    page_count=page_count,
                    text_length=len(full_text)
                )
                
                return {
                    "text": full_text,
                    "pages": pages,
                    "page_count": page_count,
                    "metadata": {
                        "title": metadata.get("Title", ""),
                        "author": metadata.get("Author", ""),
                        "subject": metadata.get("Subject", ""),
                        "creator": metadata.get("Creator", ""),
                        "producer": metadata.get("Producer", ""),
                        "creation_date": str(metadata.get("CreationDate", "")),
                    }
                }
                
        except pdfplumber.PDFSyntaxError as e:
            raise DocumentParsingError(f"Invalid PDF format: {str(e)}")
        except Exception as e:
            raise DocumentParsingError(f"Failed to read PDF: {str(e)}")
    
    @log_tool_execution("pdf_reader_bytes")
    @handle_errors(DocumentParsingError)
    def read_pdf_bytes(self, file_bytes: bytes, filename: str = "contract.pdf") -> Dict[str, any]:
        """Extract text from PDF bytes (for file uploads).
        
        Args:
            file_bytes: PDF file content as bytes
            filename: Original filename for logging
            
        Returns:
            Dictionary containing extracted text and metadata
            
        Raises:
            DocumentParsingError: If PDF parsing fails
        """
        import io
        
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                page_count = len(pdf.pages)
                
                if page_count > self.max_pages:
                    logger.warning(
                        f"PDF has {page_count} pages, exceeding limit of {self.max_pages}",
                        filename=filename
                    )
                    raise DocumentParsingError(
                        f"PDF exceeds maximum page limit ({self.max_pages} pages)"
                    )
                
                pages = []
                full_text_parts = []
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    
                    if not page_text:
                        logger.warning(f"No text extracted from page {page_num}")
                        page_text = ""
                    
                    pages.append(page_text)
                    
                    full_text_parts.append(f"[PAGE {page_num}]")
                    
                    lines = page_text.split('\n')
                    for line_num, line in enumerate(lines, start=1):
                        if line.strip():
                            full_text_parts.append(f"[LINE {line_num}] {line}")
                
                full_text = '\n'.join(full_text_parts)
                
                metadata = pdf.metadata or {}
                
                logger.info(
                    f"Successfully extracted text from PDF bytes",
                    filename=filename,
                    page_count=page_count,
                    text_length=len(full_text)
                )
                
                return {
                    "text": full_text,
                    "pages": pages,
                    "page_count": page_count,
                    "metadata": {
                        "title": metadata.get("Title", ""),
                        "author": metadata.get("Author", ""),
                        "subject": metadata.get("Subject", ""),
                        "creator": metadata.get("Creator", ""),
                        "producer": metadata.get("Producer", ""),
                        "creation_date": str(metadata.get("CreationDate", "")),
                    }
                }
                
        except pdfplumber.PDFSyntaxError as e:
            raise DocumentParsingError(f"Invalid PDF format: {str(e)}")
        except Exception as e:
            raise DocumentParsingError(f"Failed to read PDF bytes: {str(e)}")


# Tool function for ADK integration
def read_pdf_tool(file_path: str) -> str:
    """Tool function for reading PDF files in ADK agents.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text with page and line markers
    """
    reader = PDFReader()
    result = reader.read_pdf(file_path)
    return result["text"]
