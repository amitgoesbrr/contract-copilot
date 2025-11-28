"""A2A Wrapper for Contract Review Orchestrator.

This module exposes the Contract Review Orchestrator as an Agent2Agent (A2A) compliant agent.
It wraps the orchestrator in an LlmAgent and uses the ADK's to_a2a utility to create
a Starlette/FastAPI application that serves the agent and its capabilities.
"""

from typing import Optional, Dict, Any
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.genai import types
from loguru import logger

from adk.orchestrator import ContractReviewOrchestrator

def create_a2a_app(orchestrator: ContractReviewOrchestrator, port: int = 8000):
    """Create an A2A-compliant application for the orchestrator.
    
    Args:
        orchestrator: The ContractReviewOrchestrator instance to expose.
        port: The port where the agent will be served (used for agent card URL).
        
    Returns:
        A Starlette/FastAPI application serving the agent.
    """
    
    def review_contract(file_content: str, filename: str) -> str:
        """Review a contract provided as text content.
        
        Args:
            file_content: The text content of the contract.
            filename: The name of the contract file.
            
        Returns:
            A summary of the review results as a string.
        """
        logger.info(f"A2A Agent received contract: {filename}")
        
        try:
            # Process the contract using the orchestrator
            # We treat the string content as bytes
            result = orchestrator.process_contract(
                file_bytes=file_content.encode('utf-8'),
                filename=filename,
                user_id="a2a_agent_user",
                session_id=None # Let orchestrator generate session ID
            )
            
            if result["status"] == "failed":
                return f"Contract review failed: {result.get('errors', ['Unknown error'])}"
            
            # Format a simple summary for the calling agent
            summary = result.get("results", {}).get("summary", {}).get("negotiation_summary", {})
            risk_count = result.get("results", {}).get("risk_scoring", {}).get("high_risk_count", 0)
            
            output = f"Contract Review Complete for {filename}.\n"
            output += f"Status: {result['status']}\n"
            output += f"High Risks Found: {risk_count}\n"
            
            if summary:
                output += f"\nSummary: {summary.get('executive_summary', 'No summary available')}\n"
            
            return output
            
        except Exception as e:
            logger.error(f"A2A review failed: {e}")
            return f"Error processing contract: {str(e)}"

    # Create the LlmAgent that wraps the tool
    # We use a lightweight model since the heavy lifting is done by the orchestrator
    agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite"),
        name="contract_review_agent",
        description="Agent that reviews contracts for risks, compliance, and negotiation points.",
        instruction="""
        You are a contract review specialist.
        Your primary capability is to review contracts using the review_contract tool.
        When asked to review a contract, you must use the review_contract tool.
        Provide the filename and the full text content of the contract.
        Return the summary provided by the tool.
        """,
        tools=[review_contract]
    )
    
    logger.info("Created A2A Contract Review Agent")
    
    # Convert to A2A app
    # Note: The port here is used for the agent card URL generation
    return to_a2a(agent, port=port)
