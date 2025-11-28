"""Clause Extraction Agent for identifying and classifying contract clauses.

This agent uses Gemini to extract individual clauses from normalized contract text,
classify them by type, and preserve original text indices for traceability.
"""

import os
import re
import hashlib
from typing import Dict, List, Optional
from loguru import logger

from google import genai
from google.genai import types
import msgspec

from adk.models import Clause
from adk.error_handling import (
    ExtractionError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger


class ClauseExtractionAgent:
    """Agent responsible for extracting and classifying contract clauses.
    
    This agent:
    1. Identifies individual clauses within contract text
    2. Classifies clauses by type (confidentiality, indemnification, etc.)
    3. Preserves original text indices and line numbers
    4. Outputs structured JSON validated with msgspec
    5. Maintains traceability to source document
    """
    
    # Supported clause types
    CLAUSE_TYPES = [
        "confidentiality",
        "indemnification",
        "termination",
        "governing_law",
        "liability",
        "payment_terms",
        "intellectual_property",
        "warranties",
        "dispute_resolution",
        "force_majeure",
        "assignment",
        "amendment",
        "notices",
        "entire_agreement",
        "severability",
        "other"
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite"
    ):
        """Initialize the Clause Extraction Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for clause extraction
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise ExtractionError("No API key provided for Clause Extraction Agent")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Agent instruction for clause extraction
        self.instruction = self._build_instruction()
        
        # JSON decoder for msgspec
        self.decoder = msgspec.json.Decoder(List[Clause])
        
        logger.info(
            "Clause Extraction Agent initialized",
            model=model_name
        )
    
    def _build_instruction(self) -> str:
        """Build the system instruction for clause extraction.
        
        Returns:
            System instruction string
        """
        clause_types_str = ", ".join(self.CLAUSE_TYPES)
        
        return f"""You are a legal document analysis assistant specializing in contract clause extraction and classification.

Your task is to analyze contract text and extract individual clauses with the following information:
1. Identify distinct clauses or provisions within the contract
2. Classify each clause by type: {clause_types_str}
3. Extract the exact text of each clause
4. Preserve line numbers and page markers from the original text
5. Assign a unique ID to each clause

IMPORTANT GUIDELINES:
- A clause is a distinct provision or section of the contract (e.g., "Confidentiality", "Termination", "Payment Terms")
- Extract complete clauses including all sub-provisions
- Preserve the exact original text without modification
- Use line markers [LINE X] and [PAGE X] to determine start_line, end_line, and page_number
- If a clause doesn't fit standard types, classify it as "other"
- Be thorough - extract ALL meaningful clauses from the contract

OUTPUT FORMAT:
You must respond with a JSON array of clause objects. Each clause object must have:
- id: string (format: "clause_N" where N is sequential)
- type: string (one of the clause types listed above)
- text: string (exact clause text from the contract)
- start_line: integer (line number where clause starts)
- end_line: integer (line number where clause ends)
- page_number: integer (page number where clause appears)

Example output:
[
  {{
    "id": "clause_1",
    "type": "confidentiality",
    "text": "The Receiving Party agrees to maintain in confidence...",
    "start_line": 45,
    "end_line": 52,
    "page_number": 2
  }},
  {{
    "id": "clause_2",
    "type": "termination",
    "text": "Either party may terminate this Agreement...",
    "start_line": 78,
    "end_line": 85,
    "page_number": 3
  }}
]

Respond ONLY with the JSON array, no additional text or explanation."""
        
    @log_agent_execution("ClauseExtractionAgent")
    @handle_errors(ExtractionError)
    def extract_clauses(
        self,
        normalized_text: str,
        session_id: str = "default"
    ) -> Dict[str, any]:
        """Extract clauses from normalized contract text.
        
        Args:
            normalized_text: Normalized contract text with line/page markers
            session_id: Session identifier for logging
            
        Returns:
            Dictionary containing:
                - clauses: List of Clause objects
                - clause_count: Number of extracted clauses
                - clause_types: Distribution of clause types
                - extraction_metadata: Metadata about the extraction
                
        Raises:
            ExtractionError: If clause extraction fails
        """
        session_logger = get_session_logger(session_id, "ClauseExtractionAgent")
        
        if not normalized_text or not normalized_text.strip():
            raise ExtractionError("Empty or invalid normalized text provided")
        
        text_length = len(normalized_text)
        session_logger.info(f"Starting clause extraction", text_length=text_length)
        
        # Extract clauses using LLM
        clauses = self._extract_with_llm(normalized_text, session_logger)
        
        # Validate and post-process clauses
        clauses = self._validate_clauses(clauses, normalized_text, session_logger)
        
        # Calculate statistics
        clause_types_dist = self._calculate_type_distribution(clauses)
        
        session_logger.info(
            "Clause extraction complete",
            clause_count=len(clauses),
            clause_types=clause_types_dist
        )
        
        return {
            "clauses": clauses,
            "clause_count": len(clauses),
            "clause_types": clause_types_dist,
            "extraction_metadata": {
                "text_length": text_length,
                "model": self.model_name,
                "session_id": session_id
            }
        }
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _extract_with_llm(
        self,
        text: str,
        session_logger
    ) -> List[Clause]:
        """Extract clauses using Gemini LLM.
        
        Args:
            text: Normalized contract text
            session_logger: Logger with session context
            
        Returns:
            List of Clause objects
            
        Raises:
            ExtractionError: If LLM extraction fails
        """
        session_logger.info("Calling Gemini for clause extraction")
        
        try:
            # Prepare prompt
            prompt = f"""Extract all clauses from the following contract text:

{text}

Remember to respond with ONLY a JSON array of clause objects."""
            
            # Call Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.instruction)]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I will extract clauses and respond with only a JSON array.")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8000,
                    response_mime_type="application/json"
                )
            )
            
            response_text = response.text
            session_logger.info("Received LLM response", response_length=len(response_text))
            
            # Parse JSON response
            clauses = self._parse_json_response(response_text, session_logger)
            
            return clauses
            
        except Exception as e:
            session_logger.error(f"LLM extraction failed: {str(e)}")
            raise ExtractionError(f"Failed to extract clauses with LLM: {str(e)}")
    
    def _parse_json_response(
        self,
        response_text: str,
        session_logger
    ) -> List[Clause]:
        """Parse JSON response and validate with msgspec.
        
        Args:
            response_text: JSON response from LLM
            session_logger: Logger with session context
            
        Returns:
            List of validated Clause objects
            
        Raises:
            ExtractionError: If JSON parsing fails
        """
        try:
            # Clean response text (remove markdown code blocks if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Decode with msgspec
            clauses = self.decoder.decode(cleaned_text.encode('utf-8'))
            
            session_logger.info(f"Parsed {len(clauses)} clauses from JSON")
            
            return clauses
            
        except msgspec.DecodeError as e:
            session_logger.error(f"JSON decode error: {str(e)}")
            session_logger.debug(f"Response text: {response_text[:500]}")
            raise ExtractionError(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            session_logger.error(f"Unexpected parsing error: {str(e)}")
            raise ExtractionError(f"Failed to parse clause response: {str(e)}")
    
    def _validate_clauses(
        self,
        clauses: List[Clause],
        original_text: str,
        session_logger
    ) -> List[Clause]:
        """Validate and post-process extracted clauses.
        
        Args:
            clauses: List of extracted clauses
            original_text: Original normalized text
            session_logger: Logger with session context
            
        Returns:
            List of validated clauses
        """
        validated_clauses = []
        
        for i, clause in enumerate(clauses):
            # Validate clause type
            if clause.type not in self.CLAUSE_TYPES:
                session_logger.warning(
                    f"Invalid clause type '{clause.type}' for clause {clause.id}, setting to 'other'"
                )
                # Create new clause with corrected type
                clause = Clause(
                    id=clause.id,
                    type="other",
                    text=clause.text,
                    start_line=clause.start_line,
                    end_line=clause.end_line,
                    page_number=clause.page_number
                )
            
            # Validate line numbers
            if clause.start_line > clause.end_line:
                session_logger.warning(
                    f"Invalid line numbers for clause {clause.id}: start={clause.start_line}, end={clause.end_line}"
                )
                # Swap them
                clause = Clause(
                    id=clause.id,
                    type=clause.type,
                    text=clause.text,
                    start_line=clause.end_line,
                    end_line=clause.start_line,
                    page_number=clause.page_number
                )
            
            # Validate text is not empty
            if not clause.text or not clause.text.strip():
                session_logger.warning(f"Empty text for clause {clause.id}, skipping")
                continue
            
            validated_clauses.append(clause)
        
        session_logger.info(
            f"Validated {len(validated_clauses)} clauses",
            skipped=len(clauses) - len(validated_clauses)
        )
        
        return validated_clauses
    
    def _calculate_type_distribution(self, clauses: List[Clause]) -> Dict[str, int]:
        """Calculate distribution of clause types.
        
        Args:
            clauses: List of clauses
            
        Returns:
            Dictionary mapping clause type to count
        """
        distribution = {}
        for clause in clauses:
            distribution[clause.type] = distribution.get(clause.type, 0) + 1
        
        return distribution
    
    def extract_clause_by_id(
        self,
        clause_id: str,
        clauses: List[Clause]
    ) -> Optional[Clause]:
        """Find a clause by its ID.
        
        Args:
            clause_id: Clause identifier
            clauses: List of clauses to search
            
        Returns:
            Clause object or None if not found
        """
        for clause in clauses:
            if clause.id == clause_id:
                return clause
        return None
    
    def filter_clauses_by_type(
        self,
        clause_type: str,
        clauses: List[Clause]
    ) -> List[Clause]:
        """Filter clauses by type.
        
        Args:
            clause_type: Type of clause to filter
            clauses: List of clauses to filter
            
        Returns:
            List of clauses matching the type
        """
        return [c for c in clauses if c.type == clause_type]
