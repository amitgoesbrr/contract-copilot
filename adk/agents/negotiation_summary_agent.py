"""Negotiation Summary Agent for creating stakeholder-friendly negotiation materials.

This agent generates prioritized negotiation checklists, draft emails, and executive
summaries that translate technical risk assessments and redlines into business-friendly
language suitable for non-legal stakeholders.
"""

import os
from typing import Dict, List, Optional
from loguru import logger

from google import genai
from google.genai import types

from adk.models import Clause, RiskAssessment, RedlineProposal, NegotiationSummary
from adk.error_handling import (
    NegotiationSummaryError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger


class NegotiationSummaryAgent:
    """Agent responsible for generating negotiation-ready materials.
    
    This agent:
    1. Analyzes risk assessments and redline proposals
    2. Creates a prioritized negotiation checklist
    3. Generates a draft negotiation email in stakeholder-friendly language
    4. Produces an executive summary of key concerns
    5. Translates legal/technical language into business terms
    6. Ensures materials are suitable for non-legal stakeholders
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite"
    ):
        """Initialize the Negotiation Summary Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for summary generation
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise NegotiationSummaryError("No API key provided for Negotiation Summary Agent")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Agent instruction for negotiation summary generation
        self.instruction = self._build_instruction()
        
        logger.info(
            "Negotiation Summary Agent initialized",
            model=model_name
        )
    
    def _build_instruction(self) -> str:
        """Build the system instruction for negotiation summary generation.
        
        Returns:
            System instruction string
        """
        return """You are a business negotiation advisor specializing in contract negotiations.

Your task is to translate technical legal analysis into clear, actionable negotiation materials
that business stakeholders can understand and use effectively.

GUIDELINES FOR NEGOTIATION CHECKLIST:
1. Prioritize items by business impact (high-risk items first)
2. Use clear, concise bullet points
3. Focus on actionable negotiation points
4. Avoid legal jargon - use business language
5. Group related items together logically
6. Limit to 5-8 key items (most important issues only)

GUIDELINES FOR DRAFT EMAIL:
1. Use professional but friendly tone
2. Start with context and purpose
3. Present concerns as collaborative discussion points
4. Avoid accusatory or confrontational language
5. Suggest specific alternatives where possible
6. End with clear next steps
7. Keep email concise (200-300 words)
8. Use business-friendly language, not legal terminology

GUIDELINES FOR EXECUTIVE SUMMARY:
1. Start with overall assessment (e.g., "3 high-priority concerns identified")
2. Summarize key risks in plain language
3. Highlight business impact (financial, operational, reputational)
4. Keep to 3-4 paragraphs maximum
5. Focus on "what" and "why it matters" not legal technicalities
6. End with recommended approach

TONE AND LANGUAGE:
- Professional but accessible
- Solution-oriented, not problem-focused
- Collaborative, not adversarial
- Business-focused, not legal-focused
- Clear and direct, not verbose

IMPORTANT:
- Never use legal jargon without explanation
- Focus on business impact and practical solutions
- Make materials suitable for executives and business stakeholders
- Ensure all content is actionable and clear"""
    
    @log_agent_execution("NegotiationSummaryAgent")
    @handle_errors(NegotiationSummaryError)
    def generate_summary(
        self,
        clauses: List[Clause],
        risk_assessments: List[RiskAssessment],
        redline_proposals: List[RedlineProposal],
        session_id: str = "default",
        contract_metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """Generate negotiation summary materials.
        
        Args:
            clauses: List of Clause objects
            risk_assessments: List of RiskAssessment objects
            redline_proposals: List of RedlineProposal objects
            session_id: Session identifier for logging
            contract_metadata: Optional contract metadata (parties, type, etc.)
            
        Returns:
            Dictionary containing:
                - negotiation_summary: NegotiationSummary object
                - summary_stats: Statistics about the summary
                
        Raises:
            NegotiationSummaryError: If summary generation fails
        """
        session_logger = get_session_logger(session_id, "NegotiationSummaryAgent")
        
        if not risk_assessments:
            raise NegotiationSummaryError("No risk assessments provided for summary generation")
        
        session_logger.info(
            "Starting negotiation summary generation",
            total_clauses=len(clauses),
            total_risks=len(risk_assessments),
            total_redlines=len(redline_proposals)
        )
        
        # Categorize risks by severity
        high_risks = [r for r in risk_assessments if r.severity == "high"]
        medium_risks = [r for r in risk_assessments if r.severity == "medium"]
        low_risks = [r for r in risk_assessments if r.severity == "low"]
        
        session_logger.info(
            "Risk breakdown",
            high_risk_count=len(high_risks),
            medium_risk_count=len(medium_risks),
            low_risk_count=len(low_risks)
        )
        
        # Generate negotiation summary using LLM
        negotiation_summary = self._generate_negotiation_materials(
            clauses,
            risk_assessments,
            redline_proposals,
            high_risks,
            medium_risks,
            contract_metadata,
            session_logger
        )
        
        summary_stats = {
            "total_risks": len(risk_assessments),
            "high_risk_count": len(high_risks),
            "medium_risk_count": len(medium_risks),
            "low_risk_count": len(low_risks),
            "total_redlines": len(redline_proposals),
            "checklist_items": len(negotiation_summary.checklist),
            "priority_issues": len(negotiation_summary.priority_issues)
        }
        
        session_logger.info(
            "Negotiation summary generation complete",
            checklist_items=len(negotiation_summary.checklist),
            priority_issues=len(negotiation_summary.priority_issues)
        )
        
        return {
            "negotiation_summary": negotiation_summary,
            "summary_stats": summary_stats
        }
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_negotiation_materials(
        self,
        clauses: List[Clause],
        risk_assessments: List[RiskAssessment],
        redline_proposals: List[RedlineProposal],
        high_risks: List[RiskAssessment],
        medium_risks: List[RiskAssessment],
        contract_metadata: Optional[Dict],
        session_logger
    ) -> NegotiationSummary:
        """Generate all negotiation materials using LLM.
        
        Args:
            clauses: List of Clause objects
            risk_assessments: List of RiskAssessment objects
            redline_proposals: List of RedlineProposal objects
            high_risks: List of high-severity risk assessments
            medium_risks: List of medium-severity risk assessments
            contract_metadata: Optional contract metadata
            session_logger: Logger with session context
            
        Returns:
            NegotiationSummary object
        """
        session_logger.debug("Generating negotiation materials with LLM")
        
        # Build context about the contract
        context = self._build_contract_context(
            clauses,
            risk_assessments,
            redline_proposals,
            high_risks,
            medium_risks,
            contract_metadata
        )
        
        try:
            # Generate checklist
            checklist = self._generate_checklist(context, session_logger)
            
            # Generate draft email
            draft_email = self._generate_draft_email(context, session_logger)
            
            # Generate executive summary
            executive_summary = self._generate_executive_summary(context, session_logger)
            
            # Extract priority issues from high and medium risks
            priority_issues = self._extract_priority_issues(
                high_risks,
                medium_risks,
                session_logger
            )
            
            return NegotiationSummary(
                checklist=checklist,
                draft_email=draft_email,
                executive_summary=executive_summary,
                priority_issues=priority_issues
            )
            
        except Exception as e:
            session_logger.error(f"Failed to generate negotiation materials: {str(e)}")
            raise
    
    def _build_contract_context(
        self,
        clauses: List[Clause],
        risk_assessments: List[RiskAssessment],
        redline_proposals: List[RedlineProposal],
        high_risks: List[RiskAssessment],
        medium_risks: List[RiskAssessment],
        contract_metadata: Optional[Dict]
    ) -> str:
        """Build context string about the contract for LLM.
        
        Args:
            clauses: List of Clause objects
            risk_assessments: List of RiskAssessment objects
            redline_proposals: List of RedlineProposal objects
            high_risks: List of high-severity risks
            medium_risks: List of medium-severity risks
            contract_metadata: Optional contract metadata
            
        Returns:
            Context string
        """
        # Create lookup maps
        clause_map = {c.id: c for c in clauses}
        redline_map = {r.clause_id: r for r in redline_proposals}
        
        context_parts = []
        
        # Add contract metadata if available
        if contract_metadata:
            context_parts.append("CONTRACT INFORMATION:")
            if hasattr(contract_metadata, 'contract_type') and contract_metadata.contract_type:
                context_parts.append(f"Type: {contract_metadata.contract_type}")
            if hasattr(contract_metadata, 'parties') and contract_metadata.parties:
                context_parts.append(f"Parties: {', '.join(contract_metadata.parties)}")
            context_parts.append("")
        
        # Add high-risk issues
        if high_risks:
            context_parts.append("HIGH-RISK ISSUES:")
            for i, risk in enumerate(high_risks[:5], 1):  # Limit to top 5
                clause = clause_map.get(risk.clause_id)
                redline = redline_map.get(risk.clause_id)
                
                context_parts.append(f"\n{i}. {risk.risk_type}")
                context_parts.append(f"   Explanation: {risk.explanation}")
                if clause:
                    context_parts.append(f"   Clause Type: {clause.type}")
                    context_parts.append(f"   Original Text: {clause.text[:200]}...")
                if redline:
                    context_parts.append(f"   Proposed Change: {redline.rationale}")
            context_parts.append("")
        
        # Add medium-risk issues
        if medium_risks:
            context_parts.append("MEDIUM-RISK ISSUES:")
            for i, risk in enumerate(medium_risks[:3], 1):  # Limit to top 3
                clause = clause_map.get(risk.clause_id)
                redline = redline_map.get(risk.clause_id)
                
                context_parts.append(f"\n{i}. {risk.risk_type}")
                context_parts.append(f"   Explanation: {risk.explanation}")
                if redline:
                    context_parts.append(f"   Proposed Change: {redline.rationale}")
            context_parts.append("")
        
        # Add summary statistics
        context_parts.append("SUMMARY STATISTICS:")
        context_parts.append(f"Total Clauses Analyzed: {len(clauses)}")
        context_parts.append(f"High-Risk Issues: {len(high_risks)}")
        context_parts.append(f"Medium-Risk Issues: {len(medium_risks)}")
        context_parts.append(f"Redline Proposals: {len(redline_proposals)}")
        
        return "\n".join(context_parts)
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_checklist(
        self,
        context: str,
        session_logger
    ) -> List[str]:
        """Generate prioritized negotiation checklist.
        
        Args:
            context: Contract context string
            session_logger: Logger with session context
            
        Returns:
            List of checklist items
        """
        session_logger.debug("Generating negotiation checklist")
        
        prompt = f"""Based on the contract analysis below, create a prioritized negotiation checklist.

{context}

Create a checklist of 5-8 key negotiation points, prioritized by business impact.
Each item should be:
- Clear and actionable
- Written in business language (not legal jargon)
- Focused on what needs to be negotiated
- Concise (one sentence per item)

Format each item as a standalone bullet point that starts with an action verb.
Order items from highest to lowest priority.

Provide ONLY the checklist items, one per line, without numbering or bullet symbols."""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=self.instruction)]
                ),
                types.Content(
                    role="model",
                    parts=[types.Part(text="I understand. I will create clear, business-focused negotiation materials.")]
                ),
                types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=500
            )
        )
        
        checklist_text = response.text.strip()
        
        # Parse into list
        checklist = [
            line.strip().lstrip('-•*').strip()
            for line in checklist_text.split('\n')
            if line.strip() and not line.strip().startswith('#')
        ]
        
        # Limit to 8 items
        checklist = checklist[:8]
        
        session_logger.debug(f"Generated checklist with {len(checklist)} items")
        
        return checklist
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_draft_email(
        self,
        context: str,
        session_logger
    ) -> str:
        """Generate draft negotiation email.
        
        Args:
            context: Contract context string
            session_logger: Logger with session context
            
        Returns:
            Draft email text
        """
        session_logger.debug("Generating draft negotiation email")
        
        prompt = f"""Based on the contract analysis below, write a draft negotiation email.

{context}

Write a professional email to the counterparty that:
- Opens with context and purpose
- Presents concerns as collaborative discussion points
- Avoids accusatory or confrontational language
- Suggests specific alternatives where possible
- Ends with clear next steps
- Is concise (200-300 words)
- Uses business-friendly language

The email should feel collaborative and solution-oriented, not adversarial.

Provide ONLY the email body text (no subject line, no signature block)."""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=self.instruction)]
                ),
                types.Content(
                    role="model",
                    parts=[types.Part(text="I understand. I will create clear, business-focused negotiation materials.")]
                ),
                types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.6,
                max_output_tokens=600
            )
        )
        
        draft_email = response.text.strip()
        
        session_logger.debug("Generated draft negotiation email")
        
        return draft_email
    
    @retry_with_backoff(config=GEMINI_RETRY_CONFIG, exceptions=(Exception,))
    def _generate_executive_summary(
        self,
        context: str,
        session_logger
    ) -> str:
        """Generate executive summary of key concerns.
        
        Args:
            context: Contract context string
            session_logger: Logger with session context
            
        Returns:
            Executive summary text
        """
        session_logger.debug("Generating executive summary")
        
        prompt = f"""Based on the contract analysis below, write an executive summary.

{context}

Write an executive summary that:
- Starts with overall assessment (e.g., "3 high-priority concerns identified")
- Summarizes key risks in plain language
- Highlights business impact (financial, operational, reputational)
- Is 3-4 paragraphs maximum
- Focuses on "what" and "why it matters" not legal technicalities
- Ends with recommended approach

The summary should be suitable for executives and business stakeholders who need
to understand the key issues quickly without legal background.

Provide ONLY the executive summary text."""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=self.instruction)]
                ),
                types.Content(
                    role="model",
                    parts=[types.Part(text="I understand. I will create clear, business-focused negotiation materials.")]
                ),
                types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=700
            )
        )
        
        executive_summary = response.text.strip()
        
        session_logger.debug("Generated executive summary")
        
        return executive_summary
    
    def _extract_priority_issues(
        self,
        high_risks: List[RiskAssessment],
        medium_risks: List[RiskAssessment],
        session_logger
    ) -> List[str]:
        """Extract priority issues from risk assessments.
        
        Args:
            high_risks: List of high-severity risks
            medium_risks: List of medium-severity risks
            session_logger: Logger with session context
            
        Returns:
            List of priority issue descriptions
        """
        priority_issues = []
        
        # Add all high-risk issues
        for risk in high_risks:
            issue = f"{risk.risk_type}: {risk.explanation}"
            priority_issues.append(issue)
        
        # Add top medium-risk issues (limit to 3)
        for risk in medium_risks[:3]:
            issue = f"{risk.risk_type}: {risk.explanation}"
            priority_issues.append(issue)
        
        session_logger.debug(f"Extracted {len(priority_issues)} priority issues")
        
        return priority_issues
