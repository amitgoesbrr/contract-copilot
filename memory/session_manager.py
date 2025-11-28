"""Session manager for orchestrating session lifecycle.

This module provides high-level session management functions for creating,
managing, and cleaning up contract review sessions.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Tuple

from memory.session_service import DatabaseSessionService
from memory.memory_bank import MemoryBank
from adk.models import ContractMetadata, ContractSession
from adk.error_handling import SessionError
from loguru import logger


class SessionManager:
    """High-level session manager for contract review workflows.
    
    Provides convenience methods for session lifecycle management including
    initialization, persistence configuration, and cleanup.
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        cleanup_hours: int = 24,
        enable_persistence: bool = False
    ):
        """Initialize the session manager.
        
        Args:
            db_path: Path to SQLite database (defaults to env var or contract_copilot.db)
            cleanup_hours: Hours after which inactive sessions are cleaned up
            enable_persistence: Whether to enable persistent storage (from env var)
        """
        # Get configuration from environment or use defaults
        if db_path is None:
            db_path = os.getenv("DATABASE_URL", "sqlite:///./contract_copilot.db")
            # Extract file path from SQLite URL
            if db_path.startswith("sqlite:///"):
                db_path = db_path.replace("sqlite:///", "")
        
        self.enable_persistence = enable_persistence or os.getenv("SESSION_PERSISTENCE", "false").lower() == "true"
        
        if cleanup_hours is None:
            cleanup_hours = int(os.getenv("SESSION_CLEANUP_HOURS", "24"))
        
        self.session_service = DatabaseSessionService(
            db_path=db_path,
            cleanup_hours=cleanup_hours
        )
        self.memory_bank = MemoryBank(self.session_service)
        
        logger.info(
            f"SessionManager initialized (persistence={self.enable_persistence}, "
            f"cleanup_hours={cleanup_hours})"
        )
    
    def create_new_session(
        self,
        user_id: str,
        contract_metadata: ContractMetadata,
        normalized_text: str,
        filename: str = "Unknown Contract",
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Tuple[str, ContractSession]:
        """Create a new contract review session.
        
        Args:
            user_id: User identifier
            contract_metadata: Extracted contract metadata
            normalized_text: Normalized contract text
            filename: Name of the contract file
            file_bytes: Original file content
            mime_type: MIME type of the file
            session_id: Optional custom session ID (generates UUID if not provided)
            
        Returns:
            Tuple of (session_id, ContractSession)
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session = self.session_service.create_session(
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            contract_metadata=contract_metadata,
            normalized_text=normalized_text,
            file_bytes=file_bytes,
            mime_type=mime_type
        )
        
        logger.info(f"New session created: {session_id} for user: {user_id}, file: {filename}")
        return session_id, session
    
    def get_memory_bank(self) -> MemoryBank:
        """Get the Memory Bank instance for agent state management.
        
        Returns:
            MemoryBank instance
        """
        return self.memory_bank
    
    def get_session_service(self) -> DatabaseSessionService:
        """Get the DatabaseSessionService instance.
        
        Returns:
            DatabaseSessionService instance
        """
        return self.session_service
    
    def cleanup_session(self, session_id: str) -> bool:
        """Clean up a session based on persistence configuration.
        
        If persistence is disabled, the session is deleted immediately.
        If persistence is enabled, the session is kept for the configured cleanup period.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if kept for persistence
        """
        if not self.enable_persistence:
            # Delete immediately if persistence is disabled
            deleted = self.session_service.delete_session(session_id)
            if deleted:
                logger.info(f"Session {session_id} deleted (persistence disabled)")
            return deleted
        else:
            # Keep session for configured cleanup period
            logger.info(f"Session {session_id} kept for persistence (cleanup in {self.session_service.cleanup_hours}h)")
            return False
    
    def run_cleanup(self) -> int:
        """Run cleanup of old sessions based on configured policy.
        
        Returns:
            Number of sessions cleaned up
        """
        count = self.session_service.cleanup_old_sessions()
        logger.info(f"Cleanup completed: {count} sessions removed")
        return count
    
    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Get a summary of session state for monitoring.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session summary or None if not found
        """
        session = self.session_service.get_session(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "contract_type": session.contract_metadata.contract_type,
            "parties": session.contract_metadata.parties,
            "clauses_count": len(session.extracted_clauses),
            "risks_count": len(session.risk_assessments),
            "redlines_count": len(session.redline_proposals),
            "has_summary": session.negotiation_summary is not None,
            "has_audit": session.audit_bundle is not None
        }
    
    def list_user_sessions(self, user_id: str, limit: int = 10) -> list:
        """List recent sessions for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summaries
        """
        return self.session_service.list_sessions(user_id=user_id, limit=limit)


def create_session_manager(
    db_path: Optional[str] = None,
    cleanup_hours: Optional[int] = None,
    enable_persistence: Optional[bool] = None
) -> SessionManager:
    """Factory function to create a SessionManager with environment-based configuration.
    
    Args:
        db_path: Optional database path (uses env var if not provided)
        cleanup_hours: Optional cleanup hours (uses env var if not provided)
        enable_persistence: Optional persistence flag (uses env var if not provided)
        
    Returns:
        Configured SessionManager instance
    """
    return SessionManager(
        db_path=db_path,
        cleanup_hours=cleanup_hours or int(os.getenv("SESSION_CLEANUP_HOURS", "24")),
        enable_persistence=enable_persistence if enable_persistence is not None 
                          else os.getenv("SESSION_PERSISTENCE", "false").lower() == "true"
    )
