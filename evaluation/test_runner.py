"""Test runner for evaluating contract review agents with sample contracts.

This script demonstrates how to use the Evaluator class to test
the contract review pipeline with sample contracts and ground truth data.
"""

import os
from pathlib import Path
from loguru import logger

from evaluation.evaluator import Evaluator
from adk.orchestrator import create_orchestrator


def get_sample_contracts() -> list:
    """Get list of sample contracts with ground truth data.
    
    Returns:
        List of test contract dictionaries with ground truth
    """
    sample_contracts_dir = Path("sample_contracts")
    
    # Define test contracts with expected ground truth
    test_contracts = []
    
    # Sample NDA
    nda_path = sample_contracts_dir / "sample_nda.md"
    if nda_path.exists():
        test_contracts.append({
            "name": "Sample NDA",
            "file_path": str(nda_path),
            "ground_truth": {
                "expected_clause_count": 8,
                "expected_types": [
                    "confidentiality",
                    "termination",
                    "governing law",
                    "liability"
                ],
                "expected_high_risk_count": 2,
                "expected_medium_risk_count": 3,
                "expected_low_risk_count": 3
            }
        })
    
    # Sample MSA
    msa_path = sample_contracts_dir / "sample_msa.md"
    if msa_path.exists():
        test_contracts.append({
            "name": "Sample MSA",
            "file_path": str(msa_path),
            "ground_truth": {
                "expected_clause_count": 12,
                "expected_types": [
                    "payment terms",
                    "liability",
                    "indemnification",
                    "termination",
                    "governing law"
                ],
                "expected_high_risk_count": 3,
                "expected_medium_risk_count": 5,
                "expected_low_risk_count": 4
            }
        })
    
    # Sample SLA
    sla_path = sample_contracts_dir / "sample_sla.md"
    if sla_path.exists():
        test_contracts.append({
            "name": "Sample SLA",
            "file_path": str(sla_path),
            "ground_truth": {
                "expected_clause_count": 10,
                "expected_types": [
                    "termination",
                    "liability",
                    "payment terms"
                ],
                "expected_high_risk_count": 2,
                "expected_medium_risk_count": 4,
                "expected_low_risk_count": 4
            }
        })
    
    return test_contracts


def run_evaluation_suite():
    """Run the complete evaluation suite on sample contracts."""
    logger.info("Starting evaluation suite")
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY environment variable not set")
        print("Error: GOOGLE_API_KEY environment variable is required")
        return
    
    # Get sample contracts
    test_contracts = get_sample_contracts()
    
    if not test_contracts:
        logger.warning("No sample contracts found in sample_contracts/ directory")
        print("Warning: No sample contracts found. Please add sample contracts to test.")
        print("Expected files: sample_nda.md, sample_msa.md, sample_sla.md")
        return
    
    print(f"\nFound {len(test_contracts)} test contracts:")
    for contract in test_contracts:
        print(f"  - {contract['name']}")
    
    # Initialize orchestrator
    print("\nInitializing orchestrator...")
    try:
        orchestrator = create_orchestrator(
            enable_graceful_degradation=True,
            enable_observability=True
        )
        print("✓ Orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        print(f"Error: Failed to initialize orchestrator: {e}")
        return
    
    # Initialize evaluator
    evaluator = Evaluator()
    
    # Define latency thresholds (in seconds)
    latency_thresholds = {
        "IngestionAgent": 5.0,
        "ClauseExtractionAgent": 5.0,
        "RiskScoringAgent": 5.0,
        "RedlineSuggestionAgent": 5.0,
        "NegotiationSummaryAgent": 5.0,
        "ComplianceAuditAgent": 3.0
    }
    
    # Run test suite
    print("\nRunning evaluation suite...")
    print("=" * 60)
    
    try:
        results = evaluator.run_test_suite(
            orchestrator=orchestrator,
            test_contracts=test_contracts,
            latency_thresholds=latency_thresholds
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("EVALUATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {results['test_count']}")
        print(f"Successful: {results['successful_tests']}")
        print(f"Failed: {results['failed_tests']}")
        print(f"Success Rate: {results['success_rate']}%")
        print()
        print(f"Average Extraction Accuracy: {results['avg_extraction_accuracy']}%")
        print(f"Average Risk Detection Rate: {results['avg_risk_detection_rate']}%")
        print(f"Average Total Latency: {results['avg_total_latency']}s")
        print("=" * 60)
        
        # Print detailed results for each test
        print("\nDETAILED RESULTS")
        print("=" * 60)
        
        for test_result in results['test_results']:
            print(f"\n{test_result['contract_name']}:")
            print(f"  Status: {test_result['status']}")
            
            if test_result['status'] == 'success':
                extraction = test_result['extraction_evaluation']
                risk = test_result['risk_evaluation']
                latency = test_result['latency_evaluation']
                
                print(f"  Processing Time: {test_result['processing_time']}s")
                print()
                print(f"  Extraction Metrics:")
                print(f"    - Accuracy: {extraction['extraction_accuracy']}%")
                print(f"    - Precision: {extraction['precision']}%")
                print(f"    - Recall: {extraction['recall']}%")
                print(f"    - F1 Score: {extraction['f1_score']}%")
                print(f"    - Extracted: {extraction['extracted_count']} clauses")
                print(f"    - Expected: {extraction['expected_count']} clauses")
                print()
                print(f"  Risk Metrics:")
                print(f"    - Total Risks: {risk['total_risks']}")
                print(f"    - High Risk: {risk['high_risk_count']}")
                print(f"    - Medium Risk: {risk['medium_risk_count']}")
                print(f"    - Low Risk: {risk['low_risk_count']}")
                if 'risk_detection_rate' in risk:
                    print(f"    - Detection Rate: {risk['risk_detection_rate']}%")
                print()
                print(f"  Latency Metrics:")
                print(f"    - Total Latency: {latency['total_latency_seconds']}s")
                print(f"    - Success Rate: {latency['overall_success_rate']}%")
                
                if latency['threshold_violations']:
                    print(f"    - Threshold Violations:")
                    for violation in latency['threshold_violations']:
                        print(f"      * {violation['agent_name']}: {violation['violation_count']} violations")
                else:
                    print(f"    - No threshold violations")
            else:
                print(f"  Error: {test_result.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 60)
        logger.info("Evaluation suite completed successfully")
        
    except Exception as e:
        logger.error(f"Evaluation suite failed: {e}")
        print(f"\nError: Evaluation suite failed: {e}")
        import traceback
        traceback.print_exc()


def run_single_contract_evaluation(file_path: str):
    """Run evaluation on a single contract file.
    
    Args:
        file_path: Path to contract file
    """
    logger.info(f"Evaluating single contract: {file_path}")
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY environment variable not set")
        print("Error: GOOGLE_API_KEY environment variable is required")
        return
    
    # Initialize orchestrator
    print("Initializing orchestrator...")
    try:
        orchestrator = create_orchestrator()
        print("✓ Orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        print(f"Error: Failed to initialize orchestrator: {e}")
        return
    
    # Process contract
    print(f"\nProcessing contract: {file_path}")
    try:
        result = orchestrator.process_contract(
            file_path=file_path,
            user_id="evaluator"
        )
        
        # Initialize evaluator
        evaluator = Evaluator()
        
        # Evaluate extraction (without ground truth)
        extraction_eval = evaluator.evaluate_extraction(
            extracted_clauses=result["results"]["extraction"].get("clauses", []),
            ground_truth={"expected_clause_count": 0}  # No ground truth
        )
        
        # Evaluate risk quality
        risk_eval = evaluator.evaluate_risk_quality(
            risk_assessments=result["results"]["risk_scoring"].get("risk_assessments", [])
        )
        
        # Evaluate latency
        latency_eval = evaluator.evaluate_latency(
            agent_traces=result.get("agent_traces", [])
        )
        
        # Print results
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"\nExtraction:")
        print(f"  - Extracted Clauses: {extraction_eval['extracted_count']}")
        print(f"\nRisk Assessment:")
        print(f"  - Total Risks: {risk_eval['total_risks']}")
        print(f"  - High Risk: {risk_eval['high_risk_count']}")
        print(f"  - Medium Risk: {risk_eval['medium_risk_count']}")
        print(f"  - Low Risk: {risk_eval['low_risk_count']}")
        print(f"\nLatency:")
        print(f"  - Total Latency: {latency_eval['total_latency_seconds']}s")
        print(f"  - Success Rate: {latency_eval['overall_success_rate']}%")
        print("\nAgent Latencies:")
        for agent_name, stats in latency_eval['agent_latencies'].items():
            print(f"  - {agent_name}:")
            print(f"    * Avg: {stats['avg']}s")
            print(f"    * Min: {stats['min']}s")
            print(f"    * Max: {stats['max']}s")
        print("=" * 60)
        
        logger.info("Single contract evaluation completed")
        
    except Exception as e:
        logger.error(f"Contract evaluation failed: {e}")
        print(f"\nError: Contract evaluation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Run single contract evaluation
        contract_path = sys.argv[1]
        run_single_contract_evaluation(contract_path)
    else:
        # Run full evaluation suite
        run_evaluation_suite()
