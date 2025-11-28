"""Logging configuration using Loguru for structured logging.

Provides session-aware logging with JSON formatting, rotation, and retention policies.
"""

import sys
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional
from loguru import logger
import json


# Remove default handler
logger.remove()


def setup_logging(
    log_dir: str = "logs",
    level: str = "DEBUG",
    rotation: str = "100 MB",
    retention: str = "30 days",
    compression: str = "zip"
) -> None:
    """Configure Loguru logging with structured JSON format.
    
    Args:
        log_dir: Directory for log files
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        rotation: When to rotate log files
        retention: How long to keep old logs
        compression: Compression format for rotated logs
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Console handler with colored output
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        level=level,
        colorize=True
    )
    
    # Main application log with JSON format
    logger.add(
        log_path / "contract_copilot_{time}.log",
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        level=level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        serialize=False
    )
    
    # JSON structured log for parsing and analysis
    logger.add(
        log_path / "contract_copilot_json_{time}.log",
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        level=level,
        rotation=rotation,
        retention=retention,
        compression=compression,
        serialize=True
    )
    
    # Agent-specific log file
    def agent_format(record):
        session_id = record["extra"].get("session_id", "unknown")
        agent_name = record["extra"].get("agent_name", "unknown")
        return f"{record['time']} | {record['level'].name} | {session_id} | {agent_name} | {record['message']}\n"
    
    logger.add(
        log_path / "agents_{time}.log",
        format=agent_format,
        level="INFO",
        rotation=rotation,
        retention=retention,
        compression=compression,
        filter=lambda record: "agent_name" in record["extra"]
    )
    
    # Error-only log file
    logger.add(
        log_path / "errors_{time}.log",
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression=compression
    )
    
    logger.info("Logging system initialized", log_dir=log_dir, level=level)


def get_session_logger(session_id: str, agent_name: Optional[str] = None):
    """Get a logger bound to a specific session and optionally an agent.
    
    Args:
        session_id: Unique session identifier
        agent_name: Optional agent name for agent-specific logging
        
    Returns:
        Logger instance with session context
    """
    context = {"session_id": session_id}
    if agent_name:
        context["agent_name"] = agent_name
    return logger.bind(**context)


def log_agent_execution(agent_name: str) -> Callable:
    """Decorator to log agent method execution with timing.
    
    Args:
        agent_name: Name of the agent being executed
        
    Returns:
        Decorated function with logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            session_id = kwargs.get("session_id", "unknown")
            agent_logger = get_session_logger(session_id, agent_name)
            
            agent_logger.info(f"Starting {agent_name} execution", function=func.__name__)
            
            try:
                import time
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                agent_logger.info(
                    f"{agent_name} completed successfully",
                    function=func.__name__,
                    duration_seconds=round(duration, 3)
                )
                return result
                
            except Exception as e:
                agent_logger.error(
                    f"{agent_name} failed with error",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
                
        return wrapper
    return decorator


def log_tool_execution(tool_name: str) -> Callable:
    """Decorator to log tool execution.
    
    Args:
        tool_name: Name of the tool being executed
        
    Returns:
        Decorated function with logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger.debug(f"Executing tool: {tool_name}", function=func.__name__)
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Tool {tool_name} completed", function=func.__name__)
                return result
                
            except Exception as e:
                logger.error(
                    f"Tool {tool_name} failed",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
                
        return wrapper
    return decorator
