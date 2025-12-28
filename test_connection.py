"""
Test Dhan API Connection
"""

from config import get_dhan_client, DHAN_CLIENT_ID

print("=" * 50)
print("Testing Dhan API Connection")
print("=" * 50)

try:
    print(f"\n[OK] Client ID loaded: {DHAN_CLIENT_ID[:4]}...{DHAN_CLIENT_ID[-4:]}")
    
    # Get authenticated client
    dhan = get_dhan_client()
    print("[OK] Dhan client created successfully")
    
    # Test API - get fund limits (simple API call to verify connection)
    response = dhan.get_fund_limits()
    print(f"[OK] API Response received: {response}")
    
    print("\n" + "=" * 50)
    print("CONNECTION SUCCESSFUL!")
    print("=" * 50)
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nPlease check your .env file credentials.")
