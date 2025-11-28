"""Observability and tracing module for Contract Copilot.

Provides OpenTelemetry-compatible tracing, metrics collection, and trace export
for monitoring agent execution, performance, and accuracy.
"""

import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from contextlib import contextmanager

from loguru import logger

from adk.models import AgentTrace, Clause, RiskAssessment


class TraceSpan:
    """Represents a single trace span for an operation.
    
    Compatible with OpenTelemetry span structure.
    """
    
    def __init__(
        self,
        name: str,
        span_id: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        start_time: Optional[float] = None
    ):
        """Initialize a trace span.
        
        Args:
            name: Name of the operation (e.g., "ClauseExtractionAgent")
            span_id: Unique identifier for this span
            trace_id: Trace identifier (shared across related spans)
            parent_span_id: Parent span ID for nested operations
            start_time: Start timestamp (defaults to current time)
        """
        self.name = name
        self.span_id = span_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.start_time = start_time or time.time()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.status: str = "OK"
        self.error_message: Optional[str] = None
    
    def set_attribute(self, key: str, value: Any):
        """Set a span attribute.
        
        Args:
            key: Attribute name
            value: Attribute value
        """
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span.
        
        Args:
            name: Event name
            attributes: Optional event attributes
        """
        event = {
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        }
        self.events.append(event)
    
    def set_status(self, status: str, error_message: Optional[str] = None):
        """Set span status.
        
        Args:
            status: Status string ("OK" or "ERROR")
            error_message: Optional error message
        """
        self.status = status
        self.error_message = error_message
    
    def end(self):
        """End the span and record end time."""
        self.end_time = time.time()
    
    def duration_ms(self) -> float:
        """Get span duration in milliseconds.
        
        Returns:
            Duration in milliseconds
        """
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary format.
        
        Returns:
            Dictionary representation of the span
        """
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error_message": self.error_message
        }


class Tracer:
    """Tracer for creating and managing trace spans."""
    
    def __init__(self, trace_id: Optional[str] = None):
        """Initialize tracer.
        
        Args:
            trace_id: Optional trace ID (generates new if not provided)
        """
        self.trace_id = trace_id or self._generate_id()
        self.spans: List[TraceSpan] = []
        self.current_span: Optional[TraceSpan] = None
    
    def _generate_id(self) -> str:
        """Generate a unique ID.
        
        Returns:
            Hexadecimal ID string
        """
        return hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
    
    def start_span(
        self,
        name: str,
        parent_span_id: Optional[str] = None
    ) -> TraceSpan:
        """Start a new span.
        
        Args:
            name: Span name
            parent_span_id: Optional parent span ID
            
        Returns:
            New TraceSpan instance
        """
        span_id = self._generate_id()
        
        # Use current span as parent if not specified
        if parent_span_id is None and self.current_span:
            parent_span_id = self.current_span.span_id
        
        span = TraceSpan(
            name=name,
            span_id=span_id,
            trace_id=self.trace_id,
            parent_span_id=parent_span_id
        )
        
        self.spans.append(span)
        self.current_span = span
        
        return span
    
    @contextmanager
    def span(self, name: str, **attributes):
        """Context manager for creating a span.
        
        Args:
            name: Span name
            **attributes: Span attributes
            
        Yields:
            TraceSpan instance
        """
        span = self.start_span(name)
        
        # Set attributes
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
            span.set_status("OK")
        except Exception as e:
            span.set_status("ERROR", str(e))
            raise
        finally:
            span.end()
    
    def get_spans(self) -> List[TraceSpan]:
        """Get all spans in this trace.
        
        Returns:
            List of TraceSpan instances
        """
        return self.spans


class MetricsCollector:
    """Collector for agent execution metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, List[float]] = {
            "extraction_accuracy": [],
            "risk_detection_rate": [],
            "agent_latency": [],
            "high_risk_count": [],
            "clause_count": []
        }
        self.agent_metrics: Dict[str, Dict[str, List[float]]] = {}
    
    def record_extraction_accuracy(self, accuracy: float):
        """Record clause extraction accuracy.
        
        Args:
            accuracy: Accuracy percentage (0-100)
        """
        self.metrics["extraction_accuracy"].append(accuracy)
        logger.debug(f"Recorded extraction accuracy: {accuracy}%")
    
    def record_risk_detection_rate(self, rate: float):
        """Record risk detection rate.
        
        Args:
            rate: Detection rate percentage (0-100)
        """
        self.metrics["risk_detection_rate"].append(rate)
        logger.debug(f"Recorded risk detection rate: {rate}%")
    
    def record_agent_latency(self, agent_name: str, latency_seconds: float):
        """Record agent execution latency.
        
        Args:
            agent_name: Name of the agent
            latency_seconds: Execution time in seconds
        """
        self.metrics["agent_latency"].append(latency_seconds)
        
        # Track per-agent metrics
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = {
                "latency": [],
                "success_count": 0,
                "error_count": 0
            }
        
        self.agent_metrics[agent_name]["latency"].append(latency_seconds)
        logger.debug(f"Recorded {agent_name} latency: {latency_seconds}s")
    
    def record_agent_success(self, agent_name: str):
        """Record successful agent execution.
        
        Args:
            agent_name: Name of the agent
        """
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = {
                "latency": [],
                "success_count": 0,
                "error_count": 0
            }
        
        self.agent_metrics[agent_name]["success_count"] += 1
    
    def record_agent_error(self, agent_name: str):
        """Record agent execution error.
        
        Args:
            agent_name: Name of the agent
        """
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = {
                "latency": [],
                "success_count": 0,
                "error_count": 0
            }
        
        self.agent_metrics[agent_name]["error_count"] += 1
    
    def record_clause_count(self, count: int):
        """Record number of clauses extracted.
        
        Args:
            count: Number of clauses
        """
        self.metrics["clause_count"].append(count)
    
    def record_high_risk_count(self, count: int):
        """Record number of high-risk clauses detected.
        
        Args:
            count: Number of high-risk clauses
        """
        self.metrics["high_risk_count"].append(count)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all metrics.
        
        Returns:
            Dictionary with metric summaries
        """
        summary = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                summary[metric_name] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "p50": self._percentile(values, 50),
                    "p95": self._percentile(values, 95),
                    "p99": self._percentile(values, 99)
                }
        
        # Add per-agent summaries
        summary["agents"] = {}
        for agent_name, agent_data in self.agent_metrics.items():
            latencies = agent_data["latency"]
            total_executions = agent_data["success_count"] + agent_data["error_count"]
            
            summary["agents"][agent_name] = {
                "total_executions": total_executions,
                "success_count": agent_data["success_count"],
                "error_count": agent_data["error_count"],
                "success_rate": (
                    agent_data["success_count"] / total_executions * 100
                    if total_executions > 0 else 0
                ),
                "latency": {
                    "mean": sum(latencies) / len(latencies) if latencies else 0,
                    "p50": self._percentile(latencies, 50) if latencies else 0,
                    "p95": self._percentile(latencies, 95) if latencies else 0,
                    "p99": self._percentile(latencies, 99) if latencies else 0
                }
            }
        
        return summary
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value.
        
        Args:
            values: List of values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]


class TraceExporter:
    """Exporter for trace data in JSON lines format."""
    
    def __init__(self, output_dir: str = "logs/traces"):
        """Initialize trace exporter.
        
        Args:
            output_dir: Directory for trace files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create trace file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.trace_file = self.output_dir / f"traces_{timestamp}.jsonl"
        
        logger.info(f"Trace exporter initialized", trace_file=str(self.trace_file))
    
    def export_trace(self, tracer: Tracer, session_id: Optional[str] = None):
        """Export trace spans to JSON lines file.
        
        Args:
            tracer: Tracer instance with spans
            session_id: Optional session ID
        """
        with open(self.trace_file, 'a') as f:
            for span in tracer.get_spans():
                trace_data = {
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                    "trace_id": tracer.trace_id,
                    "span": span.to_dict()
                }
                f.write(json.dumps(trace_data) + '\n')
        
        logger.debug(
            f"Exported {len(tracer.get_spans())} spans",
            trace_id=tracer.trace_id,
            session_id=session_id
        )
    
    def export_metrics(self, metrics: MetricsCollector):
        """Export metrics summary to JSON file.
        
        Args:
            metrics: MetricsCollector instance
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"
        
        summary = metrics.get_summary()
        summary["timestamp"] = datetime.now().isoformat()
        
        with open(metrics_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Exported metrics summary", metrics_file=str(metrics_file))


class ObservabilityManager:
    """Manager for observability, tracing, and metrics collection."""
    
    def __init__(self, enable_tracing: bool = True, enable_metrics: bool = True):
        """Initialize observability manager.
        
        Args:
            enable_tracing: Whether to enable tracing
            enable_metrics: Whether to enable metrics collection
        """
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        
        self.tracer: Optional[Tracer] = None
        self.metrics: Optional[MetricsCollector] = None
        self.exporter: Optional[TraceExporter] = None
        
        if enable_tracing:
            self.tracer = Tracer()
            self.exporter = TraceExporter()
        
        if enable_metrics:
            self.metrics = MetricsCollector()
        
        logger.info(
            "Observability manager initialized",
            tracing=enable_tracing,
            metrics=enable_metrics
        )
    
    def start_trace(self, trace_id: Optional[str] = None):
        """Start a new trace.
        
        Args:
            trace_id: Optional trace ID
        """
        if self.enable_tracing:
            self.tracer = Tracer(trace_id=trace_id)
    
    def get_tracer(self) -> Optional[Tracer]:
        """Get the current tracer.
        
        Returns:
            Tracer instance or None
        """
        return self.tracer
    
    def get_metrics(self) -> Optional[MetricsCollector]:
        """Get the metrics collector.
        
        Returns:
            MetricsCollector instance or None
        """
        return self.metrics
    
    def export_trace(self, session_id: Optional[str] = None):
        """Export current trace.
        
        Args:
            session_id: Optional session ID
        """
        if self.enable_tracing and self.tracer and self.exporter:
            self.exporter.export_trace(self.tracer, session_id)
    
    def export_metrics(self):
        """Export metrics summary."""
        if self.enable_metrics and self.metrics and self.exporter:
            self.exporter.export_metrics(self.metrics)
    
    def trace_agent_execution(self, agent_name: str) -> Callable:
        """Decorator for tracing agent execution.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Extract session_id if available
                session_id = kwargs.get("session_id", "unknown")
                
                # Create span if tracing is enabled
                if self.enable_tracing and self.tracer:
                    with self.tracer.span(
                        agent_name,
                        agent_name=agent_name,
                        session_id=session_id
                    ) as span:
                        start_time = time.time()
                        
                        try:
                            result = func(*args, **kwargs)
                            latency = time.time() - start_time
                            
                            # Add result attributes
                            if isinstance(result, dict):
                                for key, value in result.items():
                                    if isinstance(value, (str, int, float, bool)):
                                        span.set_attribute(f"result.{key}", value)
                                    elif isinstance(value, list):
                                        span.set_attribute(f"result.{key}_count", len(value))
                            
                            # Record metrics
                            if self.enable_metrics and self.metrics:
                                self.metrics.record_agent_latency(agent_name, latency)
                                self.metrics.record_agent_success(agent_name)
                            
                            return result
                            
                        except Exception as e:
                            # Record error metrics
                            if self.enable_metrics and self.metrics:
                                self.metrics.record_agent_error(agent_name)
                            raise
                else:
                    # No tracing, just execute
                    result = func(*args, **kwargs)
                    
                    # Still record metrics if enabled
                    if self.enable_metrics and self.metrics:
                        start_time = time.time()
                        latency = time.time() - start_time
                        self.metrics.record_agent_latency(agent_name, latency)
                        self.metrics.record_agent_success(agent_name)
                    
                    return result
            
            return wrapper
        return decorator
    
    def calculate_extraction_accuracy(
        self,
        extracted_clauses: List[Clause],
        expected_clause_count: Optional[int] = None
    ) -> float:
        """Calculate and record extraction accuracy.
        
        Args:
            extracted_clauses: List of extracted clauses
            expected_clause_count: Expected number of clauses (if known)
            
        Returns:
            Accuracy percentage
        """
        if expected_clause_count is None:
            # If we don't have ground truth, use a heuristic
            # Assume accuracy based on clause type diversity
            clause_types = set(c.type for c in extracted_clauses)
            accuracy = min(len(clause_types) * 15, 100)  # 15% per unique type, max 100%
        else:
            accuracy = min(len(extracted_clauses) / expected_clause_count * 100, 100)
        
        if self.enable_metrics and self.metrics:
            self.metrics.record_extraction_accuracy(accuracy)
            self.metrics.record_clause_count(len(extracted_clauses))
        
        return accuracy
    
    def calculate_risk_detection_rate(
        self,
        risk_assessments: List[RiskAssessment]
    ) -> float:
        """Calculate and record risk detection rate.
        
        Args:
            risk_assessments: List of risk assessments
            
        Returns:
            Detection rate (high-risk clauses / total clauses)
        """
        if not risk_assessments:
            return 0.0
        
        high_risk_count = sum(1 for r in risk_assessments if r.severity == "high")
        detection_rate = high_risk_count / len(risk_assessments) * 100
        
        if self.enable_metrics and self.metrics:
            self.metrics.record_risk_detection_rate(detection_rate)
            self.metrics.record_high_risk_count(high_risk_count)
        
        return detection_rate


# Global observability manager instance
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager() -> ObservabilityManager:
    """Get or create the global observability manager.
    
    Returns:
        ObservabilityManager instance
    """
    global _observability_manager
    
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    
    return _observability_manager


def initialize_observability(
    enable_tracing: bool = True,
    enable_metrics: bool = True
) -> ObservabilityManager:
    """Initialize the global observability manager.
    
    Args:
        enable_tracing: Whether to enable tracing
        enable_metrics: Whether to enable metrics collection
        
    Returns:
        ObservabilityManager instance
    """
    global _observability_manager
    
    _observability_manager = ObservabilityManager(
        enable_tracing=enable_tracing,
        enable_metrics=enable_metrics
    )
    
    return _observability_manager
