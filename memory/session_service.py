"""Session management service using SQLite for state persistence.

This module provides DatabaseSessionService for managing contract review sessions,
including session creation, retrieval, state updates, and cleanup policies.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import msgspec

from adk.models import ContractSession, ContractMetadata
from adk.error_handling import SessionError
from loguru import logger


class DatabaseSessionService:
    """Session service using SQLite for persistent storage.
    
    Manages contract review sessions with support for:
    - Session creation and retrieval
    - State persistence across agent executions
    - Event logging for audit trails
    - Configurable cleanup policies
    """
    
    def __init__(self, db_path: str = "contract_copilot.db", cleanup_hours: int = 24):
        """Initialize the database session service.
        
        Args:
            db_path: Path to SQLite database file
            cleanup_hours: Hours after which inactive sessions are cleaned up
        """
        self.db_path = db_path
        self.cleanup_hours = cleanup_hours
        self._ensure_database_exists()
        logger.info(f"DatabaseSessionService initialized with db_path={db_path}, cleanup_hours={cleanup_hours}")
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT DEFAULT 'Unknown Contract',
                    file_mime_type TEXT,
                    original_file_blob BLOB,
                    contract_metadata TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    extracted_clauses TEXT DEFAULT '[]',
                    risk_assessments TEXT DEFAULT '[]',
                    redline_proposals TEXT DEFAULT '[]',
                    negotiation_summary TEXT,
                    audit_bundle TEXT
                )
            """)
            
            # Check for new columns (migration)
            cursor.execute("PRAGMA table_info(sessions)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "filename" not in columns:
                logger.info("Migrating database: Adding filename column")
                cursor.execute("ALTER TABLE sessions ADD COLUMN filename TEXT DEFAULT 'Unknown Contract'")
                
            if "file_mime_type" not in columns:
                logger.info("Migrating database: Adding file_mime_type column")
                cursor.execute("ALTER TABLE sessions ADD COLUMN file_mime_type TEXT")
                
            if "original_file_blob" not in columns:
                logger.info("Migrating database: Adding original_file_blob column")
                cursor.execute("ALTER TABLE sessions ADD COLUMN original_file_blob BLOB")
            
            # Events table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # State table for key-value storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    session_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, key),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Create indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
                ON sessions(user_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at 
                ON sessions(updated_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_session_id 
                ON events(session_id)
            """)
            
            conn.commit()
            logger.debug("Database schema initialized successfully")
    
    def create_session(
        self,
        session_id: str,
        user_id: str,
        filename: str,
        contract_metadata: ContractMetadata,
        normalized_text: str,
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> ContractSession:
        """Create a new contract review session.
        
        Args:
            session_id: Unique identifier for the session
            user_id: User who initiated the session
            filename: Name of the contract file
            contract_metadata: Extracted contract metadata
            normalized_text: Normalized contract text
            file_bytes: Original file content
            mime_type: MIME type of the file
            
        Returns:
            ContractSession object
            
        Raises:
            SessionError: If session creation fails
        """
        try:
            now = datetime.utcnow()
            session = ContractSession(
                session_id=session_id,
                user_id=user_id,
                filename=filename,
                file_mime_type=mime_type,
                contract_metadata=contract_metadata,
                normalized_text=normalized_text,
                created_at=now,
                updated_at=now
            )
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sessions (
                        session_id, user_id, filename, file_mime_type, original_file_blob,
                        contract_metadata, normalized_text, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id,
                    session.user_id,
                    session.filename,
                    session.file_mime_type,
                    file_bytes,
                    msgspec.json.encode(session.contract_metadata).decode(),
                    session.normalized_text,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat()
                ))
                conn.commit()
            
            self._log_event(session_id, "session_created", {"user_id": user_id, "filename": filename})
            logger.info(f"Session created: {session_id} for user: {user_id}, file: {filename}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            raise SessionError(f"Session creation failed: {e}")
    
    def get_session(self, session_id: str) -> Optional[ContractSession]:
        """Retrieve a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ContractSession object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Note: We exclude original_file_blob from standard retrieval to keep it light
                cursor.execute("""
                    SELECT session_id, user_id, contract_metadata, normalized_text,
                           created_at, updated_at, extracted_clauses, risk_assessments,
                           redline_proposals, negotiation_summary, audit_bundle, 
                           filename, file_mime_type
                    FROM sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Session not found: {session_id}")
                    return None
                
                # Deserialize the session data with proper types
                from adk.models import Clause, RiskAssessment, RedlineProposal, NegotiationSummary, AuditBundle
                
                # Handle potential missing columns during migration/race conditions
                filename = row[11] if len(row) > 11 else "Unknown Contract"
                mime_type = row[12] if len(row) > 12 else None
                
                session = ContractSession(
                    session_id=row[0],
                    user_id=row[1],
                    filename=filename,
                    file_mime_type=mime_type,
                    contract_metadata=msgspec.json.decode(row[2], type=ContractMetadata),
                    normalized_text=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]),
                    extracted_clauses=msgspec.json.decode(row[6], type=list[Clause]) if row[6] else [],
                    risk_assessments=msgspec.json.decode(row[7], type=list[RiskAssessment]) if row[7] else [],
                    redline_proposals=msgspec.json.decode(row[8], type=list[RedlineProposal]) if row[8] else [],
                    negotiation_summary=msgspec.json.decode(row[9], type=NegotiationSummary) if row[9] else None,
                    audit_bundle=msgspec.json.decode(row[10], type=AuditBundle) if row[10] else None
                )
                
                logger.debug(f"Session retrieved: {session_id}")
                return session
                
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            raise SessionError(f"Session retrieval failed: {e}")

    def get_session_file(self, session_id: str) -> Optional[tuple[bytes, str, str]]:
        """Retrieve the original file for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Tuple of (file_bytes, filename, mime_type) or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT original_file_blob, filename, file_mime_type
                    FROM sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if not row or not row[0]:
                    return None
                
                return (row[0], row[1], row[2])
                
        except Exception as e:
            logger.error(f"Failed to retrieve file for session {session_id}: {e}")
            raise SessionError(f"File retrieval failed: {e}")
    
    def update_session(self, session: ContractSession) -> None:
        """Update an existing session with new state.
        
        Args:
            session: Updated ContractSession object
            
        Raises:
            SessionError: If update fails
        """
        try:
            session.updated_at = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sessions SET
                        user_id = ?,
                        filename = ?,
                        file_mime_type = ?,
                        contract_metadata = ?,
                        normalized_text = ?,
                        updated_at = ?,
                        extracted_clauses = ?,
                        risk_assessments = ?,
                        redline_proposals = ?,
                        negotiation_summary = ?,
                        audit_bundle = ?
                    WHERE session_id = ?
                """, (
                    session.user_id,
                    session.filename,
                    session.file_mime_type,
                    msgspec.json.encode(session.contract_metadata).decode(),
                    session.normalized_text,
                    session.updated_at.isoformat(),
                    msgspec.json.encode(session.extracted_clauses).decode(),
                    msgspec.json.encode(session.risk_assessments).decode(),
                    msgspec.json.encode(session.redline_proposals).decode(),
                    msgspec.json.encode(session.negotiation_summary).decode() if session.negotiation_summary else None,
                    msgspec.json.encode(session.audit_bundle).decode() if session.audit_bundle else None,
                    session.session_id
                ))
                conn.commit()
            
            self._log_event(session.session_id, "session_updated", {})
            logger.debug(f"Session updated: {session.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to update session {session.session_id}: {e}")
            raise SessionError(f"Session update failed: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all associated data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete from state table
                cursor.execute("DELETE FROM state WHERE session_id = ?", (session_id,))
                
                # Delete from events table
                cursor.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
                
                # Delete from sessions table
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                
                deleted = cursor.rowcount > 0
                conn.commit()
            
            if deleted:
                logger.info(f"Session deleted: {session_id}")
            else:
                logger.warning(f"Session not found for deletion: {session_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise SessionError(f"Session deletion failed: {e}")
    
    def list_sessions(self, user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List sessions, optionally filtered by user.
        
        Args:
            user_id: Optional user ID to filter by
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if user_id:
                    cursor.execute("""
                        SELECT session_id, user_id, created_at, updated_at, filename
                        FROM sessions
                        WHERE user_id = ?
                        ORDER BY updated_at DESC
                        LIMIT ?
                    """, (user_id, limit))
                else:
                    cursor.execute("""
                        SELECT session_id, user_id, created_at, updated_at, filename
                        FROM sessions
                        ORDER BY updated_at DESC
                        LIMIT ?
                    """, (limit,))
                
                sessions = []
                for row in cursor.fetchall():
                    # Handle case where filename column might not exist yet (if migration failed or race condition)
                    filename = row[4] if len(row) > 4 else "Unknown Contract"
                    
                    sessions.append({
                        "session_id": row[0],
                        "user_id": row[1],
                        "created_at": row[2],
                        "updated_at": row[3],
                        "filename": filename
                    })
                
                logger.debug(f"Listed {len(sessions)} sessions")
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise SessionError(f"Session listing failed: {e}")
    
    def cleanup_old_sessions(self) -> int:
        """Clean up sessions older than the configured cleanup period.
        
        Returns:
            Number of sessions deleted
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.cleanup_hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find sessions to delete
                cursor.execute("""
                    SELECT session_id FROM sessions
                    WHERE updated_at < ?
                """, (cutoff_time.isoformat(),))
                
                session_ids = [row[0] for row in cursor.fetchall()]
                
                if not session_ids:
                    logger.debug("No old sessions to clean up")
                    return 0
                
                # Delete associated data
                placeholders = ','.join('?' * len(session_ids))
                cursor.execute(f"DELETE FROM state WHERE session_id IN ({placeholders})", session_ids)
                cursor.execute(f"DELETE FROM events WHERE session_id IN ({placeholders})", session_ids)
                cursor.execute(f"DELETE FROM sessions WHERE session_id IN ({placeholders})", session_ids)
                
                deleted_count = len(session_ids)
                conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old sessions (older than {self.cleanup_hours} hours)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            raise SessionError(f"Session cleanup failed: {e}")
    
    def set_state(self, session_id: str, key: str, value: Any) -> None:
        """Set a key-value pair in session state.
        
        Args:
            session_id: Session identifier
            key: State key
            value: State value (will be JSON serialized)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO state (session_id, key, value, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    session_id,
                    key,
                    json.dumps(value),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()
            
            logger.debug(f"State set for session {session_id}: {key}")
            
        except Exception as e:
            logger.error(f"Failed to set state for session {session_id}: {e}")
            raise SessionError(f"State update failed: {e}")
    
    def get_state(self, session_id: str, key: str) -> Optional[Any]:
        """Get a value from session state.
        
        Args:
            session_id: Session identifier
            key: State key
            
        Returns:
            State value or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM state
                    WHERE session_id = ? AND key = ?
                """, (session_id, key))
                
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
                
        except Exception as e:
            logger.error(f"Failed to get state for session {session_id}: {e}")
            raise SessionError(f"State retrieval failed: {e}")
    
    def _log_event(self, session_id: str, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log an event for audit trail.
        
        Args:
            session_id: Session identifier
            event_type: Type of event
            event_data: Event data dictionary
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events (session_id, event_type, event_data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (
                    session_id,
                    event_type,
                    json.dumps(event_data),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Failed to log event for session {session_id}: {e}")
    
    def get_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all events for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of event dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_type, event_data, timestamp
                    FROM events
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,))
                
                events = []
                for row in cursor.fetchall():
                    events.append({
                        "event_type": row[0],
                        "event_data": json.loads(row[1]),
                        "timestamp": row[2]
                    })
                
                return events
                
        except Exception as e:
            logger.error(f"Failed to get events for session {session_id}: {e}")
            raise SessionError(f"Event retrieval failed: {e}")
