"""
Instrument Resolver - Maps strategy intent to data files
"""

from pathlib import Path
from typing import List, Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR, STRIKES, EXPIRY_TYPES, OPTION_TYPES


class InstrumentResolver:
    """Maps strategy intent to correct parquet files"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self._validate_data_dir()
    
    def _validate_data_dir(self):
        """Check data directory exists"""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
    
    def resolve(self, strike: str, option_type: str, 
                expiry_type: str) -> str:
        """
        Resolve instrument parameters to filename
        
        Args:
            strike: 'ATM', 'ATM+1', 'ATM-5', etc.
            option_type: 'CE' or 'PE'
            expiry_type: 'WEEK' or 'MONTH'
        
        Returns:
            Filename like 'ATM+1_CE.parquet'
        """
        # Validate inputs
        if strike not in STRIKES:
            raise ValueError(f"Invalid strike: {strike}. Must be one of {STRIKES}")
        
        if option_type not in OPTION_TYPES:
            raise ValueError(f"Invalid option type: {option_type}. Must be CE or PE")
        
        if expiry_type not in EXPIRY_TYPES:
            raise ValueError(f"Invalid expiry: {expiry_type}. Must be WEEK or MONTH")
        
        return f"{strike}_{option_type}.parquet"
    
    def get_file_path(self, strike: str, option_type: str, 
                      expiry_type: str) -> Path:
        """Get full path to parquet file"""
        filename = self.resolve(strike, option_type, expiry_type)
        return self.data_dir / expiry_type / filename
    
    def file_exists(self, strike: str, option_type: str, 
                    expiry_type: str) -> bool:
        """Check if data file exists"""
        return self.get_file_path(strike, option_type, expiry_type).exists()
    
    def get_available_strikes(self) -> List[str]:
        """Return list of available strikes"""
        return STRIKES.copy()
    
    def get_available_files(self, expiry_type: str) -> List[str]:
        """List all available parquet files for an expiry type"""
        folder = self.data_dir / expiry_type
        if not folder.exists():
            return []
        return [f.name for f in folder.glob("*.parquet")]
    
    @staticmethod
    def parse_strike(strike_str: str) -> tuple:
        """
        Parse strike string into components
        
        Args:
            strike_str: 'ATM', 'ATM+5', 'ATM-3'
        
        Returns:
            (base, offset): ('ATM', 0), ('ATM', 5), ('ATM', -3)
        """
        if strike_str == "ATM":
            return ("ATM", 0)
        elif "+" in strike_str:
            offset = int(strike_str.split("+")[1])
            return ("ATM", offset)
        elif "-" in strike_str:
            offset = -int(strike_str.split("-")[1])
            return ("ATM", offset)
        else:
            raise ValueError(f"Cannot parse strike: {strike_str}")
