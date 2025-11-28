"""
Redline Suggestion Agent - Generate safer alternative clause language.

This agent creates negotiation-ready redline proposals for risky clauses:
1. Template matching from clause_templates.json for common patterns
2. LLM adaptation to fit specific contract context
3. Unified diff generation for clear change visualization
4. Business-friendly rationales explaining risk mitigations

Only processes HIGH and MEDIUM severity clauses to focus on actionable items.
"""

import os
import difflib
from typing import Dict, List, Optional
from loguru import logger

from google import genai
from google.genai import types

from adk.models import Clause, RiskAssessment, RedlineProposal
from adk.error_handling import (
    RedlineGenerationError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger
from tools.clause_template_lookup import ClauseTemplateLookup


class RedlineSuggestionAgent:
    """
    Generates alternative clause language with risk mitigations.
    
    Pipeline: Risky Clause -> Template Match -> LLM Adaptation -> RedlineProposal
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite",
        templates_path: Optional[str] = None
    ):
        """Initialize the Redline Suggestion Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for redline generation
            templates_path: Path to clause_templates.json file
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise RedlineGenerationError("No API key provided for Redline Suggestion Agent")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Initialize clause template lookup tool
        self.template_lookup = ClauseTemplateLookup(templates_path=templates_path)
        
        # Agent instruction for redline generation
        self.instruction = self._build_instruction()
        
        logger.info(
            "Redline Suggestion Agent initialized",
            model=model_name,
            template_count=len(self.template_lookup.get_all_templates())
        )
    
    def _build_instruction(self) -> str:
        """System prompt for LLM redline generation."""
        return """You are a legal contract negotiation assistant specializing in redline suggestions.

Generate alternative clause language that reduces risk while maintaining business viability.

REDLINE GUIDELINES:
- Preserve core business intent of the original clause
- Use clear, unambiguous language that reduces identified risks
- Adapt templates to fit specific contract context
- Ensure redlines are realistic and negotiable (not one-sided)
- Keep similar length to original clause

RATIONALE GUIDELINES:
- Explain why the redline is safer (2-3 sentences max)
- Highlight specific risk mitigations
- Use business-friendly language stakeholders can understand

IMPORTANT:
- Don't make redlines overly favorable to one party
- If a template doesn't fit, create custom language
- Focus on practical, negotiable alternatives"""
    
    @log_agent_execution("RedlineSuggestionAgent")
    @handle_errors(RedlineGenerationError)
    def generate_redlines(
        self,
        clauses: List[Clause],
        risk_assessments: List[RiskAssessment],
        session_id: str = "default"
    ) -> Dict[str, any]:
        """Generate redline suggestions for risky clauses.
        
        Args:
            clauses: List of Clause objects
            risk_assessments: List of RiskAssessment objects
            session_id: Session identifier for logging
            
        Returns:
            Dictionary containing:
                - redline_proposals: List of RedlineProposal objects
                - high_risk_redlines: List of redlines for high-risk clauses
                - medium_risk_redlines: List of redlines for medium-risk clauses
                - redline_summary: Summary statistics
                
        Raises:
            RedlineGenerationError: If redline generation fails
        """
        session_logger = get_session_logger(session_id, "RedlineSuggestionAgent")
        
        if not clauses:
            raise RedlineGenerationError("No clauses provided for redline generation")
        
        if not risk_assessments:
            raise RedlineGenerationError("No risk assessments provided for redline generation")
        
        # Create lookup map for clauses and risk assessments
        clause_map = {c.id: c for c in clauses}
        risk_map = {r.clause_id: r for r in risk_assessments}
        
        # Filter for high and medium risk clauses
        risky_assessments = [
            r for r in risk_assessments
            if r.severity in ["high", "medium"]
        ]
        
        session_logger.info(
            f"Starting redline generation",
            total_clauses=len(clauses),
            risky_clauses=len(risky_assessments)
        )
        
        if not risky_assessments:
            session_logger.info("No high or medium risk clauses found - no redlines needed")
            return {
                "redline_proposals": [],
                "proposal_count": 0,
                "high_risk_redlines": [],
                "medium_risk_redlines": [],
                "redline_summary": {
                    "total_redlines": 0,
                    "high_risk_count": 0,
                    "medium_risk_count": 0
                }
            }
        
        redline_proposals = []
        
        # Generate redline for each risky clause
        for risk_assessment in risky_assessments:
            clause = clause_map.get(risk_assessment.clause_id)
            
            if not clause:
                session_logger.warning(
                    f"Clause not found for risk assessment: {risk_assessment.clause_id}"
                )
                continue
            
            try:
                redline = self._generate_redline_for_clause(
                    clause,
                    risk_assessment,
                    session_logger
                )
                redline_proposals.append(redline)
            except Exception as e:
                session_logger.error(
                    f"Failed to generate redline for clause {clause.id}: {str(e)}",
                    clause_id=clause.id
                )
                # Continue with other clauses
        
        # Categorize by severity
        high_risk_redlines = [
            r for r in redline_proposals
            if risk_map.get(r.clause_id) and risk_map[r.clause_id].severity == "high"
        ]
        medium_risk_redlines = [
            r for r in redline_proposals
            if risk_map.get(r.clause_id) and risk_map[r.clause_id].severity == "medium"
        ]
        
        redline_summary = {
            "total_redlines": len(redline_proposals),
            "high_risk_count": len(high_risk_redlines),
            "medium_risk_count": len(medium_risk_redlines)
        }
        
        session_logger.info(
            "Redline generation complete",
            total_redlines=len(redline_proposals),
            high_risk_count=len(high_risk_redlines),
            medium_risk_count=len(medium_risk_redlines)
        )
        
        return {
            "redline_proposals": redline_proposals,
            "proposal_count": len(redline_proposals),
            "high_risk_redlines": high_risk_redlines,
            "medium_risk_redlines": medium_risk_redlines,
            "redline_summary": redline_summary
        }
    
    def _generate_redline_for_clause(
        self,
        clause: Clause,
        risk_assessment: RiskAssessment,
        session_logger
    ) -> RedlineProposal:
        """Generate a redline proposal for a single clause.
        
        Args:
            clause: Clause object
            risk_assessment: RiskAssessment object for the clause
            session_logger: Logger with session context
            
        Returns:
            RedlineProposal object
        """
        session_logger.debug(
            f"Generating redline for clause {clause.id}",
            clause_type=clause.type,
            severity=risk_assessment.severity
        )
        
        # Find best matching template
        best_template = self.template_lookup.find_best_template(
            clause.type,
            risk_assessment.severity
        )
        
        if best_template:
            session_logger.debug(
                f"Using template {best_template['template_id']} for clause {clause.id}"
            )
            
            # Generate redline using template
            proposed_text, rationale = self._generate_with_template(
                clause,
                risk_assessment,
                best_template,
                session_logger
            )
        else:
            session_logger.debug(
                f"No template found for clause {clause.id}, using LLM-only generation"
            )
            
            # Generate redline without template
            proposed_text, rationale = self._generate_without_template(
                clause,
                risk_assessment,
                session_logger
            )
        
        # Generate unified diff
        diff = self._generate_diff(clause.text, proposed_text)
        
        return RedlineProposal(
            clause_id=clause.id,
            original_text=clause.text,
            proposed_text=proposed_text,
            rationale=rationale,
            diff=diff
        )
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_with_template(
        self,
        clause: Clause,
        risk_assessment: RiskAssessment,
        template: Dict,
        session_logger
    ) -> tuple[str, str]:
        """Generate redline using a clause template.
        
        Args:
            clause: Clause object
            risk_assessment: RiskAssessment object
            template: Template dictionary
            session_logger: Logger with session context
            
        Returns:
            Tuple of (proposed_text, rationale)
        """
        session_logger.debug(f"Generating redline with template for clause {clause.id}")
        
        try:
            prompt = f"""Generate a redline suggestion for this contract clause using the provided template.

ORIGINAL CLAUSE:
Type: {clause.type}
Text: {clause.text}

IDENTIFIED RISK:
Severity: {risk_assessment.severity}
Risk Type: {risk_assessment.risk_type}
Explanation: {risk_assessment.explanation}

TEMPLATE TO USE:
{template['template']}

Template Variables: {template.get('variables', [])}
Risk Mitigation: {template['risk_mitigation']}

INSTRUCTIONS:
1. Adapt the template to fit this specific contract context
2. Fill in any template variables with appropriate values based on the original clause
3. Ensure the redline maintains the business intent while reducing risk
4. Keep the language professional and legally appropriate

Provide your response in this format:
PROPOSED CLAUSE: [your redline text]
RATIONALE: [2-3 sentence explanation of why this is safer]"""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.instruction)]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I will generate contextually appropriate redline suggestions.")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=600
                )
            )
            
            llm_response = response.text.strip()
            
            # Parse response
            proposed_text, rationale = self._parse_redline_response(
                llm_response,
                session_logger
            )
            
            session_logger.debug(f"Redline generated with template for clause {clause.id}")
            
            return proposed_text, rationale
            
        except Exception as e:
            session_logger.error(f"Failed to generate redline with template: {str(e)}")
            raise
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_without_template(
        self,
        clause: Clause,
        risk_assessment: RiskAssessment,
        session_logger
    ) -> tuple[str, str]:
        """Generate redline without a template (LLM-only).
        
        Args:
            clause: Clause object
            risk_assessment: RiskAssessment object
            session_logger: Logger with session context
            
        Returns:
            Tuple of (proposed_text, rationale)
        """
        session_logger.debug(f"Generating redline without template for clause {clause.id}")
        
        try:
            prompt = f"""Generate a redline suggestion for this contract clause.

ORIGINAL CLAUSE:
Type: {clause.type}
Text: {clause.text}

IDENTIFIED RISK:
Severity: {risk_assessment.severity}
Risk Type: {risk_assessment.risk_type}
Explanation: {risk_assessment.explanation}

INSTRUCTIONS:
1. Create alternative clause language that reduces the identified risk
2. Maintain the core business intent of the original clause
3. Use clear, professional legal language
4. Keep the redline similar in length to the original
5. Ensure the redline is realistic and negotiable

Provide your response in this format:
PROPOSED CLAUSE: [your redline text]
RATIONALE: [2-3 sentence explanation of why this is safer]"""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.instruction)]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part(text="I understand. I will generate contextually appropriate redline suggestions.")]
                    ),
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=600
                )
            )
            
            llm_response = response.text.strip()
            
            # Parse response
            proposed_text, rationale = self._parse_redline_response(
                llm_response,
                session_logger
            )
            
            session_logger.debug(f"Redline generated without template for clause {clause.id}")
            
            return proposed_text, rationale
            
        except Exception as e:
            session_logger.error(f"Failed to generate redline without template: {str(e)}")
            raise
    
    def _parse_redline_response(
        self,
        llm_response: str,
        session_logger
    ) -> tuple[str, str]:
        """Parse LLM response to extract proposed text and rationale.
        
        Args:
            llm_response: LLM response text
            session_logger: Logger with session context
            
        Returns:
            Tuple of (proposed_text, rationale)
        """
        import re
        
        # Parse proposed clause
        proposed_match = re.search(
            r'PROPOSED CLAUSE:\s*(.+?)(?=RATIONALE:|$)',
            llm_response,
            re.IGNORECASE | re.DOTALL
        )
        
        if proposed_match:
            proposed_text = proposed_match.group(1).strip()
        else:
            # Fallback: use first paragraph
            session_logger.warning("Could not parse PROPOSED CLAUSE, using fallback")
            proposed_text = llm_response.split('\n\n')[0].strip()
        
        # Parse rationale
        rationale_match = re.search(
            r'RATIONALE:\s*(.+?)$',
            llm_response,
            re.IGNORECASE | re.DOTALL
        )
        
        if rationale_match:
            rationale = rationale_match.group(1).strip()
        else:
            # Fallback: use last paragraph or generate default
            session_logger.warning("Could not parse RATIONALE, using fallback")
            paragraphs = llm_response.split('\n\n')
            if len(paragraphs) > 1:
                rationale = paragraphs[-1].strip()
            else:
                rationale = "This redline reduces risk by providing clearer terms and protections."
        
        # Clean up text
        proposed_text = proposed_text.replace('\n', ' ').strip()
        rationale = rationale.replace('\n', ' ').strip()
        
        # Limit lengths
        if len(proposed_text) > 1000:
            proposed_text = proposed_text[:997] + "..."
        if len(rationale) > 500:
            rationale = rationale[:497] + "..."
        
        return proposed_text, rationale
    
    def _generate_diff(self, original: str, proposed: str) -> str:
        """Generate unified diff format for changes.
        
        Args:
            original: Original clause text
            proposed: Proposed clause text
            
        Returns:
            Unified diff string
        """
        # Split into lines for better diff readability
        original_lines = original.split('. ')
        proposed_lines = proposed.split('. ')
        
        # Add periods back
        original_lines = [line + '.' if not line.endswith('.') else line 
                         for line in original_lines if line]
        proposed_lines = [line + '.' if not line.endswith('.') else line 
                         for line in proposed_lines if line]
        
        # Generate unified diff
        diff = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile='original',
            tofile='proposed',
            lineterm=''
        )
        
        diff_text = '\n'.join(diff)
        
        # If diff is empty or too complex, provide simple before/after
        if not diff_text or len(diff_text) > 2000:
            diff_text = f"--- ORIGINAL ---\n{original}\n\n+++ PROPOSED +++\n{proposed}"
        
        return diff_text
    
    def get_redlines_by_severity(
        self,
        redlines: List[RedlineProposal],
        risk_assessments: List[RiskAssessment],
        severity: str
    ) -> List[RedlineProposal]:
        """Filter redlines by risk severity.
        
        Args:
            redlines: List of RedlineProposal objects
            risk_assessments: List of RiskAssessment objects
            severity: Severity level to filter by
            
        Returns:
            List of redlines for the specified severity
        """
        risk_map = {r.clause_id: r for r in risk_assessments}
        
        return [
            redline for redline in redlines
            if risk_map.get(redline.clause_id) 
            and risk_map[redline.clause_id].severity == severity
        ]
