"""Risk Rule Lookup Tool for contract risk assessment.

This tool provides access to the risk rules database for pattern-based
risk detection in contract clauses.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class RiskRuleLookup:
    """Tool for looking up risk rules and matching patterns against text."""
    
    def __init__(self, rules_path: Optional[str] = None):
        """Initialize the risk rule lookup tool.
        
        Args:
            rules_path: Path to risk_rules.json file (defaults to adk/risk_rules.json)
        """
        if rules_path is None:
            # Default to adk/risk_rules.json
            rules_path = Path(__file__).parent.parent / "adk" / "risk_rules.json"
        
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()
        
        logger.info(f"Risk rules loaded", rule_count=len(self.rules))
    
    def _load_rules(self) -> Dict:
        """Load risk rules from JSON file.
        
        Returns:
            Dictionary of risk rules
            
        Raises:
            FileNotFoundError: If rules file doesn't exist
            json.JSONDecodeError: If rules file is invalid JSON
        """
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Risk rules file not found: {self.rules_path}")
        
        with open(self.rules_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        return rules
    
    def get_rule(self, rule_name: str) -> Optional[Dict]:
        """Get a specific risk rule by name.
        
        Args:
            rule_name: Name of the risk rule
            
        Returns:
            Risk rule dictionary or None if not found
        """
        return self.rules.get(rule_name)
    
    def get_all_rules(self) -> Dict:
        """Get all risk rules.
        
        Returns:
            Dictionary of all risk rules
        """
        return self.rules.copy()
    
    def match_patterns(self, text: str, case_sensitive: bool = False) -> List[Dict]:
        """Match text against all risk rule patterns.
        
        Args:
            text: Text to match against patterns
            case_sensitive: Whether to use case-sensitive matching
            
        Returns:
            List of matched rules with match information
        """
        matches = []
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for rule_name, rule_data in self.rules.items():
            pattern = rule_data["pattern"]
            
            try:
                regex = re.compile(pattern, flags)
                match = regex.search(text)
                
                if match:
                    matches.append({
                        "rule_name": rule_name,
                        "severity": rule_data["severity"],
                        "risk_type": rule_data["risk_type"],
                        "explanation": rule_data["explanation"],
                        "matched_text": match.group(0),
                        "match_start": match.start(),
                        "match_end": match.end()
                    })
                    
            except re.error as e:
                logger.warning(f"Invalid regex pattern in rule '{rule_name}': {e}")
                continue
        
        return matches
    
    def get_rules_by_severity(self, severity: str) -> Dict:
        """Get all rules of a specific severity level.
        
        Args:
            severity: Severity level (low, medium, high)
            
        Returns:
            Dictionary of rules matching the severity level
        """
        return {
            name: rule
            for name, rule in self.rules.items()
            if rule["severity"] == severity
        }
    
    def get_rules_by_risk_type(self, risk_type: str) -> Dict:
        """Get all rules of a specific risk type.
        
        Args:
            risk_type: Risk type (e.g., "Financial Exposure", "Termination Rights")
            
        Returns:
            Dictionary of rules matching the risk type
        """
        return {
            name: rule
            for name, rule in self.rules.items()
            if rule["risk_type"] == risk_type
        }
    
    def reload_rules(self):
        """Reload rules from the JSON file.
        
        Useful for picking up changes without restarting the application.
        """
        self.rules = self._load_rules()
        logger.info(f"Risk rules reloaded", rule_count=len(self.rules))
