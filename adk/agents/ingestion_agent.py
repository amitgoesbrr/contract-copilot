"""Ingestion Agent for parsing and normalizing contract documents.

This agent handles PDF parsing, text normalization, and metadata extraction
from uploaded contract documents.
"""

import os
from typing import Dict, Optional, Union
from pathlib import Path
from loguru import logger

from google import genai
from google.genai import types

from adk.models import ContractMetadata
from adk.error_handling import (
    DocumentParsingError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger

from tools.pdf_reader import PDFReader
from tools.text_normalizer import TextNormalizer, FileValidator
from tools.metadata_extractor import MetadataExtractor


class IngestionAgent:
    """Agent responsible for document ingestion and initial processing.
    
    This agent:
    1. Validates uploaded files
    2. Extracts text from PDF or plain text files
    3. Normalizes text with encoding cleanup
    4. Extracts metadata (parties, date, jurisdiction)
    5. Prepares normalized contract for downstream agents
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite",
        max_file_size_mb: int = 10,
        max_pages: int = 30
    ):
        """Initialize the Ingestion Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for metadata extraction
            max_file_size_mb: Maximum file size in megabytes
            max_pages: Maximum number of pages to process
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.max_file_size_mb = max_file_size_mb
        self.max_pages = max_pages
        
        # Initialize tools
        self.pdf_reader = PDFReader(max_pages=max_pages)
        self.text_normalizer = TextNormalizer()
        
        # Get allowed file types from environment or use defaults
        allowed_types_str = os.getenv("ALLOWED_FILE_TYPES", "pdf,txt")
        allowed_extensions = ['.' + ext.strip() for ext in allowed_types_str.split(',')]
        
        self.file_validator = FileValidator(
            max_size_mb=max_file_size_mb,
            allowed_extensions=allowed_extensions
        )
        self.metadata_extractor = MetadataExtractor()
        
        # Initialize Gemini client (only if API key is available)
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            logger.warning("No API key provided - LLM-based metadata enhancement will be disabled")
        
        # Agent instruction for metadata extraction enhancement
        self.instruction = """You are a legal document analysis assistant specializing in contract metadata extraction.

Your task is to analyze contract text and extract key metadata:
1. Parties: Identify all parties to the contract (companies, individuals, entities)
2. Date: Find the effective date or execution date of the contract
3. Jurisdiction: Identify the governing law or jurisdiction
4. Contract Type: Classify the contract (NDA, MSA, SLA, Employment, Vendor, License, etc.)

Provide accurate, concise information. If information is not found, indicate "Not found" rather than guessing.
Focus on the first few pages where this information typically appears."""
        
        logger.info(
            "Ingestion Agent initialized",
            model=model_name,
            max_file_size_mb=max_file_size_mb,
            max_pages=max_pages
        )
    
    @log_agent_execution("IngestionAgent")
    @handle_errors(DocumentParsingError)
    def process_file(
        self,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        session_id: str = "default"
    ) -> Dict[str, any]:
        """Process a contract file (PDF or text).
        
        Args:
            file_path: Path to file on disk (for local files)
            file_bytes: File content as bytes (for uploads)
            filename: Original filename (required if using file_bytes)
            session_id: Session identifier for logging
            
        Returns:
            Dictionary containing:
                - normalized_contract: Normalized text with markers
                - metadata: ContractMetadata object
                - original_text: Raw extracted text
                - page_count: Number of pages (for PDFs)
                - file_info: File validation information
                
        Raises:
            DocumentParsingError: If file processing fails
        """
        session_logger = get_session_logger(session_id, "IngestionAgent")
        
        # Validate inputs
        if not file_path and not file_bytes:
            raise DocumentParsingError("Either file_path or file_bytes must be provided")
        
        if file_bytes and not filename:
            raise DocumentParsingError("filename must be provided when using file_bytes")
        
        # Determine file info
        if file_path:
            path = Path(file_path)
            filename = path.name
            file_size = path.stat().st_size
        else:
            file_size = len(file_bytes)
        
        session_logger.info(f"Processing file: {filename}", file_size_mb=file_size / 1024 / 1024)
        
        # Step 1: Validate file
        validation_result = self.file_validator.validate_file(
            filename=filename,
            file_size=file_size,
            file_content=file_bytes if file_bytes else None
        )
        
        if not validation_result["valid"]:
            error_msg = f"File validation failed: {', '.join(validation_result['errors'])}"
            session_logger.error(error_msg)
            raise DocumentParsingError(error_msg)
        
        if validation_result["warnings"]:
            for warning in validation_result["warnings"]:
                session_logger.warning(warning)
        
        # Step 2: Extract text based on file type
        file_ext = validation_result["file_extension"]
        pdf_metadata = None
        page_count = 1
        
        if file_ext == '.pdf':
            session_logger.info("Extracting text from PDF")
            if file_path:
                pdf_result = self.pdf_reader.read_pdf(file_path)
            else:
                pdf_result = self.pdf_reader.read_pdf_bytes(file_bytes, filename)
            
            raw_text = pdf_result["text"]
            pdf_metadata = pdf_result["metadata"]
            page_count = pdf_result["page_count"]
            
        elif file_ext in ['.txt', '.md']:
            session_logger.info(f"Reading {'markdown' if file_ext == '.md' else 'plain text'} file")
            if file_path:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_text = f.read()
            else:
                raw_text = file_bytes.decode('utf-8', errors='ignore')
            
            # Add line markers for plain text/markdown
            lines = raw_text.split('\n')
            marked_lines = [f"[LINE {i+1}] {line}" for i, line in enumerate(lines) if line.strip()]
            raw_text = '\n'.join(marked_lines)
        else:
            raise DocumentParsingError(f"Unsupported file type: {file_ext}")
        
        session_logger.info(f"Text extracted", text_length=len(raw_text))
        
        # Step 3: Normalize text
        session_logger.info("Normalizing text")
        normalized_text = self.text_normalizer.normalize_with_markers(
            raw_text,
            preserve_markers=True
        )
        
        # Step 4: Extract metadata
        session_logger.info("Extracting metadata")
        metadata = self._extract_metadata_with_llm(
            normalized_text,
            pdf_metadata,
            session_logger
        )
        
        session_logger.info(
            "File processing complete",
            parties_count=len(metadata.parties),
            contract_type=metadata.contract_type
        )
        
        return {
            "normalized_contract": normalized_text,
            "metadata": metadata,
            "original_text": raw_text,
            "page_count": page_count,
            "file_info": {
                "filename": filename,
                "file_size_mb": validation_result["file_size_mb"],
                "file_type": file_ext,
                "warnings": validation_result["warnings"]
            }
        }
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _extract_metadata_with_llm(
        self,
        text: str,
        pdf_metadata: Optional[Dict],
        session_logger
    ) -> ContractMetadata:
        """Extract metadata using rule-based extraction enhanced with LLM.
        
        Args:
            text: Normalized contract text
            pdf_metadata: Optional PDF metadata
            session_logger: Logger with session context
            
        Returns:
            ContractMetadata object
        """
        # First, use rule-based extraction
        metadata = self.metadata_extractor.extract_metadata(text, pdf_metadata)
        
        # If we're missing critical information, use LLM to enhance (if available)
        if self.client and (not metadata.parties or not metadata.contract_type):
            session_logger.info("Enhancing metadata extraction with LLM")
            
            try:
                # Use first 3000 characters for LLM analysis
                text_sample = text[:3000]
                
                prompt = f"""Analyze this contract excerpt and extract metadata:

{text_sample}

Provide the following information in a structured format:
- Parties: List all parties to the contract
- Date: Effective date or execution date
- Jurisdiction: Governing law or jurisdiction
- Contract Type: Type of contract (NDA, MSA, SLA, etc.)

Format your response as:
Parties: [party1], [party2], ...
Date: [date]
Jurisdiction: [jurisdiction]
Contract Type: [type]"""

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=500
                    )
                )
                
                llm_text = response.text
                
                # Parse LLM response to enhance metadata
                metadata = self._parse_llm_metadata_response(llm_text, metadata)
                
                session_logger.info("Metadata enhanced with LLM")
                
            except Exception as e:
                session_logger.warning(f"LLM metadata enhancement failed: {str(e)}")
                # Continue with rule-based metadata
        
        return metadata
    
    def _parse_llm_metadata_response(
        self,
        llm_response: str,
        base_metadata: ContractMetadata
    ) -> ContractMetadata:
        """Parse LLM response and merge with base metadata.
        
        Args:
            llm_response: LLM response text
            base_metadata: Base metadata from rule-based extraction
            
        Returns:
            Enhanced ContractMetadata
        """
        import re
        
        parties = base_metadata.parties
        date = base_metadata.date
        jurisdiction = base_metadata.jurisdiction
        contract_type = base_metadata.contract_type
        
        # Parse parties
        if not parties:
            parties_match = re.search(r'Parties:\s*(.+?)(?:\n|$)', llm_response, re.IGNORECASE)
            if parties_match:
                parties_str = parties_match.group(1)
                if 'not found' not in parties_str.lower():
                    parties = [p.strip() for p in parties_str.split(',')]
        
        # Parse date
        if not date:
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', llm_response, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(1).strip()
                if 'not found' not in date_str.lower():
                    date = date_str
        
        # Parse jurisdiction
        if not jurisdiction:
            jurisdiction_match = re.search(r'Jurisdiction:\s*(.+?)(?:\n|$)', llm_response, re.IGNORECASE)
            if jurisdiction_match:
                jurisdiction_str = jurisdiction_match.group(1).strip()
                if 'not found' not in jurisdiction_str.lower():
                    jurisdiction = jurisdiction_str
        
        # Parse contract type
        if not contract_type:
            type_match = re.search(r'Contract Type:\s*(.+?)(?:\n|$)', llm_response, re.IGNORECASE)
            if type_match:
                type_str = type_match.group(1).strip()
                if 'not found' not in type_str.lower():
                    contract_type = type_str.upper()
        
        return ContractMetadata(
            parties=parties,
            date=date,
            jurisdiction=jurisdiction,
            contract_type=contract_type
        )
