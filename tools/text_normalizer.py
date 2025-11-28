"""Text normalization tool for cleaning and standardizing contract text.

Handles encoding issues, whitespace normalization, and format standardization.
"""

import re
import unicodedata
from typing import Dict
from loguru import logger

from adk.error_handling import DocumentParsingError, handle_errors
from adk.logging_config import log_tool_execution


class TextNormalizer:
    """Text normalizer for contract documents."""
    
    def __init__(self):
        """Initialize text normalizer."""
        pass
    
    @log_tool_execution("text_normalizer")
    @handle_errors(DocumentParsingError, reraise=False)
    def normalize(self, text: str) -> str:
        """Normalize contract text with encoding cleanup and formatting.
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            logger.warning("Empty text provided for normalization")
            return ""
        
        # Unicode normalization (NFC form)
        text = unicodedata.normalize('NFC', text)
        
        # Fix common encoding issues
        text = self._fix_encoding_issues(text)
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        # Fix line breaks
        text = self._fix_line_breaks(text)
        
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        logger.debug(f"Text normalized, length: {len(text)}")
        
        return text
    
    def _fix_encoding_issues(self, text: str) -> str:
        """Fix common encoding issues in contract text.
        
        Args:
            text: Text with potential encoding issues
            
        Returns:
            Text with fixed encoding
        """
        # Common replacements for encoding issues
        replacements = {
            '\u2018': "'",  # Left single quotation mark
            '\u2019': "'",  # Right single quotation mark
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2026': '...', # Ellipsis
            '\u00a0': ' ',  # Non-breaking space
            '\u00ad': '',   # Soft hyphen
            '\ufeff': '',   # Zero-width no-break space (BOM)
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.
        
        Args:
            text: Text with irregular whitespace
            
        Returns:
            Text with normalized whitespace
        """
        # Replace tabs with spaces
        text = text.replace('\t', '    ')
        
        # Replace multiple spaces with single space (except at line start)
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Preserve leading whitespace but normalize the rest
            leading_space = len(line) - len(line.lstrip())
            content = line.lstrip()
            content = re.sub(r' +', ' ', content)
            normalized_lines.append(' ' * leading_space + content)
        
        return '\n'.join(normalized_lines)
    
    def _fix_line_breaks(self, text: str) -> str:
        """Fix line break issues in text.
        
        Args:
            text: Text with line break issues
            
        Returns:
            Text with fixed line breaks
        """
        # Normalize different line ending styles to \n
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        return text
    
    @log_tool_execution("text_normalizer_with_markers")
    def normalize_with_markers(self, text: str, preserve_markers: bool = True) -> str:
        """Normalize text while preserving page and line markers.
        
        Args:
            text: Text with [PAGE X] and [LINE Y] markers
            preserve_markers: Whether to preserve markers during normalization
            
        Returns:
            Normalized text with preserved markers
        """
        if not preserve_markers:
            return self.normalize(text)
        
        # Split by markers
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Check if line is a marker
            if line.strip().startswith('[PAGE ') or line.strip().startswith('[LINE '):
                # Keep markers as-is
                normalized_lines.append(line)
            else:
                # Normalize content lines
                if line.strip():
                    normalized_line = self.normalize(line)
                    normalized_lines.append(normalized_line)
        
        return '\n'.join(normalized_lines)


class FileValidator:
    """Validator for uploaded contract files."""
    
    def __init__(
        self,
        max_size_mb: int = 10,
        allowed_extensions: list[str] = None
    ):
        """Initialize file validator.
        
        Args:
            max_size_mb: Maximum file size in megabytes
            allowed_extensions: List of allowed file extensions
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.allowed_extensions = allowed_extensions or ['.pdf', '.txt']
    
    @log_tool_execution("file_validator")
    def validate_file(
        self,
        filename: str,
        file_size: int,
        file_content: bytes = None
    ) -> Dict[str, any]:
        """Validate uploaded file.
        
        Args:
            filename: Name of the uploaded file
            file_size: Size of the file in bytes
            file_content: Optional file content for additional validation
            
        Returns:
            Dictionary with validation results:
                - valid: Boolean indicating if file is valid
                - errors: List of validation errors
                - warnings: List of validation warnings
                
        Raises:
            DocumentParsingError: If validation fails critically
        """
        errors = []
        warnings = []
        
        # Check file extension
        file_ext = None
        if '.' in filename:
            file_ext = '.' + filename.rsplit('.', 1)[1].lower()
        
        if not file_ext or file_ext not in self.allowed_extensions:
            errors.append(
                f"Invalid file type. Allowed types: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size
        if file_size > self.max_size_bytes:
            errors.append(
                f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds "
                f"maximum allowed size ({self.max_size_bytes / 1024 / 1024:.0f} MB)"
            )
        
        # Check if file is empty
        if file_size == 0:
            errors.append("File is empty")
        
        # Warn if file is very small (likely not a real contract)
        if file_size < 1024:  # Less than 1 KB
            warnings.append("File is very small, may not contain a complete contract")
        
        # Additional content validation if provided
        if file_content:
            # Check for PDF magic number
            if file_ext == '.pdf':
                if not file_content.startswith(b'%PDF'):
                    errors.append("File does not appear to be a valid PDF")
        
        valid = len(errors) == 0
        
        if not valid:
            logger.warning(
                f"File validation failed",
                filename=filename,
                errors=errors
            )
        
        if warnings:
            logger.info(
                f"File validation warnings",
                filename=filename,
                warnings=warnings
            )
        
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "file_extension": file_ext,
            "file_size_mb": file_size / 1024 / 1024
        }


# Tool functions for ADK integration
def normalize_text_tool(text: str) -> str:
    """Tool function for normalizing text in ADK agents.
    
    Args:
        text: Raw text to normalize
        
    Returns:
        Normalized text
    """
    normalizer = TextNormalizer()
    return normalizer.normalize(text)


def validate_file_tool(filename: str, file_size: int) -> str:
    """Tool function for validating files in ADK agents.
    
    Args:
        filename: Name of the file
        file_size: Size of the file in bytes
        
    Returns:
        Validation result as string
    """
    validator = FileValidator()
    result = validator.validate_file(filename, file_size)
    
    if result["valid"]:
        return f"File '{filename}' is valid ({result['file_size_mb']:.2f} MB)"
    else:
        return f"File validation failed: {', '.join(result['errors'])}"
