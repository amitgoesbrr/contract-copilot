"""Startup script for the FastAPI backend.

This script starts the FastAPI server with configuration from environment variables.
"""

import os
import uvicorn
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()
os.environ["SESSION_PERSISTENCE"] = "true"

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    logger.info(f"Starting AI Contract Reviewer API on {host}:{port}")
    logger.info(f"CORS origins: {os.getenv('CORS_ORIGINS', 'http://localhost:3000')}")
    logger.info(f"Session persistence: {os.getenv('SESSION_PERSISTENCE', 'false')}")
    
    # Start server
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )
