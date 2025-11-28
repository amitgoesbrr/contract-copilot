"""
Data Models - msgspec Structs for efficient serialization.

These models define the core data structures passed between agents
and stored in the Memory Bank. Using msgspec provides:
- Fast JSON serialization/deserialization
- Type validation at runtime
- Memory-efficient struct representation
"""

from datetime import datetime
from typing import List, Literal, Optional
from msgspec import Struct


class Clause(Struct):
    """Extracted contract clause with location metadata."""
    id: str
    type: str  # confidentiality, indemnification, termination, governing_law, liability, payment_terms
    text: str
    start_line: int
    end_line: int
    page_number: int


class RiskAssessment(Struct):
    """Risk evaluation for a clause with severity and explanation."""
    clause_id: str
    severity: Literal["low", "medium", "high"]
    risk_type: str
    explanation: str
    llm_rationale: Optional[str] = None


class RedlineProposal(Struct):
    """Proposed alternative clause language with unified diff."""
    clause_id: str
    original_text: str
    proposed_text: str
    rationale: str
    diff: str


class NegotiationSummary(Struct):
    """Stakeholder-ready negotiation materials."""
    checklist: List[str]
    draft_email: str
    executive_summary: str
    priority_issues: List[str]


class ContractMetadata(Struct):
    """Document metadata extracted during ingestion."""
    parties: List[str]
    date: Optional[str] = None
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None


class AgentTrace(Struct):
    """Execution trace for observability and audit."""
    agent_name: str
    timestamp: datetime
    input_hash: str
    output_hash: str
    latency_seconds: float
    success: bool
    error_message: Optional[str] = None


class AuditBundle(Struct):
    """Complete audit trail for compliance and traceability."""
    session_id: str
    timestamp: datetime
    original_contract: str
    extracted_clauses: List[Clause]
    risk_assessments: List[RiskAssessment]
    redline_proposals: List[RedlineProposal]
    negotiation_summary: NegotiationSummary
    agent_traces: List[AgentTrace]
    disclaimer: str


class ContractSession(Struct, kw_only=True):
    """Complete session state persisted in Memory Bank."""
    session_id: str
    user_id: str
    filename: str
    file_mime_type: Optional[str] = None
    contract_metadata: ContractMetadata
    normalized_text: str
    created_at: datetime
    updated_at: datetime
    extracted_clauses: List[Clause] = []
    risk_assessments: List[RiskAssessment] = []
    redline_proposals: List[RedlineProposal] = []
    negotiation_summary: Optional[NegotiationSummary] = None
    audit_bundle: Optional[AuditBundle] = None
