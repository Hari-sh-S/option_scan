"""
Data Loader - Parquet reader with caching and slicing
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, time
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR


class DataLoader:
    """Cached parquet reader with date/time slicing"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or DATA_DIR
        self._cache: Dict[str, pd.DataFrame] = {}
    
    def _get_file_path(self, strike: str, option_type: str, expiry_type: str) -> Path:
        """Get parquet file path for given parameters"""
        filename = f"{strike}_{option_type}.parquet"
        return self.data_dir / expiry_type / filename
    
    def load(self, strike: str, option_type: str, expiry_type: str) -> pd.DataFrame:
        """
        Load and cache parquet file
        
        Args:
            strike: 'ATM', 'ATM+1', 'ATM-5', etc.
            option_type: 'CE' or 'PE'
            expiry_type: 'WEEK' or 'MONTH'
        
        Returns:
            DataFrame with option data
        """
        cache_key = f"{expiry_type}_{strike}_{option_type}"
        
        if cache_key not in self._cache:
            file_path = self._get_file_path(strike, option_type, expiry_type)
            
            if not file_path.exists():
                raise FileNotFoundError(f"Data file not found: {file_path}")
            
            df = pd.read_parquet(file_path)
            
            # Ensure datetime is properly typed
            if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Convert date column to string format for consistent comparison
            if 'date' in df.columns:
                if df['date'].dtype == 'object' and len(df) > 0:
                    first_val = df['date'].iloc[0]
                    if hasattr(first_val, 'strftime'):
                        df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                    elif not isinstance(first_val, str):
                        df['date'] = df['date'].astype(str)
                elif df['date'].dtype != 'object':
                    df['date'] = df['date'].astype(str)
            
            # Add time column for filtering
            df['time'] = df['datetime'].dt.time
            
            # Sort by datetime
            df = df.sort_values('datetime').reset_index(drop=True)
            
            self._cache[cache_key] = df
        
        return self._cache[cache_key].copy()
    
    def slice_by_date(self, df: pd.DataFrame, 
                      start_date: str, end_date: str) -> pd.DataFrame:
        """
        Slice dataframe by date range
        
        Args:
            df: Source dataframe
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
        """
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        return df[mask].copy()
    
    def slice_by_time(self, df: pd.DataFrame,
                      start_time: str = "09:15",
                      end_time: str = "15:30") -> pd.DataFrame:
        """
        Slice dataframe by time window
        
        Args:
            df: Source dataframe
            start_time: 'HH:MM'
            end_time: 'HH:MM'
        """
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
        
        mask = (df['time'] >= start) & (df['time'] <= end)
        return df[mask].copy()
    
    def get_day_data(self, strike: str, option_type: str, 
                     expiry_type: str, date: str,
                     start_time: str = "09:15",
                     end_time: str = "15:30") -> pd.DataFrame:
        """
        Get data for a single trading day
        
        Args:
            strike, option_type, expiry_type: Instrument params
            date: 'YYYY-MM-DD'
            start_time, end_time: Time window
        """
        df = self.load(strike, option_type, expiry_type)
        df = self.slice_by_date(df, date, date)
        df = self.slice_by_time(df, start_time, end_time)
        return df
    
    def get_trading_days(self, expiry_type: str = "WEEK",
                         start_date: str = None, 
                         end_date: str = None) -> List[str]:
        """Get unique trading days in range"""
        # Load any file to get trading days (date is already string from load())
        df = self.load("ATM", "CE", expiry_type)
        
        if start_date:
            df = df[df['date'] >= start_date]
        if end_date:
            df = df[df['date'] <= end_date]
        
        return sorted(df['date'].unique().tolist())
    
    def get_date_range(self, expiry_type: str = "WEEK") -> tuple:
        """Get min and max dates available"""
        df = self.load("ATM", "CE", expiry_type)
        return df['date'].min(), df['date'].max()
    
    def clear_cache(self):
        """Clear the data cache"""
        self._cache.clear()
