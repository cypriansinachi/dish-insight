#!/usr/bin/env python3
"""
Startup script for the Dish Insight AI API
"""

import uvicorn
import os
from dotenv import load_dotenv

def main():
    """Start the FastAPI application"""
    # Load environment variables
    load_dotenv()
    
    # Check if required environment variables are set
    required_vars = ["GEMINI_API_KEY", "SPEECH_KEY", "ENDPOINT_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
    
    # Start the server
    print("Starting Dish Insight AI API...")
    print("API Documentation available at: http://localhost:8000/docs")
    print("Health check available at: http://localhost:8000/health")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
