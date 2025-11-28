"""Memory Bank integration for agent state persistence.

This module provides a Memory Bank wrapper that integrates with DatabaseSessionService
to enable agents to read and write state during contract review workflows.
"""

from typing import Any, Optional, Dict, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from memory.session_service import DatabaseSessionService

from adk.models import (
    ContractSession,
    Clause,
    RiskAssessment,
    RedlineProposal,
    NegotiationSummary,
    AuditBundle
)
from adk.error_handling import SessionError
from loguru import logger
import msgspec


class MemoryBank:
    """Memory Bank for agent state persistence.
    
    Provides a high-level interface for agents to read and write state
    during contract review workflows. Integrates with DatabaseSessionService
    for persistent storage.
    """
    
    def __init__(self, session_service: "DatabaseSessionService"):
        """Initialize Memory Bank with a session service.
        
        Args:
            session_service: DatabaseSessionService instance
        """
        self.session_service = session_service
        logger.info("MemoryBank initialized")
    
    def store_clauses(self, session_id: str, clauses: List[Clause]) -> None:
        """Store extracted clauses in memory.
        
        Args:
            session_id: Session identifier
            clauses: List of extracted Clause objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            session.extracted_clauses = clauses
            self.session_service.update_session(session)
            
            # Also store in state table for quick access
            self.session_service.set_state(
                session_id,
                "extracted_clauses",
                [msgspec.to_builtins(c) for c in clauses]
            )
            
            logger.info(f"Stored {len(clauses)} clauses for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store clauses for session {session_id}: {e}")
            raise SessionError(f"Failed to store clauses: {e}")
    
    def get_clauses(self, session_id: str) -> List[Clause]:
        """Retrieve extracted clauses from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of Clause objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            # Ensure we have Clause objects, not dicts
            clauses = []
            for clause in session.extracted_clauses:
                if isinstance(clause, dict):
                    # Convert dict to Clause object
                    clauses.append(Clause(**clause))
                elif isinstance(clause, Clause):
                    clauses.append(clause)
                else:
                    logger.warning(f"Unexpected clause type: {type(clause)}")
                    continue
            
            logger.debug(f"Retrieved {len(clauses)} clauses for session {session_id}")
            return clauses
            
        except Exception as e:
            logger.error(f"Failed to get clauses for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve clauses: {e}")
    
    def store_risk_assessments(self, session_id: str, assessments: List[RiskAssessment]) -> None:
        """Store risk assessments in memory.
        
        Args:
            session_id: Session identifier
            assessments: List of RiskAssessment objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            session.risk_assessments = assessments
            self.session_service.update_session(session)
            
            # Also store in state table
            self.session_service.set_state(
                session_id,
                "risk_assessments",
                [msgspec.to_builtins(a) for a in assessments]
            )
            
            logger.info(f"Stored {len(assessments)} risk assessments for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store risk assessments for session {session_id}: {e}")
            raise SessionError(f"Failed to store risk assessments: {e}")
    
    def get_risk_assessments(self, session_id: str) -> List[RiskAssessment]:
        """Retrieve risk assessments from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of RiskAssessment objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved {len(session.risk_assessments)} risk assessments for session {session_id}")
            return session.risk_assessments
            
        except Exception as e:
            logger.error(f"Failed to get risk assessments for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve risk assessments: {e}")
    
    def store_redline_proposals(self, session_id: str, proposals: List[RedlineProposal]) -> None:
        """Store redline proposals in memory.
        
        Args:
            session_id: Session identifier
            proposals: List of RedlineProposal objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            session.redline_proposals = proposals
            self.session_service.update_session(session)
            
            # Also store in state table
            self.session_service.set_state(
                session_id,
                "redline_proposals",
                [msgspec.to_builtins(p) for p in proposals]
            )
            
            logger.info(f"Stored {len(proposals)} redline proposals for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store redline proposals for session {session_id}: {e}")
            raise SessionError(f"Failed to store redline proposals: {e}")
    
    def get_redline_proposals(self, session_id: str) -> List[RedlineProposal]:
        """Retrieve redline proposals from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of RedlineProposal objects
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved {len(session.redline_proposals)} redline proposals for session {session_id}")
            return session.redline_proposals
            
        except Exception as e:
            logger.error(f"Failed to get redline proposals for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve redline proposals: {e}")
    
    def store_negotiation_summary(self, session_id: str, summary: NegotiationSummary) -> None:
        """Store negotiation summary in memory.
        
        Args:
            session_id: Session identifier
            summary: NegotiationSummary object
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            session.negotiation_summary = summary
            self.session_service.update_session(session)
            
            # Also store in state table
            self.session_service.set_state(
                session_id,
                "negotiation_summary",
                msgspec.to_builtins(summary)
            )
            
            logger.info(f"Stored negotiation summary for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store negotiation summary for session {session_id}: {e}")
            raise SessionError(f"Failed to store negotiation summary: {e}")
    
    def get_negotiation_summary(self, session_id: str) -> Optional[NegotiationSummary]:
        """Retrieve negotiation summary from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            NegotiationSummary object or None
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved negotiation summary for session {session_id}")
            return session.negotiation_summary
            
        except Exception as e:
            logger.error(f"Failed to get negotiation summary for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve negotiation summary: {e}")
    
    def store_audit_bundle(self, session_id: str, bundle: AuditBundle) -> None:
        """Store audit bundle in memory.
        
        Args:
            session_id: Session identifier
            bundle: AuditBundle object
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            session.audit_bundle = bundle
            self.session_service.update_session(session)
            
            # Also store in state table
            self.session_service.set_state(
                session_id,
                "audit_bundle",
                msgspec.to_builtins(bundle)
            )
            
            logger.info(f"Stored audit bundle for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store audit bundle for session {session_id}: {e}")
            raise SessionError(f"Failed to store audit bundle: {e}")
    
    def get_audit_bundle(self, session_id: str) -> Optional[AuditBundle]:
        """Retrieve audit bundle from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AuditBundle object or None
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved audit bundle for session {session_id}")
            return session.audit_bundle
            
        except Exception as e:
            logger.error(f"Failed to get audit bundle for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve audit bundle: {e}")
    
    def get_normalized_text(self, session_id: str) -> str:
        """Retrieve normalized contract text from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Normalized contract text
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved normalized text for session {session_id}")
            return session.normalized_text
            
        except Exception as e:
            logger.error(f"Failed to get normalized text for session {session_id}: {e}")
            raise SessionError(f"Failed to retrieve normalized text: {e}")
    
    def get_session_state(self, session_id: str) -> ContractSession:
        """Retrieve complete session state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ContractSession object
        """
        try:
            session = self.session_service.get_session(session_id)
            if not session:
                raise SessionError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved complete session state for {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session state for {session_id}: {e}")
            raise SessionError(f"Failed to retrieve session state: {e}")
    
    def set_custom_state(self, session_id: str, key: str, value: Any) -> None:
        """Store custom key-value state.
        
        Args:
            session_id: Session identifier
            key: State key
            value: State value
        """
        self.session_service.set_state(session_id, key, value)
    
    def get_custom_state(self, session_id: str, key: str) -> Optional[Any]:
        """Retrieve custom key-value state.
        
        Args:
            session_id: Session identifier
            key: State key
            
        Returns:
            State value or None
        """
        return self.session_service.get_state(session_id, key)
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all data for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was cleared
        """
        try:
            deleted = self.session_service.delete_session(session_id)
            if deleted:
                logger.info(f"Cleared session {session_id}")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
            raise SessionError(f"Failed to clear session: {e}")
