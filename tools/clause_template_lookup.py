"""Clause Template Lookup Tool for redline generation.

This tool provides access to the clause templates database for generating
alternative clause language in redline suggestions.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class ClauseTemplateLookup:
    """Tool for looking up clause templates for redline generation."""
    
    def __init__(self, templates_path: Optional[str] = None):
        """Initialize the clause template lookup tool.
        
        Args:
            templates_path: Path to clause_templates.json file (defaults to adk/clause_templates.json)
        """
        if templates_path is None:
            # Default to adk/clause_templates.json
            templates_path = Path(__file__).parent.parent / "adk" / "clause_templates.json"
        
        self.templates_path = Path(templates_path)
        self.templates = self._load_templates()
        
        logger.info(f"Clause templates loaded", template_count=len(self.templates))
    
    def _load_templates(self) -> Dict:
        """Load clause templates from JSON file.
        
        Returns:
            Dictionary of clause templates
            
        Raises:
            FileNotFoundError: If templates file doesn't exist
            json.JSONDecodeError: If templates file is invalid JSON
        """
        if not self.templates_path.exists():
            raise FileNotFoundError(f"Clause templates file not found: {self.templates_path}")
        
        with open(self.templates_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        return templates
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get a specific template by ID.
        
        Args:
            template_id: ID of the template
            
        Returns:
            Template dictionary or None if not found
        """
        return self.templates.get(template_id)
    
    def get_all_templates(self) -> Dict:
        """Get all clause templates.
        
        Returns:
            Dictionary of all templates
        """
        return self.templates.copy()
    
    def find_templates_by_clause_type(self, clause_type: str) -> List[Dict]:
        """Find templates matching a specific clause type.
        
        Args:
            clause_type: Type of clause (e.g., "liability", "termination")
            
        Returns:
            List of matching template dictionaries
        """
        matching_templates = []
        
        clause_type_lower = clause_type.lower()
        
        for template_id, template_data in self.templates.items():
            # Check if clause type matches any in the template's clause_types list
            if any(ct.lower() == clause_type_lower for ct in template_data.get("clause_types", [])):
                matching_templates.append({
                    "template_id": template_id,
                    **template_data
                })
        
        return matching_templates
    
    def find_templates_by_severity(self, severity: str) -> List[Dict]:
        """Find templates matching a specific severity level.
        
        Args:
            severity: Severity level (low, medium, high)
            
        Returns:
            List of matching template dictionaries
        """
        matching_templates = []
        
        severity_lower = severity.lower()
        
        for template_id, template_data in self.templates.items():
            # Check if severity matches any in the template's severity list
            if severity_lower in [s.lower() for s in template_data.get("severity", [])]:
                matching_templates.append({
                    "template_id": template_id,
                    **template_data
                })
        
        return matching_templates
    
    def find_best_template(
        self,
        clause_type: str,
        severity: str
    ) -> Optional[Dict]:
        """Find the best matching template for a clause type and severity.
        
        Args:
            clause_type: Type of clause
            severity: Severity level
            
        Returns:
            Best matching template dictionary or None if no match
        """
        clause_type_lower = clause_type.lower()
        severity_lower = severity.lower()
        
        # First, try to find templates matching both clause type and severity
        exact_matches = []
        clause_type_matches = []
        
        for template_id, template_data in self.templates.items():
            clause_types_match = any(
                ct.lower() == clause_type_lower 
                for ct in template_data.get("clause_types", [])
            )
            severity_match = severity_lower in [
                s.lower() for s in template_data.get("severity", [])
            ]
            
            if clause_types_match and severity_match:
                exact_matches.append({
                    "template_id": template_id,
                    **template_data
                })
            elif clause_types_match:
                clause_type_matches.append({
                    "template_id": template_id,
                    **template_data
                })
        
        # Return best match
        if exact_matches:
            # Prefer exact matches
            return exact_matches[0]
        elif clause_type_matches:
            # Fall back to clause type matches
            return clause_type_matches[0]
        else:
            # No matches found
            return None
    
    def get_template_variables(self, template_id: str) -> List[str]:
        """Get the list of variables for a specific template.
        
        Args:
            template_id: ID of the template
            
        Returns:
            List of variable names
        """
        template = self.get_template(template_id)
        if template:
            return template.get("variables", [])
        return []
    
    def get_templates_by_risk_mitigation(self, keyword: str) -> List[Dict]:
        """Find templates by risk mitigation keyword.
        
        Args:
            keyword: Keyword to search for in risk mitigation descriptions
            
        Returns:
            List of matching template dictionaries
        """
        matching_templates = []
        keyword_lower = keyword.lower()
        
        for template_id, template_data in self.templates.items():
            risk_mitigation = template_data.get("risk_mitigation", "").lower()
            if keyword_lower in risk_mitigation:
                matching_templates.append({
                    "template_id": template_id,
                    **template_data
                })
        
        return matching_templates
    
    def reload_templates(self):
        """Reload templates from the JSON file.
        
        Useful for picking up changes without restarting the application.
        """
        self.templates = self._load_templates()
        logger.info(f"Clause templates reloaded", template_count=len(self.templates))
