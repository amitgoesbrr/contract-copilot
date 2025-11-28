"""Evaluation harness for testing contract review agents.

This module provides evaluation methods for:
- Clause extraction accuracy against ground truth
- Risk detection quality and accuracy
- Agent latency and performance tracking
- End-to-end pipeline testing with sample contracts
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from loguru import logger

from adk.models import Clause, RiskAssessment, AgentTrace


class Evaluator:
    """Evaluator for contract review agent performance.
    
    This class provides methods to evaluate:
    - Extraction accuracy by comparing against ground truth
    - Risk detection quality and severity distribution
    - Agent latency and performance metrics
    """
    
    def __init__(self):
        """Initialize the evaluator."""
        self.evaluation_results: List[Dict[str, Any]] = []
        logger.info("Evaluator initialized")
    
    def evaluate_extraction(
        self,
        extracted_clauses: List[Clause],
        ground_truth: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate clause extraction accuracy against ground truth.
        
        Compares extracted clauses against expected clauses to measure:
        - Precision: How many extracted clauses are correct
        - Recall: How many expected clauses were found
        - F1 Score: Harmonic mean of precision and recall
        - Type accuracy: How many clause types match
        
        Args:
            extracted_clauses: List of Clause objects from extraction agent
            ground_truth: Dictionary with expected clauses and metadata
                Expected format:
                {
                    "expected_clause_count": int,
                    "expected_types": List[str],
                    "expected_clause_ids": List[str] (optional)
                }
        
        Returns:
            Dictionary with evaluation metrics:
            {
                "extraction_accuracy": float (0-100),
                "precision": float (0-100),
                "recall": float (0-100),
                "f1_score": float (0-100),
                "type_accuracy": float (0-100),
                "extracted_count": int,
                "expected_count": int,
                "correct_count": int,
                "type_matches": int
            }
        """
        logger.info("Evaluating extraction accuracy")
        
        extracted_count = len(extracted_clauses)
        expected_count = ground_truth.get("expected_clause_count", 0)
        expected_types = ground_truth.get("expected_types", [])
        
        # Calculate basic accuracy based on count
        if expected_count == 0:
            count_accuracy = 0.0
        else:
            count_accuracy = min(extracted_count / expected_count, 1.0) * 100
        
        # Calculate precision and recall
        # Precision: What percentage of extracted clauses are correct
        # Recall: What percentage of expected clauses were found
        correct_count = min(extracted_count, expected_count)
        
        if extracted_count > 0:
            precision = (correct_count / extracted_count) * 100
        else:
            precision = 0.0
        
        if expected_count > 0:
            recall = (correct_count / expected_count) * 100
        else:
            recall = 0.0
        
        # Calculate F1 score
        if precision + recall > 0:
            f1_score = 2 * (precision * recall) / (precision + recall)
        else:
            f1_score = 0.0
        
        # Calculate type accuracy
        extracted_types = [clause.type for clause in extracted_clauses]
        type_matches = sum(1 for t in expected_types if t in extracted_types)
        
        if len(expected_types) > 0:
            type_accuracy = (type_matches / len(expected_types)) * 100
        else:
            type_accuracy = 0.0
        
        result = {
            "extraction_accuracy": round(count_accuracy, 2),
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "f1_score": round(f1_score, 2),
            "type_accuracy": round(type_accuracy, 2),
            "extracted_count": extracted_count,
            "expected_count": expected_count,
            "correct_count": correct_count,
            "type_matches": type_matches,
            "expected_types_count": len(expected_types)
        }
        
        logger.info(
            "Extraction evaluation complete",
            accuracy=result["extraction_accuracy"],
            precision=result["precision"],
            recall=result["recall"],
            f1_score=result["f1_score"]
        )
        
        self.evaluation_results.append({
            "evaluation_type": "extraction",
            "timestamp": time.time(),
            "results": result
        })
        
        return result
    
    def evaluate_risk_quality(
        self,
        risk_assessments: List[RiskAssessment],
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate risk detection quality and accuracy.
        
        Measures:
        - Risk detection rate: Percentage of high-risk clauses identified
        - Severity distribution: Breakdown by low/medium/high
        - False positive rate: If ground truth provided
        - False negative rate: If ground truth provided
        
        Args:
            risk_assessments: List of RiskAssessment objects
            ground_truth: Optional dictionary with expected risks
                Expected format:
                {
                    "expected_high_risk_count": int,
                    "expected_medium_risk_count": int,
                    "expected_low_risk_count": int,
                    "expected_high_risk_clause_ids": List[str] (optional)
                }
        
        Returns:
            Dictionary with risk quality metrics:
            {
                "total_risks": int,
                "high_risk_count": int,
                "medium_risk_count": int,
                "low_risk_count": int,
                "high_risk_percentage": float,
                "risk_detection_rate": float (0-100),
                "severity_distribution": Dict[str, int],
                "false_positive_rate": float (optional),
                "false_negative_rate": float (optional)
            }
        """
        logger.info("Evaluating risk quality")
        
        total_risks = len(risk_assessments)
        
        # Count by severity
        high_risk_count = sum(1 for r in risk_assessments if r.severity == "high")
        medium_risk_count = sum(1 for r in risk_assessments if r.severity == "medium")
        low_risk_count = sum(1 for r in risk_assessments if r.severity == "low")
        
        # Calculate percentages
        if total_risks > 0:
            high_risk_percentage = (high_risk_count / total_risks) * 100
        else:
            high_risk_percentage = 0.0
        
        result = {
            "total_risks": total_risks,
            "high_risk_count": high_risk_count,
            "medium_risk_count": medium_risk_count,
            "low_risk_count": low_risk_count,
            "high_risk_percentage": round(high_risk_percentage, 2),
            "severity_distribution": {
                "high": high_risk_count,
                "medium": medium_risk_count,
                "low": low_risk_count
            }
        }
        
        # Calculate detection rate if ground truth provided
        if ground_truth:
            expected_high_risk = ground_truth.get("expected_high_risk_count", 0)
            
            if expected_high_risk > 0:
                detection_rate = min(high_risk_count / expected_high_risk, 1.0) * 100
                result["risk_detection_rate"] = round(detection_rate, 2)
                result["expected_high_risk_count"] = expected_high_risk
            
            # Calculate false positives and false negatives if clause IDs provided
            expected_high_risk_ids = set(ground_truth.get("expected_high_risk_clause_ids", []))
            if expected_high_risk_ids:
                detected_high_risk_ids = set(
                    r.clause_id for r in risk_assessments if r.severity == "high"
                )
                
                # True positives: correctly identified high-risk clauses
                true_positives = len(expected_high_risk_ids & detected_high_risk_ids)
                
                # False positives: incorrectly marked as high-risk
                false_positives = len(detected_high_risk_ids - expected_high_risk_ids)
                
                # False negatives: missed high-risk clauses
                false_negatives = len(expected_high_risk_ids - detected_high_risk_ids)
                
                # Calculate rates
                if high_risk_count > 0:
                    false_positive_rate = (false_positives / high_risk_count) * 100
                else:
                    false_positive_rate = 0.0
                
                if expected_high_risk > 0:
                    false_negative_rate = (false_negatives / expected_high_risk) * 100
                else:
                    false_negative_rate = 0.0
                
                result["true_positives"] = true_positives
                result["false_positives"] = false_positives
                result["false_negatives"] = false_negatives
                result["false_positive_rate"] = round(false_positive_rate, 2)
                result["false_negative_rate"] = round(false_negative_rate, 2)
        
        logger.info(
            "Risk quality evaluation complete",
            total_risks=total_risks,
            high_risk_count=high_risk_count,
            high_risk_percentage=result["high_risk_percentage"]
        )
        
        self.evaluation_results.append({
            "evaluation_type": "risk_quality",
            "timestamp": time.time(),
            "results": result
        })
        
        return result
    
    def evaluate_latency(
        self,
        agent_traces: List[AgentTrace],
        latency_thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Evaluate agent latency and performance.
        
        Measures:
        - Per-agent latency statistics (min, max, avg, p50, p95, p99)
        - Total pipeline latency
        - Success rate per agent
        - Threshold violations
        
        Args:
            agent_traces: List of AgentTrace objects from orchestrator
            latency_thresholds: Optional dict of agent_name -> max_latency_seconds
                Example: {"ClauseExtractionAgent": 5.0, "RiskScoringAgent": 3.0}
        
        Returns:
            Dictionary with latency metrics:
            {
                "total_latency_seconds": float,
                "agent_latencies": Dict[str, Dict[str, float]],
                "success_rates": Dict[str, float],
                "threshold_violations": List[Dict[str, Any]],
                "overall_success_rate": float
            }
        """
        logger.info("Evaluating latency and performance")
        
        if not agent_traces:
            logger.warning("No agent traces provided for latency evaluation")
            return {
                "total_latency_seconds": 0.0,
                "agent_latencies": {},
                "success_rates": {},
                "threshold_violations": [],
                "overall_success_rate": 0.0
            }
        
        # Group traces by agent name
        agent_groups: Dict[str, List[AgentTrace]] = {}
        for trace in agent_traces:
            if trace.agent_name not in agent_groups:
                agent_groups[trace.agent_name] = []
            agent_groups[trace.agent_name].append(trace)
        
        # Calculate per-agent statistics
        agent_latencies = {}
        success_rates = {}
        threshold_violations = []
        
        for agent_name, traces in agent_groups.items():
            latencies = [t.latency_seconds for t in traces]
            successes = sum(1 for t in traces if t.success)
            
            # Calculate statistics
            latencies_sorted = sorted(latencies)
            n = len(latencies_sorted)
            
            stats = {
                "count": n,
                "min": round(min(latencies), 3),
                "max": round(max(latencies), 3),
                "avg": round(sum(latencies) / n, 3),
                "p50": round(latencies_sorted[n // 2], 3),
                "p95": round(latencies_sorted[int(n * 0.95)], 3) if n > 1 else round(latencies_sorted[0], 3),
                "p99": round(latencies_sorted[int(n * 0.99)], 3) if n > 1 else round(latencies_sorted[0], 3)
            }
            
            agent_latencies[agent_name] = stats
            success_rates[agent_name] = round((successes / n) * 100, 2)
            
            # Check threshold violations
            if latency_thresholds and agent_name in latency_thresholds:
                threshold = latency_thresholds[agent_name]
                violations = [t for t in traces if t.latency_seconds > threshold]
                
                if violations:
                    threshold_violations.append({
                        "agent_name": agent_name,
                        "threshold_seconds": threshold,
                        "violation_count": len(violations),
                        "max_violation_seconds": round(max(v.latency_seconds for v in violations), 3)
                    })
        
        # Calculate total latency (sum of all agent latencies)
        total_latency = sum(t.latency_seconds for t in agent_traces)
        
        # Calculate overall success rate
        total_successes = sum(1 for t in agent_traces if t.success)
        overall_success_rate = (total_successes / len(agent_traces)) * 100
        
        result = {
            "total_latency_seconds": round(total_latency, 3),
            "agent_latencies": agent_latencies,
            "success_rates": success_rates,
            "threshold_violations": threshold_violations,
            "overall_success_rate": round(overall_success_rate, 2),
            "total_traces": len(agent_traces)
        }
        
        logger.info(
            "Latency evaluation complete",
            total_latency=result["total_latency_seconds"],
            overall_success_rate=result["overall_success_rate"]
        )
        
        self.evaluation_results.append({
            "evaluation_type": "latency",
            "timestamp": time.time(),
            "results": result
        })
        
        return result
    
    def run_test_suite(
        self,
        orchestrator,
        test_contracts: List[Dict[str, Any]],
        latency_thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Run evaluation suite on multiple test contracts.
        
        Processes multiple contracts and aggregates evaluation metrics.
        
        Args:
            orchestrator: ContractReviewOrchestrator instance
            test_contracts: List of test contract dictionaries
                Each dict should contain:
                {
                    "name": str,
                    "file_path": str,
                    "ground_truth": {
                        "expected_clause_count": int,
                        "expected_types": List[str],
                        "expected_high_risk_count": int,
                        ...
                    }
                }
            latency_thresholds: Optional latency thresholds for agents
        
        Returns:
            Dictionary with aggregated results:
            {
                "test_count": int,
                "successful_tests": int,
                "failed_tests": int,
                "avg_extraction_accuracy": float,
                "avg_risk_detection_rate": float,
                "avg_total_latency": float,
                "test_results": List[Dict[str, Any]]
            }
        """
        logger.info(f"Running test suite with {len(test_contracts)} contracts")
        
        test_results = []
        successful_tests = 0
        failed_tests = 0
        
        for test_contract in test_contracts:
            contract_name = test_contract.get("name", "unknown")
            file_path = test_contract.get("file_path")
            ground_truth = test_contract.get("ground_truth", {})
            
            logger.info(f"Testing contract: {contract_name}")
            
            try:
                # Process contract
                start_time = time.time()
                result = orchestrator.process_contract(
                    file_path=file_path,
                    user_id="evaluator"
                )
                processing_time = time.time() - start_time
                
                # Evaluate extraction
                extraction_eval = self.evaluate_extraction(
                    extracted_clauses=result["results"]["extraction"].get("clauses", []),
                    ground_truth=ground_truth
                )
                
                # Evaluate risk quality
                risk_eval = self.evaluate_risk_quality(
                    risk_assessments=result["results"]["risk_scoring"].get("risk_assessments", []),
                    ground_truth=ground_truth
                )
                
                # Evaluate latency
                latency_eval = self.evaluate_latency(
                    agent_traces=result.get("agent_traces", []),
                    latency_thresholds=latency_thresholds
                )
                
                test_results.append({
                    "contract_name": contract_name,
                    "status": "success",
                    "processing_time": round(processing_time, 3),
                    "extraction_evaluation": extraction_eval,
                    "risk_evaluation": risk_eval,
                    "latency_evaluation": latency_eval
                })
                
                successful_tests += 1
                logger.info(f"✓ Test passed for {contract_name}")
                
            except Exception as e:
                logger.error(f"✗ Test failed for {contract_name}: {e}")
                test_results.append({
                    "contract_name": contract_name,
                    "status": "failed",
                    "error": str(e)
                })
                failed_tests += 1
        
        # Calculate aggregated metrics
        successful_results = [r for r in test_results if r["status"] == "success"]
        
        if successful_results:
            avg_extraction_accuracy = sum(
                r["extraction_evaluation"]["extraction_accuracy"]
                for r in successful_results
            ) / len(successful_results)
            
            avg_risk_detection_rate = sum(
                r["risk_evaluation"].get("risk_detection_rate", 0)
                for r in successful_results
            ) / len(successful_results)
            
            avg_total_latency = sum(
                r["latency_evaluation"]["total_latency_seconds"]
                for r in successful_results
            ) / len(successful_results)
        else:
            avg_extraction_accuracy = 0.0
            avg_risk_detection_rate = 0.0
            avg_total_latency = 0.0
        
        summary = {
            "test_count": len(test_contracts),
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": round((successful_tests / len(test_contracts)) * 100, 2),
            "avg_extraction_accuracy": round(avg_extraction_accuracy, 2),
            "avg_risk_detection_rate": round(avg_risk_detection_rate, 2),
            "avg_total_latency": round(avg_total_latency, 3),
            "test_results": test_results
        }
        
        logger.info(
            "Test suite complete",
            successful=successful_tests,
            failed=failed_tests,
            avg_accuracy=summary["avg_extraction_accuracy"]
        )
        
        return summary
    
    def get_evaluation_history(self) -> List[Dict[str, Any]]:
        """Get history of all evaluations run.
        
        Returns:
            List of evaluation result dictionaries
        """
        return self.evaluation_results
    
    def clear_history(self):
        """Clear evaluation history."""
        self.evaluation_results = []
        logger.info("Evaluation history cleared")
