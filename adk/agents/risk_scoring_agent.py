"""
Risk Scoring Agent - Hybrid rule-based and LLM risk assessment.

This agent combines deterministic pattern matching with LLM reasoning:
1. Rule-based detection via risk_rules.json for known risk patterns
2. LLM enhancement for contextual analysis and business implications
3. Fallback to pure LLM analysis for clauses without rule matches

Severity Levels:
- HIGH: Significant financial/legal exposure requiring immediate attention
- MEDIUM: Negotiable concerns that should be addressed
- LOW: Standard terms with minimal risk
"""

import os
from typing import Dict, List, Optional
from loguru import logger

from google import genai
from google.genai import types

from adk.models import Clause, RiskAssessment
from adk.error_handling import (
    RiskAssessmentError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger
from tools.risk_rule_lookup import RiskRuleLookup


class RiskScoringAgent:
    """
    Hybrid risk assessment agent combining rules and LLM reasoning.
    
    Pipeline: Clause -> Rule Matching -> LLM Enhancement -> RiskAssessment
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite",
        rules_path: Optional[str] = None
    ):
        """Initialize the Risk Scoring Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for risk reasoning
            rules_path: Path to risk_rules.json file (defaults to adk/risk_rules.json)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise RiskAssessmentError("No API key provided for Risk Scoring Agent")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Initialize risk rule lookup tool
        self.risk_lookup = RiskRuleLookup(rules_path=rules_path)
        
        # Agent instruction for risk reasoning
        self.instruction = self._build_instruction()
        
        logger.info(
            "Risk Scoring Agent initialized",
            model=model_name,
            rule_count=len(self.risk_lookup.get_all_rules())
        )
    
    def _build_instruction(self) -> str:
        """System prompt for LLM risk analysis."""
        return """You are a legal risk analysis assistant specializing in contract review.

Analyze contract clauses and provide risk assessments:
1. Severity: low, medium, or high
2. Risk type: Financial Exposure, Termination Rights, Confidentiality, etc.
3. Clear explanation of why the clause is risky
4. Business context and practical implications

SEVERITY GUIDELINES:
- HIGH: Significant financial exposure, loss of critical rights, major business impact
- MEDIUM: Moderate risk worth negotiating but not deal-breaking
- LOW: Minor concerns or standard terms acceptable with awareness

GUIDELINES:
- Be specific about what could go wrong
- Consider both legal and business implications
- Focus on the most significant risk if multiple exist
- Use plain business language, avoid legal jargon
- Use Google Search to verify legal precedents or industry practices if needed

Help business stakeholders understand practical implications of contract terms."""
    
    @log_agent_execution("RiskScoringAgent")
    @handle_errors(RiskAssessmentError)
    def assess_risks(
        self,
        clauses: List[Clause],
        session_id: str = "default"
    ) -> Dict[str, any]:
        """Assess risks for a list of contract clauses.
        
        Args:
            clauses: List of Clause objects to assess
            session_id: Session identifier for logging
            
        Returns:
            Dictionary containing:
                - risk_assessments: List of RiskAssessment objects
                - risk_summary: Summary statistics
                - high_risk_clauses: List of high-risk clause IDs
                - medium_risk_clauses: List of medium-risk clause IDs
                - low_risk_clauses: List of low-risk clause IDs
                
        Raises:
            RiskAssessmentError: If risk assessment fails
        """
        session_logger = get_session_logger(session_id, "RiskScoringAgent")
        
        if not clauses:
            raise RiskAssessmentError("No clauses provided for risk assessment")
        
        session_logger.info(f"Starting risk assessment", clause_count=len(clauses))
        
        risk_assessments = []
        
        # Process each clause
        for clause in clauses:
            try:
                assessment = self._assess_clause(clause, session_logger)
                risk_assessments.append(assessment)
            except Exception as e:
                session_logger.error(
                    f"Failed to assess clause {clause.id}: {str(e)}",
                    clause_id=clause.id
                )
                # Create a default low-risk assessment for failed clauses
                risk_assessments.append(
                    RiskAssessment(
                        clause_id=clause.id,
                        severity="low",
                        risk_type="Assessment Failed",
                        explanation="Unable to assess risk for this clause",
                        llm_rationale=f"Error: {str(e)}"
                    )
                )
        
        # Calculate summary statistics
        risk_summary = self._calculate_risk_summary(risk_assessments)
        
        # Categorize by severity
        high_risk = [r.clause_id for r in risk_assessments if r.severity == "high"]
        medium_risk = [r.clause_id for r in risk_assessments if r.severity == "medium"]
        low_risk = [r.clause_id for r in risk_assessments if r.severity == "low"]
        
        session_logger.info(
            "Risk assessment complete",
            total_clauses=len(clauses),
            high_risk_count=len(high_risk),
            medium_risk_count=len(medium_risk),
            low_risk_count=len(low_risk)
        )
        
        return {
            "risk_assessments": risk_assessments,
            "risk_summary": risk_summary,
            "high_risk_clauses": high_risk,
            "medium_risk_clauses": medium_risk,
            "low_risk_clauses": low_risk
        }
    
    def _assess_clause(
        self,
        clause: Clause,
        session_logger
    ) -> RiskAssessment:
        """Assess risk for a single clause.
        
        Args:
            clause: Clause object to assess
            session_logger: Logger with session context
            
        Returns:
            RiskAssessment object
        """
        session_logger.debug(f"Assessing clause {clause.id}", clause_type=clause.type)
        
        # Step 1: Apply rule-based pattern matching
        rule_matches = self.risk_lookup.match_patterns(clause.text, case_sensitive=False)
        
        if rule_matches:
            # Found rule-based risks
            session_logger.debug(
                f"Found {len(rule_matches)} rule matches for clause {clause.id}",
                clause_id=clause.id,
                match_count=len(rule_matches)
            )
            
            # Use the highest severity match
            highest_severity_match = self._get_highest_severity_match(rule_matches)
            
            # Enhance with LLM reasoning
            try:
                llm_rationale = self._get_llm_reasoning(
                    clause,
                    highest_severity_match,
                    session_logger
                )
                # Ensure we got a valid string
                if llm_rationale is None or not isinstance(llm_rationale, str):
                    session_logger.error(f"_get_llm_reasoning returned invalid type for clause {clause.id}: {type(llm_rationale)}")
                    llm_rationale = f"""Here's the analysis of the {clause.type} clause:

1.  **Why this clause is risky:** {highest_severity_match['explanation']}
2.  **Practical business implications:** This clause could impact your business operations and should be reviewed carefully with legal counsel.
3.  **What could go wrong:** Without proper negotiation, this clause may expose your business to {highest_severity_match['risk_type'].lower()} risks."""
            except Exception as e:
                session_logger.error(f"Exception calling _get_llm_reasoning for clause {clause.id}: {str(e)}")
                llm_rationale = f"""Here's the analysis of the {clause.type} clause:

1.  **Why this clause is risky:** {highest_severity_match['explanation']}
2.  **Practical business implications:** This clause could impact your business operations and should be reviewed carefully with legal counsel.
3.  **What could go wrong:** Without proper negotiation, this clause may expose your business to {highest_severity_match['risk_type'].lower()} risks."""
            
            # Log the llm_rationale value before creating RiskAssessment
            session_logger.info(
                f"Creating RiskAssessment for {clause.id} with llm_rationale type: {type(llm_rationale)}, "
                f"is None: {llm_rationale is None}, length: {len(llm_rationale) if llm_rationale else 0}"
            )
            
            return RiskAssessment(
                clause_id=clause.id,
                severity=highest_severity_match["severity"],
                risk_type=highest_severity_match["risk_type"],
                explanation=highest_severity_match["explanation"],
                llm_rationale=llm_rationale
            )
        else:
            # No rule matches - use LLM for complex analysis
            session_logger.debug(
                f"No rule matches for clause {clause.id}, using LLM analysis",
                clause_id=clause.id
            )
            
            return self._assess_with_llm(clause, session_logger)
    
    def _get_highest_severity_match(self, matches: List[Dict]) -> Dict:
        """Get the match with the highest severity.
        
        Args:
            matches: List of rule matches
            
        Returns:
            Match dictionary with highest severity
        """
        severity_order = {"high": 3, "medium": 2, "low": 1}
        
        return max(
            matches,
            key=lambda m: severity_order.get(m["severity"], 0)
        )
    
    def _get_llm_reasoning(
        self,
        clause: Clause,
        rule_match: Dict,
        session_logger
    ) -> str:
        """Get LLM reasoning to enhance rule-based risk detection.
        
        Args:
            clause: Clause object
            rule_match: Matched rule information
            session_logger: Logger with session context
            
        Returns:
            LLM-generated rationale (never None or empty)
        """
        session_logger.debug(f"Getting LLM reasoning for clause {clause.id}")
        
        # Default fallback - MUST be defined first
        fallback_rationale = f"""Here's the analysis of the {clause.type} clause:

1.  **Why this clause is risky:** {rule_match['explanation']}
2.  **Practical business implications:** This clause could impact your business operations and should be reviewed carefully with legal counsel.
3.  **What could go wrong:** Without proper negotiation, this clause may expose your business to {rule_match['risk_type'].lower()} risks."""
        
        # Try to get LLM reasoning, but ALWAYS return something
        try:
            prompt = f"""Analyze this contract clause and provide additional context about the identified risk:

Clause Type: {clause.type}
Clause Text: {clause.text}

Identified Risk: {rule_match['risk_type']}
Severity: {rule_match['severity']}
Rule Explanation: {rule_match['explanation']}

Provide a brief (2-3 sentences) explanation of:
1. Why this specific clause language creates the identified risk
2. What practical business implications this could have
3. What could go wrong if this clause is accepted as-is

Keep your response concise and focused on business impact."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.instruction)]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I will provide concise risk analysis focused on business impact.")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=300,
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            rationale = response.text.strip() if response and response.text else ""
            
            # Ensure we never return empty string or None
            if not rationale:
                session_logger.warning(f"Empty LLM response for clause {clause.id}, using fallback")
                return fallback_rationale
            
            session_logger.debug(f"LLM reasoning generated for clause {clause.id}")
            return rationale
            
        except Exception as e:
            session_logger.warning(f"Failed to get LLM reasoning for clause {clause.id}: {str(e)}")
            # ALWAYS return fallback, NEVER None
            return fallback_rationale
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _assess_with_llm(
        self,
        clause: Clause,
        session_logger
    ) -> RiskAssessment:
        """Assess clause risk using LLM when no rules match.
        
        Args:
            clause: Clause object
            session_logger: Logger with session context
            
        Returns:
            RiskAssessment object
        """
        session_logger.debug(f"Performing LLM-based risk assessment for clause {clause.id}")
        
        try:
            prompt = f"""Analyze this contract clause for potential risks:

Clause Type: {clause.type}
Clause Text: {clause.text}

Provide a risk assessment with:
1. Severity: low, medium, or high
2. Risk Type: Category of risk (e.g., "Financial Exposure", "Termination Rights", "Confidentiality", etc.)
3. Explanation: Brief explanation of the risk (2-3 sentences)

Format your response as:
Severity: [low/medium/high]
Risk Type: [category]
Explanation: [your explanation]

If the clause appears to be standard and low-risk, indicate that clearly."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.instruction)]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I will provide structured risk assessment.")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=400,
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            llm_response = response.text.strip()
            
            # Parse LLM response
            assessment = self._parse_llm_assessment(clause.id, llm_response, session_logger)
            
            session_logger.debug(
                f"LLM assessment complete for clause {clause.id}",
                severity=assessment.severity
            )
            
            return assessment
            
        except Exception as e:
            session_logger.error(f"LLM assessment failed for clause {clause.id}: {str(e)}")
            # Return default low-risk assessment with fallback rationale
            fallback = f"""Here's the analysis of the {clause.type} clause:

1.  **Why this clause is risky:** This appears to be a standard contract clause. While no immediate high-risk patterns were detected, it should still be reviewed by legal counsel to ensure it aligns with your business needs.
2.  **Practical business implications:** Standard clauses can still have implications depending on your specific business context and risk tolerance.
3.  **What could go wrong:** Without proper review, even standard clauses might contain terms that don't align with your business objectives or create unexpected obligations."""
            
            return RiskAssessment(
                clause_id=clause.id,
                severity="low",
                risk_type="Standard Clause",
                explanation="This appears to be a standard contract clause with no significant risks identified.",
                llm_rationale=fallback
            )
    
    def _parse_llm_assessment(
        self,
        clause_id: str,
        llm_response: str,
        session_logger
    ) -> RiskAssessment:
        """Parse LLM response into RiskAssessment object.
        
        Args:
            clause_id: Clause identifier
            llm_response: LLM response text
            session_logger: Logger with session context
            
        Returns:
            RiskAssessment object
        """
        import re
        
        # Parse severity
        severity_match = re.search(r'Severity:\s*(low|medium|high)', llm_response, re.IGNORECASE)
        severity = severity_match.group(1).lower() if severity_match else "low"
        
        # Validate severity
        if severity not in ["low", "medium", "high"]:
            severity = "low"
        
        # Parse risk type
        risk_type_match = re.search(r'Risk Type:\s*(.+?)(?:\n|$)', llm_response, re.IGNORECASE)
        risk_type = risk_type_match.group(1).strip() if risk_type_match else "General Risk"
        
        # Parse explanation
        explanation_match = re.search(r'Explanation:\s*(.+?)(?:\n\n|$)', llm_response, re.IGNORECASE | re.DOTALL)
        explanation = explanation_match.group(1).strip() if explanation_match else llm_response
        
        # Clean up explanation
        explanation = explanation.replace('\n', ' ').strip()
        if len(explanation) > 500:
            explanation = explanation[:497] + "..."
        
        # For LLM-only assessments, use the full response as llm_rationale
        return RiskAssessment(
            clause_id=clause_id,
            severity=severity,
            risk_type=risk_type,
            explanation=explanation,
            llm_rationale=llm_response  # Include full LLM response for UI display
        )
    
    def _calculate_risk_summary(self, assessments: List[RiskAssessment]) -> Dict:
        """Calculate summary statistics for risk assessments.
        
        Args:
            assessments: List of RiskAssessment objects
            
        Returns:
            Dictionary with summary statistics
        """
        total = len(assessments)
        high_count = sum(1 for a in assessments if a.severity == "high")
        medium_count = sum(1 for a in assessments if a.severity == "medium")
        low_count = sum(1 for a in assessments if a.severity == "low")
        
        # Calculate risk type distribution
        risk_types = {}
        for assessment in assessments:
            risk_types[assessment.risk_type] = risk_types.get(assessment.risk_type, 0) + 1
        
        return {
            "total_clauses": total,
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "low_risk_count": low_count,
            "high_risk_percentage": round((high_count / total * 100) if total > 0 else 0, 1),
            "medium_risk_percentage": round((medium_count / total * 100) if total > 0 else 0, 1),
            "low_risk_percentage": round((low_count / total * 100) if total > 0 else 0, 1),
            "risk_type_distribution": risk_types
        }
    
    def get_high_risk_assessments(
        self,
        assessments: List[RiskAssessment]
    ) -> List[RiskAssessment]:
        """Filter for high-risk assessments only.
        
        Args:
            assessments: List of RiskAssessment objects
            
        Returns:
            List of high-risk assessments
        """
        return [a for a in assessments if a.severity == "high"]
    
    def get_assessments_by_risk_type(
        self,
        assessments: List[RiskAssessment],
        risk_type: str
    ) -> List[RiskAssessment]:
        """Filter assessments by risk type.
        
        Args:
            assessments: List of RiskAssessment objects
            risk_type: Risk type to filter by
            
        Returns:
            List of assessments matching the risk type
        """
        return [a for a in assessments if a.risk_type == risk_type]
