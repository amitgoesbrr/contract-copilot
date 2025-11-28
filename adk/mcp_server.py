"""MCP Server for Contract Copilot.

This module implements a Model Context Protocol (MCP) server that exposes
contract data (risks, summaries) as resources. This allows other MCP-compliant
tools and agents to access contract insights directly.
"""

import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from loguru import logger

from memory.session_manager import create_session_manager

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("Contract Copilot MCP")

# Initialize session manager
try:
    session_manager = create_session_manager()
    memory_bank = session_manager.get_memory_bank()
    logger.info("MCP Server initialized with session manager")
except Exception as e:
    logger.error(f"Failed to initialize session manager: {e}")
    raise

@mcp.resource("contract://{session_id}/risks")
def get_contract_risks(session_id: str) -> str:
    """Get risk assessments for a contract session.
    
    Args:
        session_id: The session identifier.
        
    Returns:
        Formatted string containing risk assessments.
    """
    try:
        risks = memory_bank.get_risk_assessments(session_id)
        if not risks:
            return f"No risk assessments found for session {session_id}."
        
        output = f"# Risk Assessments for Session {session_id}\n\n"
        
        # Group by severity
        high_risks = [r for r in risks if r.severity == "high"]
        medium_risks = [r for r in risks if r.severity == "medium"]
        low_risks = [r for r in risks if r.severity == "low"]
        
        if high_risks:
            output += "## 🔴 High Risks\n"
            for risk in high_risks:
                output += f"### {risk.risk_type}\n"
                output += f"{risk.explanation}\n\n"
        
        if medium_risks:
            output += "## 🟡 Medium Risks\n"
            for risk in medium_risks:
                output += f"### {risk.risk_type}\n"
                output += f"{risk.explanation}\n\n"
                
        if low_risks:
            output += "## 🟢 Low Risks\n"
            for risk in low_risks:
                output += f"### {risk.risk_type}\n"
                output += f"{risk.explanation}\n\n"
                
        return output
        
    except Exception as e:
        logger.error(f"Error retrieving risks for {session_id}: {e}")
        return f"Error retrieving risks: {str(e)}"

@mcp.resource("contract://{session_id}/summary")
def get_contract_summary(session_id: str) -> str:
    """Get negotiation summary for a contract session.
    
    Args:
        session_id: The session identifier.
        
    Returns:
        The executive summary of the negotiation.
    """
    try:
        summary = memory_bank.get_negotiation_summary(session_id)
        if not summary:
            return f"No negotiation summary found for session {session_id}."
        
        return f"# Negotiation Summary\n\n{summary.executive_summary}"
        
    except Exception as e:
        logger.error(f"Error retrieving summary for {session_id}: {e}")
        return f"Error retrieving summary: {str(e)}"

@mcp.resource("contract://{session_id}/clauses")
def get_contract_clauses(session_id: str) -> str:
    """Get extracted clauses for a contract session.
    
    Args:
        session_id: The session identifier.
        
    Returns:
        Formatted string of extracted clauses.
    """
    try:
        clauses = memory_bank.get_clauses(session_id)
        if not clauses:
            return f"No clauses found for session {session_id}."
        
        output = f"# Extracted Clauses for Session {session_id}\n\n"
        for clause in clauses:
            output += f"## {clause.type.title()} (ID: {clause.id})\n"
            output += f"{clause.text}\n\n"
            
        return output
        
    except Exception as e:
        logger.error(f"Error retrieving clauses for {session_id}: {e}")
        return f"Error retrieving clauses: {str(e)}"

if __name__ == "__main__":
    mcp.run()
