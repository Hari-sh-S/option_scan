"""
NIFTY Options Backtester - Global Configuration
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "historical_data" / "NIFTY"

# Trading Constants
LOT_SIZE = 50  # NIFTY lot size
TRADING_START = "09:15"
TRADING_END = "15:30"

# Default Costs
DEFAULT_SLIPPAGE_PCT = 0.05
DEFAULT_BROKERAGE_PER_LOT = 20

# Available Strikes
STRIKES = ["ATM"] + [f"ATM+{i}" for i in range(1, 11)] + [f"ATM-{i}" for i in range(1, 11)]

# Expiry Types
EXPIRY_TYPES = ["WEEK", "MONTH"]

# Option Types
OPTION_TYPES = ["CE", "PE"]
