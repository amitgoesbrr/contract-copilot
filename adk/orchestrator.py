"""
Contract Review Orchestrator - Multi-agent pipeline coordinator.

Manages the sequential execution of specialized agents:
    Ingestion -> Extraction -> Risk Scoring -> Redlining -> Summary -> Audit

Key Features:
- Memory Bank integration for state persistence between agents
- Graceful degradation: continues processing even if individual agents fail
- OpenTelemetry tracing for observability
- Session resume capability for long-running operations
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from loguru import logger

from adk.models import (
    ContractMetadata,
    ContractSession,
    Clause,
    RiskAssessment,
    RedlineProposal,
    NegotiationSummary,
    AuditBundle,
    AgentTrace
)
from adk.error_handling import (
    ContractCopilotError,
    DocumentParsingError,
    ExtractionError,
    RiskAnalysisError,
    RedlineGenerationError,
    SessionError,
    graceful_degradation
)
from adk.observability import (
    ObservabilityManager,
    initialize_observability,
    get_observability_manager
)
from memory.memory_bank import MemoryBank

if TYPE_CHECKING:
    from memory.session_manager import SessionManager

from adk.agents import (
    IngestionAgent,
    ClauseExtractionAgent,
    RiskScoringAgent,
    RedlineSuggestionAgent,
    NegotiationSummaryAgent,
    ComplianceAuditAgent
)


class ContractReviewOrchestrator:
    """
    Coordinates the multi-agent contract review pipeline.
    
    Each agent reads from and writes to the Memory Bank, enabling
    state persistence and session resume capabilities.
    5. Provides session state management
    """
    
    def __init__(
        self,
        session_manager: Optional["SessionManager"] = None,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite",
        enable_graceful_degradation: bool = True,
        enable_observability: bool = True
    ):
        """Initialize the orchestrator.
        
        Args:
            session_manager: SessionManager instance (creates default if not provided)
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use for all agents
            enable_graceful_degradation: Whether to continue on agent failures
            enable_observability: Whether to enable tracing and metrics
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name
        self.enable_graceful_degradation = enable_graceful_degradation
        
        # Initialize session manager
        if session_manager is None:
            from memory.session_manager import create_session_manager
            session_manager = create_session_manager()
        
        self.session_manager = session_manager
        self.memory_bank = session_manager.get_memory_bank()
        
        # Initialize observability
        self.observability = initialize_observability(
            enable_tracing=enable_observability,
            enable_metrics=enable_observability
        ) if enable_observability else None
        
        # Initialize agents
        self._initialize_agents()
        
        # Track agent execution traces
        self.agent_traces: List[AgentTrace] = []
        
        logger.info(
            "ContractReviewOrchestrator initialized",
            model=model_name,
            graceful_degradation=enable_graceful_degradation,
            observability=enable_observability
        )
    
    def _initialize_agents(self):
        """Initialize all agents in the pipeline."""
        try:
            self.ingestion_agent = IngestionAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            self.extraction_agent = ClauseExtractionAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            self.risk_agent = RiskScoringAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            self.redline_agent = RedlineSuggestionAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            self.summary_agent = NegotiationSummaryAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            self.audit_agent = ComplianceAuditAgent(
                api_key=self.api_key,
                model_name=self.model_name
            )
            
            logger.info("All agents initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise ContractCopilotError(f"Agent initialization failed: {e}")
    
    def process_contract(
        self,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        user_id: str = "default_user",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a contract through the complete agent pipeline.
        
        Args:
            file_path: Path to contract file (for local files)
            file_bytes: File content as bytes (for uploads)
            filename: Original filename (required if using file_bytes)
            user_id: User identifier
            session_id: Optional session ID (generates new if not provided)
            
        Returns:
            Dictionary containing:
                - session_id: Session identifier
                - status: Overall processing status
                - results: Complete processing results
                - agent_traces: Execution traces for all agents
                - errors: Any errors encountered (if graceful degradation enabled)
                
        Raises:
            ContractCopilotError: If processing fails critically
        """
        start_time = time.time()
        self.agent_traces = []
        errors = []
        
        # Start new trace for this processing run
        if self.observability:
            self.observability.start_trace()
        
        logger.info(
            "Starting contract processing",
            user_id=user_id,
            session_id=session_id,
            filename=filename or file_path
        )
        
        try:
            # Step 1: Ingestion
            ingestion_result = self._run_ingestion(
                file_path=file_path,
                file_bytes=file_bytes,
                filename=filename,
                session_id=session_id
            )
            
            # Create session with ingestion results
            if session_id is None:
                session_id = ingestion_result["session_id"]
            
            # Step 2: Clause Extraction
            extraction_result = self._run_extraction(session_id)
            
            # Step 3: Risk Scoring
            risk_result = self._run_risk_scoring(session_id)
            
            # Step 4: Redline Suggestions
            redline_result = self._run_redline_generation(session_id)
            
            # Step 5: Negotiation Summary
            summary_result = self._run_summary_generation(session_id)
            
            # Step 6: Compliance Audit
            audit_result = self._run_audit_compilation(session_id)
            
            # Calculate total processing time
            total_time = time.time() - start_time
            
            # Calculate and record metrics
            if self.observability:
                # Calculate extraction accuracy
                if extraction_result.get("clauses"):
                    self.observability.calculate_extraction_accuracy(
                        extraction_result["clauses"]
                    )
                
                # Calculate risk detection rate
                if risk_result.get("risk_assessments"):
                    self.observability.calculate_risk_detection_rate(
                        risk_result["risk_assessments"]
                    )
                
                # Export trace and metrics
                self.observability.export_trace(session_id)
                self.observability.export_metrics()
            
            logger.info(
                "Contract processing complete",
                session_id=session_id,
                total_time_seconds=total_time,
                errors_count=len(errors)
            )
            
            return {
                "session_id": session_id,
                "status": "completed" if not errors else "completed_with_errors",
                "results": {
                    "ingestion": ingestion_result,
                    "extraction": extraction_result,
                    "risk_scoring": risk_result,
                    "redline": redline_result,
                    "summary": summary_result,
                    "audit": audit_result
                },
                "agent_traces": self.agent_traces,
                "errors": errors,
                "processing_time_seconds": total_time
            }
            
        except Exception as e:
            logger.error(f"Contract processing failed: {e}", session_id=session_id)
            
            # Try to save partial results if session was created
            if session_id:
                try:
                    self._save_partial_results(session_id, errors)
                except Exception as save_error:
                    logger.error(f"Failed to save partial results: {save_error}")
            
            raise ContractCopilotError(f"Contract processing failed: {e}")
    
    def _run_ingestion(
        self,
        file_path: Optional[str],
        file_bytes: Optional[bytes],
        filename: Optional[str],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run ingestion agent with error tracking.
        
        Returns:
            Ingestion results including session_id
        """
        agent_name = "IngestionAgent"
        start_time = time.time()
        
        # Create trace span if observability is enabled
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("filename", filename or file_path or "unknown")
        
        try:
            logger.info(f"Running {agent_name}")
            
            # Generate session ID if not provided
            import uuid
            if session_id is None:
                session_id = str(uuid.uuid4())
            
            if span:
                span.set_attribute("session_id", session_id)
            
            # Check if session already exists with data
            if session_id:
                try:
                    existing_session = self.memory_bank.get_session_state(session_id)
                    if existing_session and existing_session.normalized_text:
                        logger.info(f"Resuming session {session_id}: Skipping ingestion", session_id=session_id)
                        return {
                            "session_id": session_id,
                            "normalized_contract": existing_session.normalized_text,
                            "metadata": existing_session.contract_metadata,
                            "page_count": existing_session.contract_metadata.page_count if existing_session.contract_metadata else 0,
                            "status": "skipped_already_exists"
                        }
                except Exception:
                    # If session lookup fails, proceed with ingestion
                    pass

            # Process file
            result = self.ingestion_agent.process_file(
                file_path=file_path,
                file_bytes=file_bytes,
                filename=filename,
                session_id=session_id
            )
            
            # Determine mime type
            import mimetypes
            mime_type = None
            if filename:
                mime_type, _ = mimetypes.guess_type(filename)

            # Create session in database
            session, _ = self.session_manager.create_new_session(
                user_id="default_user",
                contract_metadata=result["metadata"],
                normalized_text=result["normalized_contract"],
                filename=filename or "Unknown Contract",
                file_bytes=file_bytes,
                mime_type=mime_type,
                session_id=session_id
            )
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
            
            # Update span
            if span:
                span.set_attribute("page_count", result.get("page_count", 0))
                span.set_attribute("text_length", len(result.get("normalized_contract", "")))
                span.set_status("OK")
                span.end()
            
            logger.info(f"{agent_name} completed", latency_seconds=latency)
            
            result["session_id"] = session_id
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}")
            raise DocumentParsingError(f"Ingestion failed: {e}")
    
    def _run_extraction(self, session_id: str) -> Dict[str, Any]:
        """Run clause extraction agent with error tracking."""
        agent_name = "ClauseExtractionAgent"
        start_time = time.time()
        
        # Create trace span
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("session_id", session_id)
        
        try:
            logger.info(f"Running {agent_name}", session_id=session_id)
            
            # Get normalized text from memory
            normalized_text = self.memory_bank.get_normalized_text(session_id)
            
            if span:
                span.set_attribute("input_length", len(normalized_text))
            
            # Check for existing clauses
            existing_clauses = self.memory_bank.get_clauses(session_id)
            if existing_clauses:
                logger.info(f"Resuming session {session_id}: Skipping extraction", session_id=session_id)
                return {
                    "clauses": existing_clauses,
                    "clause_count": len(existing_clauses),
                    "status": "skipped_already_exists"
                }

            # Extract clauses
            result = self.extraction_agent.extract_clauses(
                normalized_text=normalized_text,
                session_id=session_id
            )
            
            # Store clauses in memory
            self.memory_bank.store_clauses(session_id, result["clauses"])
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
                self.observability.metrics.record_clause_count(result["clause_count"])
            
            # Update span
            if span:
                span.set_attribute("clause_count", result["clause_count"])
                span.set_status("OK")
                span.end()
            
            logger.info(
                f"{agent_name} completed",
                session_id=session_id,
                clause_count=result["clause_count"],
                latency_seconds=latency
            )
            
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}", session_id=session_id)
            
            if not self.enable_graceful_degradation:
                raise ExtractionError(f"Clause extraction failed: {e}")
            
            # Return empty result for graceful degradation
            return {"clauses": [], "clause_count": 0, "error": str(e)}
    
    def _run_risk_scoring(self, session_id: str) -> Dict[str, Any]:
        """Run risk scoring agent with error tracking."""
        agent_name = "RiskScoringAgent"
        start_time = time.time()
        
        # Create trace span
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("session_id", session_id)
        
        try:
            logger.info(f"Running {agent_name}", session_id=session_id)
            
            # Get clauses from memory
            clauses = self.memory_bank.get_clauses(session_id)
            
            if not clauses:
                logger.warning(f"No clauses available for risk scoring", session_id=session_id)
                if span:
                    span.set_attribute("warning", "No clauses to score")
                    span.set_status("OK")
                    span.end()
                return {"risk_assessments": [], "high_risk_count": 0, "warning": "No clauses to score"}
            
            if span:
                span.set_attribute("clause_count", len(clauses))
            
            # Check for existing risk assessments
            existing_risks = self.memory_bank.get_risk_assessments(session_id)
            if existing_risks:
                logger.info(f"Resuming session {session_id}: Skipping risk scoring", session_id=session_id)
                high_risk_count = sum(1 for r in existing_risks if r.severity == "high")
                return {
                    "risk_assessments": existing_risks,
                    "high_risk_count": high_risk_count,
                    "status": "skipped_already_exists"
                }

            # Score risks
            result = self.risk_agent.assess_risks(
                clauses=clauses,
                session_id=session_id
            )
            
            # Store risk assessments in memory
            self.memory_bank.store_risk_assessments(session_id, result["risk_assessments"])
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
                self.observability.metrics.record_high_risk_count(result.get("high_risk_count", 0))
            
            # Update span
            if span:
                span.set_attribute("risk_count", len(result["risk_assessments"]))
                span.set_attribute("high_risk_count", result.get("high_risk_count", 0))
                span.set_status("OK")
                span.end()
            
            logger.info(
                f"{agent_name} completed",
                session_id=session_id,
                risk_count=len(result["risk_assessments"]),
                high_risk_count=result.get("high_risk_count", 0),
                latency_seconds=latency
            )
            
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}", session_id=session_id)
            
            if not self.enable_graceful_degradation:
                raise RiskAnalysisError(f"Risk scoring failed: {e}")
            
            return {"risk_assessments": [], "high_risk_count": 0, "error": str(e)}
    
    def _run_redline_generation(self, session_id: str) -> Dict[str, Any]:
        """Run redline suggestion agent with error tracking."""
        agent_name = "RedlineSuggestionAgent"
        start_time = time.time()
        
        # Create trace span
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("session_id", session_id)
        
        try:
            logger.info(f"Running {agent_name}", session_id=session_id)
            
            # Get clauses and risk assessments from memory
            clauses = self.memory_bank.get_clauses(session_id)
            risk_assessments = self.memory_bank.get_risk_assessments(session_id)
            
            if not clauses or not risk_assessments:
                logger.warning(
                    f"Insufficient data for redline generation",
                    session_id=session_id,
                    clauses_count=len(clauses),
                    risks_count=len(risk_assessments)
                )
                return {
                    "redline_proposals": [],
                    "proposal_count": 0,
                    "warning": "Insufficient data for redline generation"
                }
            
            # Check for existing redline proposals
            existing_proposals = self.memory_bank.get_redline_proposals(session_id)
            if existing_proposals:
                logger.info(f"Resuming session {session_id}: Skipping redline generation", session_id=session_id)
                return {
                    "redline_proposals": existing_proposals,
                    "proposal_count": len(existing_proposals),
                    "status": "skipped_already_exists"
                }

            # Generate redlines
            result = self.redline_agent.generate_redlines(
                clauses=clauses,
                risk_assessments=risk_assessments,
                session_id=session_id
            )
            
            # Store redline proposals in memory
            self.memory_bank.store_redline_proposals(session_id, result["redline_proposals"])
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
            
            # Update span
            if span:
                span.set_attribute("proposal_count", result["proposal_count"])
                span.set_status("OK")
                span.end()
            
            logger.info(
                f"{agent_name} completed",
                session_id=session_id,
                proposal_count=result["proposal_count"],
                latency_seconds=latency
            )
            
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}", session_id=session_id)
            
            if not self.enable_graceful_degradation:
                raise RedlineGenerationError(f"Redline generation failed: {e}")
            
            return {"redline_proposals": [], "proposal_count": 0, "error": str(e)}
    
    def _run_summary_generation(self, session_id: str) -> Dict[str, Any]:
        """Run negotiation summary agent with error tracking."""
        agent_name = "NegotiationSummaryAgent"
        start_time = time.time()
        
        # Create trace span
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("session_id", session_id)
        
        try:
            logger.info(f"Running {agent_name}", session_id=session_id)
            
            # Get clauses, risk assessments and redline proposals from memory
            clauses = self.memory_bank.get_clauses(session_id)
            risk_assessments = self.memory_bank.get_risk_assessments(session_id)
            redline_proposals = self.memory_bank.get_redline_proposals(session_id)
            session = self.memory_bank.get_session_state(session_id)
            
            if not risk_assessments:
                logger.warning(
                    f"No risk assessments available for summary",
                    session_id=session_id
                )
                return {"warning": "No risk assessments available for summary"}
            
            # Check for existing summary
            existing_summary = self.memory_bank.get_negotiation_summary(session_id)
            if existing_summary:
                logger.info(f"Resuming session {session_id}: Skipping summary generation", session_id=session_id)
                return {
                    "negotiation_summary": existing_summary,
                    "status": "skipped_already_exists"
                }

            # Generate summary
            result = self.summary_agent.generate_summary(
                clauses=clauses,
                risk_assessments=risk_assessments,
                redline_proposals=redline_proposals,
                session_id=session_id,
                contract_metadata=session.contract_metadata if session else None
            )
            
            # Store negotiation summary in memory
            self.memory_bank.store_negotiation_summary(session_id, result["negotiation_summary"])
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
            
            # Update span
            if span:
                span.set_status("OK")
                span.end()
            
            logger.info(
                f"{agent_name} completed",
                session_id=session_id,
                latency_seconds=latency
            )
            
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}", session_id=session_id)
            
            if not self.enable_graceful_degradation:
                raise ContractCopilotError(f"Summary generation failed: {e}")
            
            return {"error": str(e)}
    
    def _run_audit_compilation(self, session_id: str) -> Dict[str, Any]:
        """Run compliance audit agent with error tracking."""
        agent_name = "ComplianceAuditAgent"
        start_time = time.time()
        
        # Create trace span
        span = None
        if self.observability and self.observability.tracer:
            span = self.observability.tracer.start_span(agent_name)
            span.set_attribute("agent_name", agent_name)
            span.set_attribute("session_id", session_id)
        
        try:
            logger.info(f"Running {agent_name}", session_id=session_id)
            
            # Get complete session state from memory
            session = self.memory_bank.get_session_state(session_id)
            
            # Check for existing audit bundle
            existing_bundle = self.memory_bank.get_audit_bundle(session_id)
            if existing_bundle:
                logger.info(f"Resuming session {session_id}: Skipping audit compilation", session_id=session_id)
                return {
                    "audit_bundle": existing_bundle,
                    "status": "skipped_already_exists"
                }

            # Compile audit bundle
            result = self.audit_agent.compile_audit_bundle(
                session_id=session_id,
                original_contract=session.normalized_text,
                extracted_clauses=session.extracted_clauses,
                risk_assessments=session.risk_assessments,
                redline_proposals=session.redline_proposals,
                negotiation_summary=session.negotiation_summary,
                agent_traces=self.agent_traces,
                contract_metadata=session.contract_metadata
            )
            
            # Store audit bundle in memory
            self.memory_bank.store_audit_bundle(session_id, result["audit_bundle"])
            
            # Record trace
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=True)
            
            # Record metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_latency(agent_name, latency)
                self.observability.metrics.record_agent_success(agent_name)
            
            # Update span
            if span:
                span.set_status("OK")
                span.end()
            
            logger.info(
                f"{agent_name} completed",
                session_id=session_id,
                latency_seconds=latency
            )
            
            return result
            
        except Exception as e:
            latency = time.time() - start_time
            self._record_trace(agent_name, latency, success=False, error=str(e))
            
            # Record error metrics
            if self.observability and self.observability.metrics:
                self.observability.metrics.record_agent_error(agent_name)
            
            # Update span
            if span:
                span.set_status("ERROR", str(e))
                span.end()
            
            logger.error(f"{agent_name} failed: {e}", session_id=session_id)
            
            if not self.enable_graceful_degradation:
                raise ContractCopilotError(f"Audit compilation failed: {e}")
            
            return {"error": str(e)}
    
    def _record_trace(
        self,
        agent_name: str,
        latency: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record agent execution trace.
        
        Args:
            agent_name: Name of the agent
            latency: Execution time in seconds
            success: Whether execution succeeded
            error: Error message if failed
        """
        import hashlib
        
        trace = AgentTrace(
            agent_name=agent_name,
            timestamp=datetime.now(),
            input_hash=hashlib.sha256(agent_name.encode()).hexdigest()[:16],
            output_hash=hashlib.sha256(f"{agent_name}_{success}".encode()).hexdigest()[:16],
            latency_seconds=round(latency, 3),
            success=success,
            error_message=error
        )
        
        self.agent_traces.append(trace)
    
    def _save_partial_results(self, session_id: str, errors: List[str]):
        """Save partial results when processing fails.
        
        Args:
            session_id: Session identifier
            errors: List of error messages
        """
        try:
            # Store error information in custom state
            self.memory_bank.set_custom_state(
                session_id,
                "processing_errors",
                errors
            )
            
            self.memory_bank.set_custom_state(
                session_id,
                "processing_status",
                "failed"
            )
            
            logger.info(f"Saved partial results for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to save partial results: {e}")
    
    def get_session_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve results for a completed session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session results or None if not found
        """
        try:
            session = self.memory_bank.get_session_state(session_id)
            
            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "metadata": session.contract_metadata,
                "clauses": session.extracted_clauses,
                "risk_assessments": session.risk_assessments,
                "redline_proposals": session.redline_proposals,
                "negotiation_summary": session.negotiation_summary,
                "audit_bundle": session.audit_bundle,
                "created_at": session.created_at,
                "updated_at": session.updated_at
            }
            
        except SessionError:
            logger.warning(f"Session not found: {session_id}")
            return None
    
    def cleanup_session(self, session_id: str) -> bool:
        """Clean up a session based on persistence configuration.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted
        """
        return self.session_manager.cleanup_session(session_id)
    
    def get_agent_traces(self) -> List[AgentTrace]:
        """Get execution traces for the last processing run.
        
        Returns:
            List of AgentTrace objects
        """
        return self.agent_traces


def create_orchestrator(
    session_manager: Optional["SessionManager"] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    enable_graceful_degradation: Optional[bool] = None,
    enable_observability: Optional[bool] = None
) -> ContractReviewOrchestrator:
    """Factory function to create an orchestrator with environment-based configuration.
    
    Args:
        session_manager: Optional SessionManager instance
        api_key: Optional API key (uses env var if not provided)
        model_name: Optional model name (uses env var or default)
        enable_graceful_degradation: Optional flag (uses env var or default)
        enable_observability: Optional flag (uses env var or default)
        
    Returns:
        Configured ContractReviewOrchestrator instance
    """
    if model_name is None:
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    
    if enable_graceful_degradation is None:
        enable_graceful_degradation = os.getenv("GRACEFUL_DEGRADATION", "true").lower() == "true"
    
    if enable_observability is None:
        enable_observability = os.getenv("ENABLE_OBSERVABILITY", "true").lower() == "true"
    
    return ContractReviewOrchestrator(
        session_manager=session_manager,
        api_key=api_key,
        model_name=model_name,
        enable_graceful_degradation=enable_graceful_degradation,
        enable_observability=enable_observability
    )
