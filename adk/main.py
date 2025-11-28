#!/usr/bin/env python3
"""Main entry point for the AI Contract Reviewer & Negotiation Copilot.

This module provides the main application entry point with:
- CLI argument parsing for configuration
- Agent and orchestrator initialization
- Session service and Memory Bank setup
- Graceful shutdown handling
- Environment-based configuration
"""

import os
import sys
import signal
import argparse
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

from adk.orchestrator import create_orchestrator, ContractReviewOrchestrator
from adk.logging_config import setup_logging
from memory.session_manager import create_session_manager, SessionManager
from adk.error_handling import ContractCopilotError


class ContractCopilotApplication:
    """Main application class for the Contract Copilot system.
    
    Manages application lifecycle including initialization, configuration,
    and graceful shutdown.
    """
    
    def __init__(self, args: argparse.Namespace):
        """Initialize the application with parsed arguments.
        
        Args:
            args: Parsed command-line arguments
        """
        self.args = args
        self.orchestrator: Optional[ContractReviewOrchestrator] = None
        self.session_manager: Optional[SessionManager] = None
        self._shutdown_requested = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        logger.warning(f"Received {signal_name} signal, initiating graceful shutdown...")
        self._shutdown_requested = True
        self.shutdown()
        sys.exit(0)
    
    def initialize(self) -> None:
        """Initialize all application components.
        
        Sets up:
        - Logging system
        - Session manager and Memory Bank
        - Agent orchestrator
        - Configuration validation
        
        Raises:
            ContractCopilotError: If initialization fails
        """
        try:
            # Setup logging
            setup_logging(
                log_dir=self.args.log_dir,
                level=self.args.log_level,
                rotation=self.args.log_rotation,
                retention=self.args.log_retention
            )
            
            logger.info("=" * 80)
            logger.info("AI Contract Reviewer & Negotiation Copilot")
            logger.info("=" * 80)
            logger.info(f"Version: 1.0.0")
            logger.info(f"Python: {sys.version.split()[0]}")
            logger.info(f"Log Level: {self.args.log_level}")
            logger.info(f"Log Directory: {self.args.log_dir}")
            
            # Validate API key
            if not self.args.api_key:
                logger.error("GOOGLE_API_KEY not set. Please set it in .env file or via --api-key argument")
                raise ContractCopilotError("Missing GOOGLE_API_KEY")
            
            logger.info(f"API Key: {'*' * 8}{self.args.api_key[-4:]}")
            logger.info(f"Model: {self.args.model_name}")
            
            # Initialize session manager
            logger.info("Initializing session manager...")
            self.session_manager = create_session_manager(
                db_path=self.args.db_path,
                cleanup_hours=self.args.cleanup_hours,
                enable_persistence=self.args.enable_persistence
            )
            logger.info(
                f"Session manager initialized (persistence={self.args.enable_persistence}, "
                f"cleanup_hours={self.args.cleanup_hours})"
            )
            
            # Initialize orchestrator
            logger.info("Initializing agent orchestrator...")
            self.orchestrator = create_orchestrator(
                session_manager=self.session_manager,
                api_key=self.args.api_key,
                model_name=self.args.model_name,
                enable_graceful_degradation=self.args.enable_graceful_degradation,
                enable_observability=self.args.enable_observability
            )
            logger.info("Agent orchestrator initialized successfully")
            
            # Run initial cleanup if configured
            if self.args.cleanup_on_start:
                logger.info("Running initial session cleanup...")
                cleaned = self.session_manager.run_cleanup()
                logger.info(f"Initial cleanup completed: {cleaned} sessions removed")
            
            logger.info("=" * 80)
            logger.info("Application initialized successfully")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Application initialization failed: {e}")
            raise ContractCopilotError(f"Initialization failed: {e}")
    
    def process_contract(
        self,
        file_path: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None
    ) -> dict:
        """Process a contract file through the agent pipeline.
        
        Args:
            file_path: Path to contract file
            user_id: User identifier
            session_id: Optional session ID
            
        Returns:
            Processing results dictionary
            
        Raises:
            ContractCopilotError: If processing fails
        """
        if self._shutdown_requested:
            raise ContractCopilotError("Shutdown requested, cannot process contract")
        
        if not self.orchestrator:
            raise ContractCopilotError("Orchestrator not initialized")
        
        logger.info(f"Processing contract: {file_path}")
        
        try:
            result = self.orchestrator.process_contract(
                file_path=file_path,
                user_id=user_id,
                session_id=session_id
            )
            
            logger.info(
                f"Contract processing completed",
                session_id=result["session_id"],
                status=result["status"],
                processing_time=result["processing_time_seconds"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Contract processing failed: {e}")
            raise
    
    def get_orchestrator(self) -> ContractReviewOrchestrator:
        """Get the orchestrator instance.
        
        Returns:
            ContractReviewOrchestrator instance
            
        Raises:
            ContractCopilotError: If orchestrator not initialized
        """
        if not self.orchestrator:
            raise ContractCopilotError("Orchestrator not initialized")
        return self.orchestrator
    
    def get_session_manager(self) -> SessionManager:
        """Get the session manager instance.
        
        Returns:
            SessionManager instance
            
        Raises:
            ContractCopilotError: If session manager not initialized
        """
        if not self.session_manager:
            raise ContractCopilotError("Session manager not initialized")
        return self.session_manager
    
    def shutdown(self) -> None:
        """Perform graceful shutdown of the application.
        
        Cleans up resources and performs final session cleanup if configured.
        """
        logger.info("Shutting down application...")
        
        try:
            # Run final cleanup if configured
            if self.session_manager and self.args.cleanup_on_shutdown:
                logger.info("Running final session cleanup...")
                cleaned = self.session_manager.run_cleanup()
                logger.info(f"Final cleanup completed: {cleaned} sessions removed")
            
            logger.info("Application shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="AI Contract Reviewer & Negotiation Copilot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default configuration (uses .env file)
  python -m adk.main
  
  # Process a specific contract file
  python -m adk.main --file sample_contracts/sample_nda.md
  
  # Run with custom configuration
  python -m adk.main --api-key YOUR_KEY --model gemini-2.0-flash-exp --log-level DEBUG
  
  # Disable persistence for maximum privacy
  python -m adk.main --no-persistence
  
  # Run cleanup and exit
  python -m adk.main --cleanup-only

For more information, see README.md
        """
    )
    
    # API Configuration
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("GOOGLE_API_KEY"),
        help="Google API key for Gemini (default: from GOOGLE_API_KEY env var)"
    )
    
    parser.add_argument(
        "--model-name",
        type=str,
        default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
        help="Gemini model name (default: gemini-2.0-flash-exp)"
    )
    
    # Logging Configuration
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getenv("LOG_DIR", "logs"),
        help="Directory for log files (default: logs)"
    )
    
    parser.add_argument(
        "--log-rotation",
        type=str,
        default="100 MB",
        help="Log rotation size (default: 100 MB)"
    )
    
    parser.add_argument(
        "--log-retention",
        type=str,
        default="30 days",
        help="Log retention period (default: 30 days)"
    )
    
    # Database Configuration
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,  # Will use session_manager default
        help="Database path (default: from DATABASE_URL env var or contract_copilot.db)"
    )
    
    # Session Management
    parser.add_argument(
        "--enable-persistence",
        dest="enable_persistence",
        action="store_true",
        default=os.getenv("SESSION_PERSISTENCE", "false").lower() == "true",
        help="Enable session persistence (default: from SESSION_PERSISTENCE env var)"
    )
    
    parser.add_argument(
        "--no-persistence",
        dest="enable_persistence",
        action="store_false",
        help="Disable session persistence (delete sessions immediately)"
    )
    
    parser.add_argument(
        "--cleanup-hours",
        type=int,
        default=int(os.getenv("SESSION_CLEANUP_HOURS", "24")),
        help="Hours after which inactive sessions are cleaned up (default: 24)"
    )
    
    parser.add_argument(
        "--cleanup-on-start",
        action="store_true",
        default=True,
        help="Run session cleanup on application start (default: True)"
    )
    
    parser.add_argument(
        "--cleanup-on-shutdown",
        action="store_true",
        default=True,
        help="Run session cleanup on application shutdown (default: True)"
    )
    
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Run cleanup and exit without starting the application"
    )
    
    # Agent Configuration
    parser.add_argument(
        "--enable-graceful-degradation",
        dest="enable_graceful_degradation",
        action="store_true",
        default=os.getenv("GRACEFUL_DEGRADATION", "true").lower() == "true",
        help="Enable graceful degradation on agent failures (default: True)"
    )
    
    parser.add_argument(
        "--no-graceful-degradation",
        dest="enable_graceful_degradation",
        action="store_false",
        help="Disable graceful degradation (fail fast on errors)"
    )
    
    parser.add_argument(
        "--enable-observability",
        dest="enable_observability",
        action="store_true",
        default=os.getenv("ENABLE_OBSERVABILITY", "true").lower() == "true",
        help="Enable observability (tracing and metrics) (default: True)"
    )
    
    parser.add_argument(
        "--no-observability",
        dest="enable_observability",
        action="store_false",
        help="Disable observability features"
    )
    
    # File Processing
    parser.add_argument(
        "--file",
        type=str,
        help="Contract file to process (optional, for CLI usage)"
    )
    
    parser.add_argument(
        "--user-id",
        type=str,
        default="default_user",
        help="User ID for session tracking (default: default_user)"
    )
    
    parser.add_argument(
        "--session-id",
        type=str,
        help="Optional session ID (generates new if not provided)"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point for the application.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Parse command-line arguments
    args = parse_arguments()
    
    try:
        # Handle cleanup-only mode
        if args.cleanup_only:
            setup_logging(log_dir=args.log_dir, level=args.log_level)
            logger.info("Running cleanup-only mode...")
            
            session_manager = create_session_manager(
                db_path=args.db_path,
                cleanup_hours=args.cleanup_hours
            )
            
            cleaned = session_manager.run_cleanup()
            logger.info(f"Cleanup completed: {cleaned} sessions removed")
            return 0
        
        # Initialize application
        app = ContractCopilotApplication(args)
        app.initialize()
        
        # If a file is provided, process it
        if args.file:
            file_path = Path(args.file)
            
            if not file_path.exists():
                logger.error(f"File not found: {args.file}")
                return 1
            
            logger.info(f"Processing file: {args.file}")
            result = app.process_contract(
                file_path=str(file_path),
                user_id=args.user_id,
                session_id=args.session_id
            )
            
            # Print summary
            logger.info("=" * 80)
            logger.info("Processing Summary")
            logger.info("=" * 80)
            logger.info(f"Session ID: {result['session_id']}")
            logger.info(f"Status: {result['status']}")
            logger.info(f"Processing Time: {result['processing_time_seconds']:.2f}s")
            
            if result.get('results'):
                results = result['results']
                if 'extraction' in results:
                    logger.info(f"Clauses Extracted: {results['extraction'].get('clause_count', 0)}")
                if 'risk_scoring' in results:
                    logger.info(f"High Risk Clauses: {results['risk_scoring'].get('high_risk_count', 0)}")
                if 'redline' in results:
                    logger.info(f"Redline Proposals: {results['redline'].get('proposal_count', 0)}")
            
            if result.get('errors'):
                logger.warning(f"Errors Encountered: {len(result['errors'])}")
                for error in result['errors']:
                    logger.warning(f"  - {error}")
            
            logger.info("=" * 80)
            
            # Cleanup session if persistence is disabled
            if not args.enable_persistence:
                logger.info("Cleaning up session (persistence disabled)...")
                app.get_session_manager().cleanup_session(result['session_id'])
        
        else:
            # No file provided, just initialize and wait
            logger.info("Application ready. Use the API or provide --file argument to process contracts.")
            logger.info("Press Ctrl+C to shutdown gracefully.")
            
            # Keep the application running
            try:
                signal.pause()
            except AttributeError:
                # signal.pause() not available on Windows
                import time
                while not app._shutdown_requested:
                    time.sleep(1)
        
        # Graceful shutdown
        app.shutdown()
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
        
    except ContractCopilotError as e:
        logger.error(f"Application error: {e}")
        return 1
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
