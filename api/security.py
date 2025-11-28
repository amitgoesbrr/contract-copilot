"""Security utilities for API authentication and data protection."""

import os
import re
from typing import Optional, Dict, Any
from loguru import logger


def validate_api_key_format(api_key: str) -> bool:
    """Validate Google API key format."""
    if not api_key:
        return False
    
    placeholder_values = [
        "your_gemini_api_key_here",
        "your_api_key_here",
        "placeholder",
        "test_key",
        "demo_key"
    ]
    
    if api_key.lower() in placeholder_values:
        return False
    
    if api_key.startswith("AIza") and len(api_key) == 39:
        return True
    
    if len(api_key) >= 20 and re.match(r'^[A-Za-z0-9_-]+$', api_key):
        return True
    
    return False


def validate_environment_security() -> Dict[str, Any]:
    """Validate security configuration from environment variables.
    
    Returns:
        Dictionary with validation results and warnings
    """
    warnings = []
    errors = []
    
    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        errors.append("GOOGLE_API_KEY is not set")
    elif not validate_api_key_format(api_key):
        errors.append("GOOGLE_API_KEY has invalid format or is a placeholder")
    
    # Check session persistence configuration
    session_persistence = os.getenv("SESSION_PERSISTENCE", "false").lower()
    if session_persistence == "true":
        warnings.append(
            "SESSION_PERSISTENCE is enabled. Ensure this is intentional for your privacy requirements."
        )
    
    # Check CORS configuration
    cors_origins = os.getenv("CORS_ORIGINS", "")
    if "*" in cors_origins:
        warnings.append(
            "CORS_ORIGINS includes wildcard (*). This is insecure for production."
        )
    elif not cors_origins:
        warnings.append("CORS_ORIGINS is not configured")
    
    # Check TLS configuration
    tls_enabled = os.getenv("TLS_ENABLED", "false").lower() == "true"
    if not tls_enabled:
        warnings.append(
            "TLS is not enabled. HTTPS should be used in production."
        )
    
    # Check log level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level == "DEBUG":
        warnings.append(
            "LOG_LEVEL is set to DEBUG. Consider using INFO or WARNING in production."
        )
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def sanitize_session_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize session data by removing sensitive information.
    
    This function removes or redacts sensitive data before logging or
    returning to clients.
    
    Args:
        data: Session data dictionary
        
    Returns:
        Sanitized data dictionary
    """
    sanitized = data.copy()
    
    # Remove full contract text (keep only metadata)
    if "normalized_text" in sanitized:
        text = sanitized["normalized_text"]
        sanitized["normalized_text"] = f"[REDACTED: {len(text)} characters]"
    
    # Redact party names in metadata (optional - depends on privacy requirements)
    if "contract_metadata" in sanitized and isinstance(sanitized["contract_metadata"], dict):
        metadata = sanitized["contract_metadata"]
        if "parties" in metadata:
            metadata["parties"] = [f"Party_{i+1}" for i in range(len(metadata["parties"]))]
    
    return sanitized


def get_security_headers() -> Dict[str, str]:
    """Get recommended security headers for API responses.
    
    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }


def get_tls_config() -> Optional[Dict[str, str]]:
    """Get TLS/SSL configuration from environment.
    
    Returns:
        Dictionary with cert and key paths, or None if TLS is not enabled
    """
    import os.path as ospath
    
    tls_enabled = os.getenv("TLS_ENABLED", "false").lower() == "true"
    
    if not tls_enabled:
        return None
    
    cert_path = os.getenv("TLS_CERT_PATH")
    key_path = os.getenv("TLS_KEY_PATH")
    
    if not cert_path or not key_path:
        logger.warning("TLS_ENABLED is true but certificate paths are not configured")
        return None
    
    # Verify files exist
    if not ospath.isfile(cert_path):
        logger.error(f"TLS certificate not found: {cert_path}")
        return None
    
    if not ospath.isfile(key_path):
        logger.error(f"TLS key not found: {key_path}")
        return None
    
    return {
        "certfile": cert_path,
        "keyfile": key_path
    }


def log_security_audit(event_type: str, session_id: str, details: Optional[Dict[str, Any]] = None):
    """Log security-related events for audit trail.
    
    Args:
        event_type: Type of security event (e.g., "session_created", "session_deleted")
        session_id: Session identifier
        details: Optional additional details
    """
    audit_entry = {
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "details": details or {}
    }
    
    logger.info(f"SECURITY_AUDIT: {event_type}", **audit_entry)
