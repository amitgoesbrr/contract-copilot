"""
FastAPI Backend for AI Contract Reviewer & Negotiation Copilot.

This module provides the REST API layer for the contract review system:
- Contract upload and async processing
- Session status tracking and results retrieval
- Admin authentication and rate limiting
- A2A (Agent-to-Agent) protocol support

Architecture:
    Client -> FastAPI -> Orchestrator -> Multi-Agent Pipeline -> Results
"""

import base64
import hashlib
import hmac
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from loguru import logger
from pydantic import BaseModel

from adk.a2a_wrapper import create_a2a_app
from adk.error_handling import ContractCopilotError, DocumentParsingError
from adk.logging_config import setup_logging
from adk.orchestrator import ContractReviewOrchestrator, create_orchestrator
from api.security import (
    get_security_headers,
    get_tls_config,
    log_security_audit,
    validate_api_key_format,
    validate_environment_security,
)
from memory.session_manager import create_session_manager

load_dotenv()

setup_logging(
    log_dir="logs",
    level=os.getenv("LOG_LEVEL", "INFO"),
    rotation="100 MB",
    retention="30 days",
)


# =============================================================================
# FastAPI Application Setup
# =============================================================================

app = FastAPI(
    title="AI Contract Reviewer & Negotiation Copilot",
    description="Multi-agent system for automated contract review, risk assessment, and negotiation preparation",
    version="1.0.0",
)

# CORS configuration for frontend communication
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Rate limiting: requests per window (sliding window algorithm)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "50"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# =============================================================================
# Authentication Helpers
# =============================================================================


def create_session_token(admin_code: str) -> str:
    """Create HMAC-signed session token with timestamp for expiration tracking."""
    timestamp = str(int(time.time()))
    secret = admin_code.encode()
    msg = f"{admin_code}:{timestamp}".encode()
    signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    token = f"{timestamp}:{signature}"
    return base64.b64encode(token.encode()).decode()


def verify_session_token(token: str, admin_code: str) -> bool:
    """Verify session token signature and check 24-hour expiration."""
    try:
        decoded = base64.b64decode(token).decode()
        timestamp, signature = decoded.split(":")

        # Token expires after 24 hours
        if time.time() - int(timestamp) > 86400:
            return False

        secret = admin_code.encode()
        msg = f"{admin_code}:{timestamp}".encode()
        expected_sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected_sig)
    except Exception:
        return False


# =============================================================================
# Middleware Stack
# =============================================================================


@app.middleware("http")
async def admin_access_middleware(request: Request, call_next):
    """Enforce admin authentication via session cookie. Skips public endpoints."""
    admin_code = os.getenv("ADMIN_ACCESS_CODE")

    if not admin_code:
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)

    # Public endpoints that don't require authentication
    public_paths = ["/", "/health", "/docs", "/openapi.json", "/verify"]
    if request.url.path in public_paths:
        return await call_next(request)

    session_token = request.cookies.get("admin_session")
    if not session_token or not verify_session_token(session_token, admin_code):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized: Invalid or expired session"},
        )

    return await call_next(request)


# In-memory rate limiter (per-IP request tracking)
request_counts: Dict[str, list] = {}


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Sliding window rate limiter. Bypasses localhost for development."""
    client_ip = request.client.host if request.client else "unknown"

    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return await call_next(request)

    now = time.time()

    if client_ip not in request_counts:
        request_counts[client_ip] = []

    # Remove expired timestamps
    request_counts[client_ip] = [
        ts for ts in request_counts[client_ip] if now - ts < RATE_LIMIT_WINDOW
    ]

    if len(request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests. Please try again later."},
        )

    request_counts[client_ip].append(now)
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Inject security headers (CSP, X-Frame-Options, etc.) into all responses."""
    response = await call_next(request)
    security_headers = get_security_headers()
    for header, value in security_headers.items():
        response.headers[header] = value
    return response


# =============================================================================
# Orchestrator Singleton
# =============================================================================

orchestrator: Optional[ContractReviewOrchestrator] = None
processing_status: Dict[str, Dict[str, Any]] = {}


def get_orchestrator() -> ContractReviewOrchestrator:
    """Lazy initialization of the multi-agent orchestrator singleton."""
    global orchestrator
    if orchestrator is None:
        session_manager = create_session_manager()
        orchestrator = create_orchestrator(session_manager=session_manager)
        logger.info("Orchestrator initialized")
    return orchestrator


# =============================================================================
# A2A Protocol Support
# =============================================================================

try:
    orch_instance = get_orchestrator()
    api_port = int(os.getenv("API_PORT", "8000"))
    a2a_app = create_a2a_app(orch_instance, port=api_port)
    app.mount("/a2a", a2a_app)
    logger.info("A2A Agent mounted at /a2a")
except Exception as e:
    logger.error(f"Failed to initialize A2A agent: {e}")


# =============================================================================
# Request/Response Models
# =============================================================================


class UploadResponse(BaseModel):
    """Response returned after contract upload initiation."""

    session_id: str
    status: str
    message: str
    filename: str


class StatusResponse(BaseModel):
    """Polling response for async processing status."""

    session_id: str
    status: str
    progress: Optional[str] = None
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None


class ResultsResponse(BaseModel):
    """Complete analysis results including agent traces."""

    session_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    agent_traces: Optional[list] = None
    errors: Optional[list] = None
    processing_time_seconds: Optional[float] = None


class AccessCodeRequest(BaseModel):
    """Admin access code for authentication."""

    access_code: str


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AI Contract Reviewer & Negotiation Copilot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "upload": "/upload",
            "status": "/status/{session_id}",
            "results": "/results/{session_id}",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/verify")
async def verify_access(request: AccessCodeRequest, response: Response):
    """Authenticate with admin code and receive session cookie."""
    admin_code = os.getenv("ADMIN_ACCESS_CODE")

    if not admin_code:
        return {"status": "authorized", "message": "No admin code configured"}

    if request.access_code != admin_code:
        raise HTTPException(status_code=401, detail="Invalid access code")

    token = create_session_token(admin_code)

    # Check if running in production (HTTPS)
    is_production = (
        os.getenv("NODE_ENV") == "production"
        or os.getenv("ENVIRONMENT") == "production"
    )

    # HttpOnly cookie prevents XSS attacks
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        samesite="none" if is_production else "lax",
        secure=is_production,
        max_age=86400,
    )

    return {"status": "authorized"}


@app.get("/verify")
async def check_auth_status(request: Request):
    """Check if current session is valid."""
    admin_code = os.getenv("ADMIN_ACCESS_CODE")
    logger.info(f"GET /verify - ADMIN_ACCESS_CODE configured: {bool(admin_code)}")

    if not admin_code:
        logger.warning("No ADMIN_ACCESS_CODE configured - allowing access")
        return {"status": "authorized"}

    session_token = request.cookies.get("admin_session")
    logger.info(f"GET /verify - Session token present: {bool(session_token)}")

    if session_token and verify_session_token(session_token, admin_code):
        return {"status": "authorized"}

    raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/cleanup/{session_id}")
async def cleanup_session(session_id: str):
    """Manually cleanup a session.

    This endpoint allows explicit cleanup of session data.
    Useful for ensuring sensitive data is removed immediately.

    Args:
        session_id: Session identifier

    Returns:
        Cleanup status

    Raises:
        HTTPException: If session not found
    """
    if session_id not in processing_status:
        # Check if session exists in database
        if orchestrator:
            session = orchestrator.session_manager.get_session_summary(session_id)
            if session:
                # Session exists in database but not in memory
                deleted = orchestrator.cleanup_session(session_id)
                return {
                    "session_id": session_id,
                    "status": "cleaned",
                    "deleted_from_database": deleted,
                    "message": "Session cleaned from database",
                }

        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Cleanup session data
    _cleanup_session_data(session_id)

    return {
        "session_id": session_id,
        "status": "cleaned",
        "message": "Session data cleaned successfully",
    }


@app.post("/cleanup/all")
async def cleanup_all_sessions():
    """Cleanup all old sessions based on configured policy.

    This endpoint runs the cleanup process for all sessions older than
    the configured cleanup period. Requires admin access in production.

    Returns:
        Cleanup summary
    """
    # Clear in-memory processing status
    memory_count = len(processing_status)
    processing_status.clear()

    # Run database cleanup
    db_count = 0
    if orchestrator:
        db_count = orchestrator.session_manager.run_cleanup()

    logger.info(f"Manual cleanup: {memory_count} from memory, {db_count} from database")

    return {
        "status": "completed",
        "memory_sessions_cleared": memory_count,
        "database_sessions_cleaned": db_count,
        "message": "Cleanup completed successfully",
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = "default_user",
):
    """Upload a contract file for processing.

    Args:
        file: Contract file (PDF or text)
        user_id: User identifier (optional)

    Returns:
        UploadResponse with session_id and status

    Raises:
        HTTPException: If file validation fails or processing cannot start
    """
    logger.info(f"Received upload request: {file.filename}")

    # Validate file type
    max_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    allowed_types = os.getenv("ALLOWED_FILE_TYPES", "pdf,txt").split(",")

    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    try:
        # Read file content
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)

        if file_size_mb > max_size_mb:
            raise HTTPException(
                status_code=400, detail=f"File too large. Maximum size: {max_size_mb}MB"
            )

        logger.info(f"File validated: {file.filename} ({file_size_mb:.2f}MB)")

        # Generate session ID
        import uuid

        session_id = str(uuid.uuid4())

        # Log security audit event
        log_security_audit(
            "session_created",
            session_id,
            {
                "user_id": user_id,
                "filename": file.filename,
                "file_size_mb": file_size_mb,
            },
        )

        # Initialize processing status
        processing_status[session_id] = {
            "status": "processing",
            "filename": file.filename,
            "started_at": time.time(),
            "progress": "Initializing...",
        }

        # Process contract in background
        background_tasks.add_task(
            process_contract_async,
            session_id=session_id,
            file_bytes=file_content,
            filename=file.filename,
            user_id=user_id,
        )

        return UploadResponse(
            session_id=session_id,
            status="processing",
            message="Contract uploaded successfully. Processing started.",
            filename=file.filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_contract_async(
    session_id: str, file_bytes: bytes, filename: str, user_id: str
):
    """Process contract asynchronously in background.

    Args:
        session_id: Session identifier
        file_bytes: File content as bytes
        filename: Original filename
        user_id: User identifier
    """
    try:
        logger.info(f"Starting async processing for session {session_id}")

        # Update status
        processing_status[session_id]["progress"] = "Processing contract..."

        # Get orchestrator and process
        orch = get_orchestrator()
        result = orch.process_contract(
            file_bytes=file_bytes,
            filename=filename,
            user_id=user_id,
            session_id=session_id,
        )

        # Update status with results
        processing_status[session_id].update(
            {
                "status": result["status"],
                "results": result["results"],
                "agent_traces": result["agent_traces"],
                "errors": result.get("errors", []),
                "processing_time_seconds": result["processing_time_seconds"],
                "completed_at": time.time(),
            }
        )

        logger.info(f"Processing completed for session {session_id}")

    except DocumentParsingError as e:
        logger.error(f"Document parsing failed for session {session_id}: {e}")
        processing_status[session_id].update(
            {
                "status": "failed",
                "error": f"Document parsing failed: {str(e)}",
                "completed_at": time.time(),
            }
        )

    except ContractCopilotError as e:
        logger.error(f"Processing failed for session {session_id}: {e}")
        processing_status[session_id].update(
            {"status": "failed", "error": str(e), "completed_at": time.time()}
        )

    except Exception as e:
        logger.error(f"Unexpected error for session {session_id}: {e}")
        processing_status[session_id].update(
            {
                "status": "failed",
                "error": f"Unexpected error: {str(e)}",
                "completed_at": time.time(),
            }
        )


@app.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """Get processing status for a session.

    Args:
        session_id: Session identifier

    Returns:
        StatusResponse with current status and progress

    Raises:
        HTTPException: If session not found
    """
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    status_data = processing_status[session_id]

    # Calculate processing time
    processing_time = None
    if "completed_at" in status_data:
        processing_time = status_data["completed_at"] - status_data["started_at"]
    elif "started_at" in status_data:
        processing_time = time.time() - status_data["started_at"]

    return StatusResponse(
        session_id=session_id,
        status=status_data["status"],
        progress=status_data.get("progress"),
        error=status_data.get("error"),
        processing_time_seconds=processing_time,
    )


@app.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: str, cleanup: bool = True):
    """Get complete results for a processed contract.

    Args:
        session_id: Session identifier
        cleanup: Whether to cleanup session data after retrieval (default: True)

    Returns:
        ResultsResponse with complete processing results

    Raises:
        HTTPException: If session not found or still processing
    """
    # Check in-memory status first
    if session_id in processing_status:
        status_data = processing_status[session_id]

        if status_data["status"] == "processing":
            raise HTTPException(status_code=202, detail="Processing in progress")

        if status_data["status"] == "failed":
            return ResultsResponse(
                session_id=session_id,
                status="failed",
                errors=[status_data.get("error", "Unknown error")],
                processing_time_seconds=status_data.get("processing_time_seconds"),
            )

        # Serialize results for JSON response
        serialized_results = _serialize_results(status_data["results"])
        serialized_traces = _serialize_traces(status_data["agent_traces"])

        # Cleanup if requested
        if cleanup:
            background_tasks = BackgroundTasks()
            background_tasks.add_task(_cleanup_session_data, session_id)

        return ResultsResponse(
            session_id=session_id,
            status="completed",
            results=serialized_results,
            agent_traces=serialized_traces,
            processing_time_seconds=status_data.get("processing_time_seconds"),
        )

    # Fallback to database
    orch = get_orchestrator()
    session = orch.session_manager.session_service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Construct response from DB session
    import msgspec

    # Reconstruct results dict
    results = {
        "extraction": {
            "clauses": [msgspec.to_builtins(c) for c in session.extracted_clauses]
        },
        "risk_scoring": {
            "risks": [msgspec.to_builtins(r) for r in session.risk_assessments]
        },
        "redlining": {
            "redlines": [msgspec.to_builtins(r) for r in session.redline_proposals]
        },
        "summary": {
            "negotiation_summary": (
                msgspec.to_builtins(session.negotiation_summary)
                if session.negotiation_summary
                else None
            )
        },
        "audit": {
            "audit_bundle": (
                msgspec.to_builtins(session.audit_bundle)
                if session.audit_bundle
                else None
            )
        },
    }

    # Get traces from events (simplified reconstruction)
    # For now return empty list as we don't fully reconstruct traces from events yet
    agent_traces = []

    return ResultsResponse(
        session_id=session_id,
        status="completed",
        results=results,
        agent_traces=agent_traces,
        processing_time_seconds=None,
    )


# =============================================================================
# Serialization Helpers
# =============================================================================


def _serialize_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert msgspec Struct objects to JSON-serializable dicts."""
    import msgspec

    serialized = {}
    for key, value in results.items():
        if isinstance(value, dict):
            serialized[key] = _serialize_results(value)
        elif isinstance(value, list):
            serialized[key] = [
                (
                    msgspec.to_builtins(item)
                    if hasattr(item, "__struct_fields__")
                    else item
                )
                for item in value
            ]
        elif hasattr(value, "__struct_fields__"):
            serialized[key] = msgspec.to_builtins(value)
        else:
            serialized[key] = value

    return serialized


def _serialize_traces(traces: list) -> list:
    """Convert AgentTrace structs to JSON-serializable format."""
    import msgspec

    return [
        msgspec.to_builtins(trace) if hasattr(trace, "__struct_fields__") else trace
        for trace in traces
    ]


def _cleanup_session_data(session_id: str) -> None:
    """
    Remove session from memory and optionally from database.

    Behavior depends on SESSION_PERSISTENCE env var:
    - false: Immediate deletion for privacy
    - true: Retain for configured cleanup period
    """
    try:
        log_security_audit(
            "session_cleanup",
            session_id,
            {
                "persistence_enabled": os.getenv("SESSION_PERSISTENCE", "false").lower()
                == "true"
            },
        )

        if session_id in processing_status:
            del processing_status[session_id]
            logger.info(f"Removed session {session_id} from processing status")

        if orchestrator:
            deleted = orchestrator.cleanup_session(session_id)
            if deleted:
                logger.info(f"Session {session_id} deleted from database")
                log_security_audit(
                    "session_deleted", session_id, {"reason": "persistence_disabled"}
                )
            else:
                logger.info(f"Session {session_id} retained (persistence enabled)")

    except Exception as e:
        logger.error(f"Failed to cleanup session {session_id}: {e}")


# =============================================================================
# Application Lifecycle Events
# =============================================================================


@app.on_event("startup")
async def startup_event():
    """Validate configuration and initialize services on startup."""
    logger.info("Starting AI Contract Reviewer API")

    security_validation = validate_environment_security()

    if not security_validation["valid"]:
        for error in security_validation["errors"]:
            logger.error(f"Security validation error: {error}")
        raise ValueError(
            "Security validation failed. Check environment configuration:\n"
            + "\n".join(f"  - {error}" for error in security_validation["errors"])
        )

    for warning in security_validation["warnings"]:
        logger.warning(f"Security warning: {warning}")

    logger.info("Security validation passed")
    get_orchestrator()

    tls_config = get_tls_config()
    if tls_config:
        logger.info("TLS/SSL enabled")
    else:
        logger.warning("TLS/SSL not enabled - use HTTPS in production")

    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown: clear sessions and run cleanup."""
    logger.info("Shutting down AI Contract Reviewer API")

    session_count = len(processing_status)
    processing_status.clear()
    logger.info(f"Cleared {session_count} sessions from memory")

    if orchestrator:
        try:
            cleaned = orchestrator.session_manager.run_cleanup()
            logger.info(f"Database cleanup completed: {cleaned} sessions removed")
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")


@app.get("/sessions")
async def list_sessions(limit: int = 20, user_id: Optional[str] = None):
    """List recent sessions.

    Args:
        limit: Maximum number of sessions to return
        user_id: Optional user ID to filter by

    Returns:
        List of session summaries
    """
    try:
        orch = get_orchestrator()
        sessions = orch.session_manager.list_user_sessions(
            user_id=user_id if user_id else "default_user",  # Default user for now
            limit=limit,
        )
        return sessions
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/file")
async def download_original_file(session_id: str):
    """Download the original contract file for a session."""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")

        file_data = orchestrator.session_manager.session_service.get_session_file(
            session_id
        )
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")

        file_bytes, filename, mime_type = file_data

        # Determine media type
        media_type = mime_type or "application/octet-stream"

        # Create response with file content
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all associated data."""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Service not initialized")

        # Check if session exists first
        session = orchestrator.session_manager.session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Delete session
        deleted = orchestrator.session_manager.session_service.delete_session(
            session_id
        )
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete session")

        return {"message": "Session deleted successfully", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/{session_id}/markdown")
async def get_results_markdown(session_id: str):
    """Get session results as markdown.

    Args:
        session_id: Session identifier

    Returns:
        Markdown string
    """
    try:
        orch = get_orchestrator()
        session = orch.session_manager.get_session_summary(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get full session data
        full_session = orch.session_manager.session_service.get_session(session_id)
        if not full_session:
            raise HTTPException(status_code=404, detail="Session data not found")

        # Generate markdown
        md = f"# Contract Analysis Report\n\n"
        md += f"**Session ID:** {session_id}\n\n"
        md += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "---\n\n"

        # Executive Summary
        if (
            full_session.negotiation_summary
            and full_session.negotiation_summary.executive_summary
        ):
            md += f"## Executive Summary\n\n{full_session.negotiation_summary.executive_summary}\n\n"

        # Risks
        if full_session.risk_assessments:
            md += f"## Risk Assessment\n\n"
            for risk in full_session.risk_assessments:
                md += f"### {risk.risk_type} ({risk.severity.upper()})\n\n"
                md += f"**Explanation:** {risk.explanation}\n\n"
                if risk.llm_rationale:
                    md += f"**AI Analysis:** {risk.llm_rationale}\n\n"
                md += "---\n\n"

        # Clauses
        if full_session.extracted_clauses:
            md += f"## Extracted Clauses\n\n"
            for clause in full_session.extracted_clauses:
                md += f"### {clause.type}\n\n"
                md += f"{clause.text}\n\n"

        return JSONResponse(content=md)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    # Get TLS configuration
    tls_config = get_tls_config()

    if tls_config:
        logger.info(f"Starting HTTPS server on {host}:{port}")
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
            ssl_certfile=tls_config["certfile"],
            ssl_keyfile=tls_config["keyfile"],
        )
    else:
        logger.info(f"Starting HTTP server on {host}:{port}")
        logger.warning("TLS not configured - use HTTPS in production")
        uvicorn.run("api.main:app", host=host, port=port, reload=True, log_level="info")
