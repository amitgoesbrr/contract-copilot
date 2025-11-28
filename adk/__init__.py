"""AI Contract Reviewer & Negotiation Copilot - ADK Package."""

from adk.models import (
    Clause,
    RiskAssessment,
    RedlineProposal,
    NegotiationSummary,
    ContractMetadata,
    AgentTrace,
    AuditBundle,
    ContractSession,
)

from adk.logging_config import (
    setup_logging,
    get_session_logger,
    log_agent_execution,
    log_tool_execution,
)

from adk.error_handling import (
    ContractCopilotError,
    DocumentParsingError,
    ExtractionError,
    RiskAnalysisError,
    RedlineGenerationError,
    LLMError,
    ToolExecutionError,
    SessionError,
    RetryConfig,
    GEMINI_RETRY_CONFIG,
    retry_with_backoff,
    handle_errors,
    graceful_degradation,
)

from adk.orchestrator import (
    ContractReviewOrchestrator,
    create_orchestrator,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Clause",
    "RiskAssessment",
    "RedlineProposal",
    "NegotiationSummary",
    "ContractMetadata",
    "AgentTrace",
    "AuditBundle",
    "ContractSession",
    # Logging
    "setup_logging",
    "get_session_logger",
    "log_agent_execution",
    "log_tool_execution",
    # Error Handling
    "ContractCopilotError",
    "DocumentParsingError",
    "ExtractionError",
    "RiskAnalysisError",
    "RedlineGenerationError",
    "LLMError",
    "ToolExecutionError",
    "SessionError",
    "RetryConfig",
    "GEMINI_RETRY_CONFIG",
    "retry_with_backoff",
    "handle_errors",
    "graceful_degradation",
    # Orchestrator
    "ContractReviewOrchestrator",
    "create_orchestrator",
]
