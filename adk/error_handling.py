"""Error handling and retry configuration for the Contract Copilot system.

Provides custom exceptions, retry logic, and error handling decorators.
"""

from functools import wraps
from typing import Any, Callable, Optional, Type
import time
from loguru import logger


# Custom Exception Classes

class ContractCopilotError(Exception):
    """Base exception for all Contract Copilot errors."""
    pass


class DocumentParsingError(ContractCopilotError):
    """Raised when document parsing fails."""
    pass


class ExtractionError(ContractCopilotError):
    """Raised when clause extraction fails."""
    pass


class RiskAnalysisError(ContractCopilotError):
    """Raised when risk analysis fails."""
    pass


class RiskAssessmentError(ContractCopilotError):
    """Raised when risk assessment fails."""
    pass


class RedlineGenerationError(ContractCopilotError):
    """Raised when redline generation fails."""
    pass


class NegotiationSummaryError(ContractCopilotError):
    """Raised when negotiation summary generation fails."""
    pass


class ComplianceAuditError(ContractCopilotError):
    """Raised when compliance audit compilation fails."""
    pass


class LLMError(ContractCopilotError):
    """Raised when LLM API calls fail."""
    pass


class ToolExecutionError(ContractCopilotError):
    """Raised when tool execution fails."""
    pass


class SessionError(ContractCopilotError):
    """Raised when session management fails."""
    pass


# Retry Configuration

class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    
    def __init__(
        self,
        attempts: int = 5,
        exp_base: int = 7,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        http_status_codes: Optional[list[int]] = None
    ):
        """Initialize retry configuration.
        
        Args:
            attempts: Maximum number of retry attempts
            exp_base: Base for exponential backoff calculation
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay between retries in seconds
            http_status_codes: HTTP status codes that trigger retries
        """
        self.attempts = attempts
        self.exp_base = exp_base
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.http_status_codes = http_status_codes or [429, 500, 503, 504]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.exp_base ** attempt)
        return min(delay, self.max_delay)


# Default retry configuration for Gemini API
GEMINI_RETRY_CONFIG = RetryConfig(
    attempts=5,
    exp_base=7,
    initial_delay=1.0,
    max_delay=60.0,
    http_status_codes=[429, 500, 503, 504]
)


def retry_with_backoff(
    config: RetryConfig = GEMINI_RETRY_CONFIG,
    exceptions: tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """Decorator to retry function execution with exponential backoff.
    
    Args:
        config: Retry configuration
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < config.attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.attempts} failed, retrying in {delay}s",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.attempts} attempts failed",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__
                        )
            
            raise last_exception
            
        return wrapper
    return decorator


def handle_errors(
    error_type: Type[ContractCopilotError],
    default_return: Any = None,
    reraise: bool = True
) -> Callable:
    """Decorator to handle errors and convert them to custom exception types.
    
    Args:
        error_type: Custom exception type to raise
        default_return: Default value to return on error (if not reraising)
        reraise: Whether to reraise the exception after logging
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
                
            except ContractCopilotError:
                # Already a custom exception, just reraise
                raise
                
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}",
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                if reraise:
                    raise error_type(f"Error in {func.__name__}: {str(e)}") from e
                else:
                    return default_return
                    
        return wrapper
    return decorator


def graceful_degradation(fallback_func: Optional[Callable] = None) -> Callable:
    """Decorator to provide graceful degradation on failure.
    
    Args:
        fallback_func: Optional fallback function to call on error
        
    Returns:
        Decorated function with graceful degradation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.warning(
                    f"Function {func.__name__} failed, attempting graceful degradation",
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(
                            f"Fallback function also failed",
                            error=str(fallback_error),
                            error_type=type(fallback_error).__name__
                        )
                        raise
                else:
                    # Return None or empty result based on function signature
                    return None
                    
        return wrapper
    return decorator
