"""Compliance and Audit Agent for generating complete audit trails.

This agent compiles all outputs from the contract review pipeline into a comprehensive
audit bundle that includes timestamps, agent traces, LLM interactions, and disclaimers
for compliance and reproducibility purposes.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from google import genai
from google.genai import types
import msgspec

from adk.models import (
    Clause,
    RiskAssessment,
    RedlineProposal,
    NegotiationSummary,
    AuditBundle,
    AgentTrace,
    ContractMetadata
)
from adk.error_handling import (
    ComplianceAuditError,
    handle_errors,
    retry_with_backoff,
    GEMINI_RETRY_CONFIG
)
from adk.logging_config import log_agent_execution, get_session_logger


class ComplianceAuditAgent:
    """Agent responsible for generating compliance and audit documentation.
    
    This agent:
    1. Compiles all agent outputs into a comprehensive audit bundle
    2. Tracks timestamps for each operation
    3. Records LLM prompt/response pairs for reproducibility
    4. Generates appropriate disclaimer text
    5. Exports audit bundle in both JSON and Markdown formats
    6. Ensures 100% traceability of all agent decisions
    """
    
    # Standard disclaimer text
    DISCLAIMER = """IMPORTANT LEGAL DISCLAIMER:

This AI Contract Reviewer & Negotiation Copilot is an automated analysis tool and is NOT a substitute 
for legal advice. It is intended for preliminary analysis and informational purposes only.

Key Limitations:
- This tool does not provide legal advice or create an attorney-client relationship
- AI-generated analysis may contain errors, omissions, or inaccuracies
- Contract interpretation requires human legal expertise and contextual understanding
- Risk assessments are based on pattern matching and may not capture all nuances
- Redline suggestions should be reviewed by qualified legal counsel before use
- This tool should not be relied upon as the sole basis for legal decisions

Recommendations:
- Always have contracts reviewed by qualified legal professionals
- Verify all AI-generated analysis with human legal expertise
- Consider jurisdiction-specific requirements and regulations
- Consult with legal counsel before acting on any recommendations
- Use this tool as a preliminary screening aid, not a final authority

By using this tool, you acknowledge that you understand these limitations and will seek 
appropriate legal counsel for all contract-related decisions.

Generated: {timestamp}
Session ID: {session_id}"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite"
    ):
        """Initialize the Compliance and Audit Agent.
        
        Args:
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for audit compilation
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        
        if not self.api_key:
            raise ComplianceAuditError("No API key provided for Compliance Audit Agent")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        logger.info(
            "Compliance Audit Agent initialized",
            model=model_name
        )
    
    @log_agent_execution("ComplianceAuditAgent")
    @handle_errors(ComplianceAuditError)
    def compile_audit_bundle(
        self,
        session_id: str,
        original_contract: str,
        extracted_clauses: List[Clause],
        risk_assessments: List[RiskAssessment],
        redline_proposals: List[RedlineProposal],
        negotiation_summary: NegotiationSummary,
        agent_traces: List[AgentTrace],
        contract_metadata: Optional[ContractMetadata] = None
    ) -> Dict[str, any]:
        """Compile complete audit bundle with all agent outputs.
        
        Args:
            session_id: Session identifier
            original_contract: Original contract text
            extracted_clauses: List of Clause objects
            risk_assessments: List of RiskAssessment objects
            redline_proposals: List of RedlineProposal objects
            negotiation_summary: NegotiationSummary object
            agent_traces: List of AgentTrace objects tracking agent executions
            contract_metadata: Optional contract metadata
            
        Returns:
            Dictionary containing:
                - audit_bundle: AuditBundle object
                - json_export: JSON string representation
                - markdown_export: Markdown string representation
                
        Raises:
            ComplianceAuditError: If audit compilation fails
        """
        session_logger = get_session_logger(session_id, "ComplianceAuditAgent")
        
        session_logger.info(
            "Starting audit bundle compilation",
            total_clauses=len(extracted_clauses),
            total_risks=len(risk_assessments),
            total_redlines=len(redline_proposals),
            total_traces=len(agent_traces)
        )
        
        # Generate timestamp
        timestamp = datetime.now()
        
        # Generate disclaimer with session info
        disclaimer = self.DISCLAIMER.format(
            timestamp=timestamp.isoformat(),
            session_id=session_id
        )
        
        # Create audit bundle
        audit_bundle = AuditBundle(
            session_id=session_id,
            timestamp=timestamp,
            original_contract=original_contract,
            extracted_clauses=extracted_clauses,
            risk_assessments=risk_assessments,
            redline_proposals=redline_proposals,
            negotiation_summary=negotiation_summary,
            agent_traces=agent_traces,
            disclaimer=disclaimer
        )
        
        session_logger.info("Audit bundle compiled successfully")
        
        # Export to JSON
        json_export = self._export_to_json(audit_bundle, session_logger)
        
        # Export to Markdown
        markdown_export = self._export_to_markdown(
            audit_bundle,
            contract_metadata,
            session_logger
        )
        
        session_logger.info(
            "Audit bundle exports generated",
            json_size=len(json_export),
            markdown_size=len(markdown_export)
        )
        
        return {
            "audit_bundle": audit_bundle,
            "json_export": json_export,
            "markdown_export": markdown_export
        }
    
    def _export_to_json(
        self,
        audit_bundle: AuditBundle,
        session_logger
    ) -> str:
        """Export audit bundle to JSON format.
        
        Args:
            audit_bundle: AuditBundle object
            session_logger: Logger with session context
            
        Returns:
            JSON string representation
        """
        session_logger.debug("Exporting audit bundle to JSON")
        
        try:
            # Use msgspec encoder for efficient serialization
            encoder = msgspec.json.Encoder()
            json_bytes = encoder.encode(audit_bundle)
            json_str = json_bytes.decode('utf-8')
            
            # Pretty print for readability
            json_obj = json.loads(json_str)
            json_export = json.dumps(json_obj, indent=2, default=str)
            
            session_logger.debug(f"JSON export size: {len(json_export)} bytes")
            
            return json_export
            
        except Exception as e:
            session_logger.error(f"Failed to export to JSON: {str(e)}")
            raise ComplianceAuditError(f"JSON export failed: {str(e)}")
    
    def _export_to_markdown(
        self,
        audit_bundle: AuditBundle,
        contract_metadata: Optional[ContractMetadata],
        session_logger
    ) -> str:
        """Export audit bundle to Markdown format.
        
        Args:
            audit_bundle: AuditBundle object
            contract_metadata: Optional contract metadata
            session_logger: Logger with session context
            
        Returns:
            Markdown string representation
        """
        session_logger.debug("Exporting audit bundle to Markdown")
        
        try:
            md_parts = []
            
            # Header
            md_parts.append("# Contract Review Audit Report")
            md_parts.append("")
            md_parts.append(f"**Session ID:** {audit_bundle.session_id}")
            md_parts.append(f"**Generated:** {audit_bundle.timestamp.isoformat()}")
            md_parts.append("")
            
            # Contract metadata
            if contract_metadata:
                md_parts.append("## Contract Information")
                md_parts.append("")
                if contract_metadata.contract_type:
                    md_parts.append(f"**Type:** {contract_metadata.contract_type}")
                if contract_metadata.parties:
                    md_parts.append(f"**Parties:** {', '.join(contract_metadata.parties)}")
                if contract_metadata.date:
                    md_parts.append(f"**Date:** {contract_metadata.date}")
                if contract_metadata.jurisdiction:
                    md_parts.append(f"**Jurisdiction:** {contract_metadata.jurisdiction}")
                md_parts.append("")
            
            # Executive summary
            if audit_bundle.negotiation_summary and hasattr(audit_bundle.negotiation_summary, 'executive_summary'):
                md_parts.append("## Executive Summary")
                md_parts.append("")
                md_parts.append(audit_bundle.negotiation_summary.executive_summary)
                md_parts.append("")
            
            # Statistics
            md_parts.append("## Analysis Statistics")
            md_parts.append("")
            md_parts.append(f"- **Total Clauses Extracted:** {len(audit_bundle.extracted_clauses)}")
            md_parts.append(f"- **Risk Assessments:** {len(audit_bundle.risk_assessments)}")
            
            high_risks = [r for r in audit_bundle.risk_assessments if r.severity == "high"]
            medium_risks = [r for r in audit_bundle.risk_assessments if r.severity == "medium"]
            low_risks = [r for r in audit_bundle.risk_assessments if r.severity == "low"]
            
            md_parts.append(f"  - High Risk: {len(high_risks)}")
            md_parts.append(f"  - Medium Risk: {len(medium_risks)}")
            md_parts.append(f"  - Low Risk: {len(low_risks)}")
            md_parts.append(f"- **Redline Proposals:** {len(audit_bundle.redline_proposals)}")
            md_parts.append(f"- **Agent Executions:** {len(audit_bundle.agent_traces)}")
            md_parts.append("")
            
            # Negotiation checklist
            if audit_bundle.negotiation_summary and hasattr(audit_bundle.negotiation_summary, 'checklist'):
                md_parts.append("## Negotiation Checklist")
                md_parts.append("")
                for i, item in enumerate(audit_bundle.negotiation_summary.checklist, 1):
                    md_parts.append(f"{i}. {item}")
                md_parts.append("")
            
            # Priority issues
            if audit_bundle.negotiation_summary and hasattr(audit_bundle.negotiation_summary, 'priority_issues') and audit_bundle.negotiation_summary.priority_issues:
                md_parts.append("## Priority Issues")
                md_parts.append("")
                for i, issue in enumerate(audit_bundle.negotiation_summary.priority_issues, 1):
                    md_parts.append(f"### Issue {i}")
                    md_parts.append("")
                    md_parts.append(issue)
                    md_parts.append("")
            
            # Extracted clauses
            md_parts.append("## Extracted Clauses")
            md_parts.append("")
            for clause in audit_bundle.extracted_clauses:
                md_parts.append(f"### Clause {clause.id}")
                md_parts.append("")
                md_parts.append(f"**Type:** {clause.type}")
                md_parts.append(f"**Location:** Page {clause.page_number}, Lines {clause.start_line}-{clause.end_line}")
                md_parts.append("")
                md_parts.append("**Text:**")
                md_parts.append("```")
                md_parts.append(clause.text)
                md_parts.append("```")
                md_parts.append("")
            
            # Risk assessments
            md_parts.append("## Risk Assessments")
            md_parts.append("")
            
            # Group by severity
            for severity in ["high", "medium", "low"]:
                severity_risks = [r for r in audit_bundle.risk_assessments if r.severity == severity]
                if severity_risks:
                    md_parts.append(f"### {severity.upper()} Risk Issues")
                    md_parts.append("")
                    for risk in severity_risks:
                        md_parts.append(f"#### {risk.risk_type}")
                        md_parts.append("")
                        md_parts.append(f"**Clause ID:** {risk.clause_id}")
                        md_parts.append(f"**Severity:** {risk.severity}")
                        md_parts.append(f"**Explanation:** {risk.explanation}")
                        if risk.llm_rationale:
                            md_parts.append(f"**LLM Analysis:** {risk.llm_rationale}")
                        md_parts.append("")
            
            # Redline proposals
            if audit_bundle.redline_proposals:
                md_parts.append("## Redline Proposals")
                md_parts.append("")
                for i, redline in enumerate(audit_bundle.redline_proposals, 1):
                    md_parts.append(f"### Proposal {i}")
                    md_parts.append("")
                    md_parts.append(f"**Clause ID:** {redline.clause_id}")
                    md_parts.append(f"**Rationale:** {redline.rationale}")
                    md_parts.append("")
                    md_parts.append("**Original Text:**")
                    md_parts.append("```")
                    md_parts.append(redline.original_text)
                    md_parts.append("```")
                    md_parts.append("")
                    md_parts.append("**Proposed Text:**")
                    md_parts.append("```")
                    md_parts.append(redline.proposed_text)
                    md_parts.append("```")
                    md_parts.append("")
                    md_parts.append("**Diff:**")
                    md_parts.append("```diff")
                    md_parts.append(redline.diff)
                    md_parts.append("```")
                    md_parts.append("")
            
            # Draft negotiation email
            if audit_bundle.negotiation_summary and hasattr(audit_bundle.negotiation_summary, 'draft_email'):
                md_parts.append("## Draft Negotiation Email")
                md_parts.append("")
                md_parts.append(audit_bundle.negotiation_summary.draft_email)
                md_parts.append("")
            
            # Agent execution traces
            md_parts.append("## Agent Execution Traces")
            md_parts.append("")
            md_parts.append("| Agent | Timestamp | Latency (s) | Success | Input Hash | Output Hash |")
            md_parts.append("|-------|-----------|-------------|---------|------------|-------------|")
            
            for trace in audit_bundle.agent_traces:
                success_icon = "✓" if trace.success else "✗"
                error_msg = f" ({trace.error_message})" if trace.error_message else ""
                md_parts.append(
                    f"| {trace.agent_name} | {trace.timestamp.strftime('%H:%M:%S')} | "
                    f"{trace.latency_seconds:.2f} | {success_icon}{error_msg} | "
                    f"{trace.input_hash[:8]}... | {trace.output_hash[:8]}... |"
                )
            md_parts.append("")
            
            # Disclaimer
            md_parts.append("## Legal Disclaimer")
            md_parts.append("")
            md_parts.append(audit_bundle.disclaimer)
            md_parts.append("")
            
            markdown_export = "\n".join(md_parts)
            
            session_logger.debug(f"Markdown export size: {len(markdown_export)} bytes")
            
            return markdown_export
            
        except Exception as e:
            session_logger.error(f"Failed to export to Markdown: {str(e)}")
            raise ComplianceAuditError(f"Markdown export failed: {str(e)}")
    
    def save_audit_bundle(
        self,
        audit_bundle: AuditBundle,
        json_export: str,
        markdown_export: str,
        output_dir: str = "audit_bundles",
        session_logger=None
    ) -> Dict[str, str]:
        """Save audit bundle to files.
        
        Args:
            audit_bundle: AuditBundle object
            json_export: JSON string representation
            markdown_export: Markdown string representation
            output_dir: Directory to save files
            session_logger: Optional logger with session context
            
        Returns:
            Dictionary with file paths:
                - json_path: Path to JSON file
                - markdown_path: Path to Markdown file
        """
        if session_logger is None:
            session_logger = logger
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filenames with session ID and timestamp
            timestamp_str = audit_bundle.timestamp.strftime("%Y%m%d_%H%M%S")
            base_filename = f"audit_{audit_bundle.session_id}_{timestamp_str}"
            
            json_path = os.path.join(output_dir, f"{base_filename}.json")
            markdown_path = os.path.join(output_dir, f"{base_filename}.md")
            
            # Save JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(json_export)
            
            # Save Markdown
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_export)
            
            session_logger.info(
                "Audit bundle saved to files",
                json_path=json_path,
                markdown_path=markdown_path
            )
            
            return {
                "json_path": json_path,
                "markdown_path": markdown_path
            }
            
        except Exception as e:
            session_logger.error(f"Failed to save audit bundle: {str(e)}")
            raise ComplianceAuditError(f"Failed to save audit bundle: {str(e)}")
    
    @staticmethod
    def create_agent_trace(
        agent_name: str,
        input_data: any,
        output_data: any,
        latency_seconds: float,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AgentTrace:
        """Create an agent trace record.
        
        Args:
            agent_name: Name of the agent
            input_data: Input data to the agent
            output_data: Output data from the agent
            latency_seconds: Execution time in seconds
            success: Whether execution was successful
            error_message: Optional error message if failed
            
        Returns:
            AgentTrace object
        """
        # Create hashes of input and output for traceability
        input_hash = hashlib.sha256(
            str(input_data).encode('utf-8')
        ).hexdigest()
        
        output_hash = hashlib.sha256(
            str(output_data).encode('utf-8')
        ).hexdigest()
        
        return AgentTrace(
            agent_name=agent_name,
            timestamp=datetime.now(),
            input_hash=input_hash,
            output_hash=output_hash,
            latency_seconds=latency_seconds,
            success=success,
            error_message=error_message
        )
