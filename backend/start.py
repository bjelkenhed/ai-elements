#!/usr/bin/env python3
"""
Development server launcher for FastAPI backend
Run with: python start.py
"""
import logging
import uvicorn
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Try to activate virtual environment if it exists
venv_path = backend_dir / "venv"
if venv_path.exists():
    activate_script = venv_path / "bin" / "activate"
    if activate_script.exists():
        print(f"Using virtual environment: {venv_path}")
    else:
        print("Virtual environment found but no activate script")
else:
    print("No virtual environment found, using system Python")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting FastAPI development server...")
    logger.info(f"Backend directory: {backend_dir}")

    # Check for .env file
    env_file = backend_dir / ".env"
    if not env_file.exists():
        logger.warning(f".env file not found at {env_file}")
        logger.warning("Please copy .env.example to .env and add your OPENAI_API_KEY")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )