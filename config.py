"""
Dhan API Configuration
Uses official dhanhq SDK for authentication
"""

import os
from dotenv import load_dotenv
from dhanhq import DhanContext, dhanhq

# Load environment variables from .env file
load_dotenv()

# Dhan API Credentials
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")


def validate_credentials():
    """Check if credentials are configured"""
    if not DHAN_CLIENT_ID or DHAN_CLIENT_ID == "your_client_id_here":
        raise ValueError("DHAN_CLIENT_ID not configured. Please update .env file.")
    if not DHAN_ACCESS_TOKEN or DHAN_ACCESS_TOKEN == "your_access_token_here":
        raise ValueError("DHAN_ACCESS_TOKEN not configured. Please update .env file.")
    return True


def get_dhan_client():
    """Get authenticated Dhan client using official SDK"""
    validate_credentials()
    
    context = DhanContext(
        client_id=DHAN_CLIENT_ID,
        access_token=DHAN_ACCESS_TOKEN
    )
    
    return dhanhq(context)
