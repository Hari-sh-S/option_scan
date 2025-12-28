"""
NIFTY Options Rolling Data Downloader
Downloads expired options data from Dhan API and saves as Parquet files
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import get_dhan_client, DHAN_ACCESS_TOKEN, DHAN_CLIENT_ID

# Unbuffered print
def log(msg):
    print(msg, flush=True)

# API Configuration
API_URL = "https://api.dhan.co/v2/charts/rollingoption"

# NIFTY Configuration
SECURITY_ID = 13  # NIFTY
INSTRUMENT = "OPTIDX"
EXCHANGE_SEGMENT = "NSE_FNO"

# Strikes to download
STRIKES = ["ATM"] + [f"ATM+{i}" for i in range(1, 11)] + [f"ATM-{i}" for i in range(1, 11)]

# Data fields to request
REQUIRED_DATA = ["open", "high", "low", "close", "iv", "volume", "oi", "strike", "spot"]

# Output directory
OUTPUT_DIR = "historical_data"


def get_headers():
    """Get API headers"""
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def download_rolling_data(from_date, to_date, expiry_flag, strike, option_type):
    """
    Download rolling options data for a specific configuration
    
    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        expiry_flag: "WEEK" or "MONTH"
        strike: e.g., "ATM", "ATM+1", "ATM-1"
        option_type: "CALL" or "PUT"
    
    Returns:
        DataFrame with options data or None if error
    """
    payload = {
        "exchangeSegment": EXCHANGE_SEGMENT,
        "interval": "1",  # 1-minute data
        "securityId": SECURITY_ID,
        "instrument": INSTRUMENT,
        "expiryFlag": expiry_flag,
        "expiryCode": 1,  # Current expiry
        "strike": strike,
        "drvOptionType": option_type,
        "requiredData": REQUIRED_DATA,
        "fromDate": from_date,
        "toDate": to_date
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=get_headers(), timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == "error":
            log(f"  [WARN] API error: {data.get('remarks', 'Unknown error')}")
            return None
        
        # Extract data based on option type
        key = "ce" if option_type == "CALL" else "pe"
        option_data = data.get("data", {}).get(key)
        
        if not option_data or not option_data.get("timestamp"):
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame({
            "timestamp": option_data.get("timestamp", []),
            "open": option_data.get("open", []),
            "high": option_data.get("high", []),
            "low": option_data.get("low", []),
            "close": option_data.get("close", []),
            "iv": option_data.get("iv", []),
            "volume": option_data.get("volume", []),
            "oi": option_data.get("oi", []),
            "strike_price": option_data.get("strike", []),
            "spot": option_data.get("spot", [])
        })
        
        # Convert timestamp to datetime
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        df["date"] = df["datetime"].dt.date
        
        # Add metadata columns
        df["expiry_type"] = expiry_flag
        df["strike_type"] = strike
        df["option_type"] = option_type
        
        return df
        
    except requests.exceptions.RequestException as e:
        log(f"  [ERROR] Request failed: {e}")
        return None
    except Exception as e:
        log(f"  [ERROR] Unexpected error: {e}")
        return None


def generate_date_ranges(start_date, end_date, chunk_days=30):
    """Generate date ranges in chunks (API limit is 30 days per call)"""
    ranges = []
    current = start_date
    
    while current < end_date:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
        ranges.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)
    
    return ranges


def save_to_parquet(df, expiry_flag, option_type, strike):
    """Save DataFrame to parquet file"""
    if df is None or df.empty:
        return
    
    # Create directory structure
    dir_path = os.path.join(OUTPUT_DIR, "NIFTY", expiry_flag, option_type, strike.replace("+", "plus").replace("-", "minus"))
    os.makedirs(dir_path, exist_ok=True)
    
    # Generate filename based on date range
    min_date = df["date"].min().strftime("%Y%m%d")
    max_date = df["date"].max().strftime("%Y%m%d")
    filename = f"{min_date}_{max_date}.parquet"
    
    filepath = os.path.join(dir_path, filename)
    df.to_parquet(filepath, index=False)
    
    return filepath


def download_all(start_date, end_date, expiry_flags=None):
    """
    Download all NIFTY options data
    
    Args:
        start_date: datetime object
        end_date: datetime object
        expiry_flags: List of expiry types ["WEEK", "MONTH"] or None for both
    """
    if expiry_flags is None:
        expiry_flags = ["WEEK", "MONTH"]
    
    option_types = ["CALL", "PUT"]
    date_ranges = generate_date_ranges(start_date, end_date)
    
    total_tasks = len(expiry_flags) * len(option_types) * len(STRIKES) * len(date_ranges)
    completed = 0
    
    log("=" * 60)
    log("NIFTY Options Rolling Data Downloader")
    log("=" * 60)
    log(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    log(f"Expiry types: {expiry_flags}")
    log(f"Strikes: {len(STRIKES)} (ATM +/- 10)")
    log(f"Total API calls: {total_tasks}")
    log("=" * 60)
    
    for expiry_flag in expiry_flags:
        log(f"\n[{expiry_flag}] Starting download...")
        
        for option_type in option_types:
            for strike in STRIKES:
                # Check if already downloaded (for resume)
                check_dir = os.path.join(OUTPUT_DIR, "NIFTY", expiry_flag, option_type, strike.replace("+", "plus").replace("-", "minus"))
                if os.path.exists(check_dir) and any(f.endswith('.parquet') for f in os.listdir(check_dir)):
                    log(f"  [SKIP] {expiry_flag} {option_type} {strike} - already downloaded")
                    completed += len(date_ranges)
                    continue
                
                all_data = []
                
                for from_date, to_date in date_ranges:
                    completed += 1
                    progress = (completed / total_tasks) * 100
                    
                    log(f"  [{progress:5.1f}%] {expiry_flag} {option_type} {strike:6} | {from_date} to {to_date}")
                    
                    df = download_rolling_data(from_date, to_date, expiry_flag, strike, option_type)
                    
                    if df is not None and not df.empty:
                        all_data.append(df)
                        log(f"         -> {len(df)} rows")
                    else:
                        log(f"         -> No data")
                    
                    # Rate limiting - 1 request per second
                    time.sleep(1)
                
                # Combine and save all data for this strike
                if all_data:
                    combined_df = pd.concat(all_data, ignore_index=True)
                    filepath = save_to_parquet(combined_df, expiry_flag, option_type, strike)
                    if filepath:
                        log(f"  [SAVED] {filepath} ({len(combined_df)} rows)")
    
    log("\n" + "=" * 60)
    log("Download complete!")
    log("=" * 60)


def test_download():
    """Test download with a small date range"""
    log("Running test download (1 month, ATM only)...")
    
    # Test with 1 month of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    df = download_rolling_data(
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "MONTH",
        "ATM",
        "CALL"
    )
    
    if df is not None and not df.empty:
        log(f"[OK] Test successful! Retrieved {len(df)} rows")
        log(f"[OK] Columns: {list(df.columns)}")
        log(f"[OK] Date range: {df['date'].min()} to {df['date'].max()}")
        
        # Save test file
        filepath = save_to_parquet(df, "MONTH", "CALL", "ATM")
        log(f"[OK] Saved to: {filepath}")
        return True
    else:
        log("[ERROR] Test failed - no data returned")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_download()
    else:
        # Download 5 years of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5*365)
        
        # Download weekly and monthly separately
        download_all(start_date, end_date, expiry_flags=["WEEK", "MONTH"])
