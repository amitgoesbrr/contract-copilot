"""Metadata extraction tool for contract documents.

Extracts parties, dates, jurisdiction, and contract type from contract text.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from adk.models import ContractMetadata
from adk.logging_config import log_tool_execution


class MetadataExtractor:
    """Extractor for contract metadata."""
    
    def __init__(self):
        """Initialize metadata extractor."""
        # Common patterns for metadata extraction
        self.date_patterns = [
            r'dated?\s+(?:as\s+of\s+)?([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        ]
        
        self.jurisdiction_patterns = [
            r'governed?\s+by\s+the\s+laws?\s+of\s+(?:the\s+)?([A-Z][a-z\s]+?)(?:\.|,|\s+without)',
            r'jurisdiction\s+of\s+(?:the\s+)?([A-Z][a-z\s]+?)(?:\.|,)',
            r'courts?\s+of\s+(?:the\s+)?([A-Z][a-z\s]+?)(?:\s+shall\s+have)',
        ]
        
        self.contract_type_keywords = {
            'nda': ['non-disclosure', 'confidentiality', 'nda'],
            'msa': ['master service', 'msa'],
            'sla': ['service level', 'sla'],
            'employment': ['employment agreement', 'employment contract'],
            'vendor': ['vendor agreement', 'supplier agreement'],
            'license': ['license agreement', 'licensing'],
            'lease': ['lease agreement', 'rental agreement'],
        }
    
    @log_tool_execution("metadata_extractor")
    def extract_metadata(self, text: str, pdf_metadata: Optional[Dict] = None) -> ContractMetadata:
        """Extract metadata from contract text.
        
        Args:
            text: Contract text to analyze
            pdf_metadata: Optional PDF metadata from document
            
        Returns:
            ContractMetadata object with extracted information
        """
        parties = self._extract_parties(text)
        date = self._extract_date(text, pdf_metadata)
        jurisdiction = self._extract_jurisdiction(text)
        contract_type = self._identify_contract_type(text)
        
        logger.info(
            "Metadata extracted",
            parties_count=len(parties),
            date=date,
            jurisdiction=jurisdiction,
            contract_type=contract_type
        )
        
        return ContractMetadata(
            parties=parties,
            date=date,
            jurisdiction=jurisdiction,
            contract_type=contract_type
        )
    
    def _extract_parties(self, text: str) -> List[str]:
        """Extract party names from contract text.
        
        Args:
            text: Contract text
            
        Returns:
            List of party names
        """
        parties = []
        
        # Look for common party introduction patterns
        patterns = [
            r'between\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\(|,\s+a\s+)',
            r'and\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\(|,\s+a\s+)',
            r'by\s+and\s+between\s+([A-Z][A-Za-z\s&,\.]+?)(?:\s+\(|,)',
            r'Party:\s*([A-Z][A-Za-z\s&,\.]+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text[:2000])  # Search in first 2000 chars
            for match in matches:
                party = match.group(1).strip()
                # Clean up party name
                party = re.sub(r'\s+', ' ', party)
                party = party.rstrip('.,;')
                
                if len(party) > 3 and party not in parties:
                    parties.append(party)
        
        # Limit to first 5 parties (usually 2-3 in most contracts)
        return parties[:5]
    
    def _extract_date(self, text: str, pdf_metadata: Optional[Dict] = None) -> Optional[str]:
        """Extract contract date from text or metadata.
        
        Args:
            text: Contract text
            pdf_metadata: Optional PDF metadata
            
        Returns:
            Date string or None
        """
        # Try to extract from text first
        for pattern in self.date_patterns:
            match = re.search(pattern, text[:2000])
            if match:
                date_str = match.group(1)
                # Try to parse and standardize the date
                try:
                    # This is a simple approach; could use dateutil for better parsing
                    return date_str
                except:
                    pass
        
        # Fallback to PDF metadata
        if pdf_metadata and 'creation_date' in pdf_metadata:
            creation_date = pdf_metadata['creation_date']
            if creation_date:
                return creation_date
        
        return None
    
    def _extract_jurisdiction(self, text: str) -> Optional[str]:
        """Extract jurisdiction from contract text.
        
        Args:
            text: Contract text
            
        Returns:
            Jurisdiction string or None
        """
        for pattern in self.jurisdiction_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                jurisdiction = match.group(1).strip()
                # Clean up jurisdiction
                jurisdiction = re.sub(r'\s+', ' ', jurisdiction)
                jurisdiction = jurisdiction.rstrip('.,;')
                return jurisdiction
        
        return None
    
    def _identify_contract_type(self, text: str) -> Optional[str]:
        """Identify contract type from text.
        
        Args:
            text: Contract text
            
        Returns:
            Contract type string or None
        """
        text_lower = text[:3000].lower()  # Search in first 3000 chars
        
        for contract_type, keywords in self.contract_type_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return contract_type.upper()
        
        return None


# Tool function for ADK integration
def extract_metadata_tool(text: str) -> str:
    """Tool function for extracting metadata in ADK agents.
    
    Args:
        text: Contract text
        
    Returns:
        Metadata as formatted string
    """
    extractor = MetadataExtractor()
    metadata = extractor.extract_metadata(text)
    
    result = []
    result.append(f"Parties: {', '.join(metadata.parties) if metadata.parties else 'Not found'}")
    result.append(f"Date: {metadata.date or 'Not found'}")
    result.append(f"Jurisdiction: {metadata.jurisdiction or 'Not found'}")
    result.append(f"Contract Type: {metadata.contract_type or 'Not identified'}")
    
    return '\n'.join(result)
