"""
Data Loader - Downloads data from Hugging Face and provides cached access
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, time
import os

# Try to import huggingface_hub, install if not present
try:
    from huggingface_hub import hf_hub_download, snapshot_download
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'huggingface_hub'])
    from huggingface_hub import hf_hub_download, snapshot_download


class DataLoader:
    """Cached parquet reader with Hugging Face download support"""
    
    # Hugging Face dataset configuration
    # UPDATE THIS with your actual dataset name after uploading
    HF_DATASET_REPO = "artist-23/nifty-options-data"  # Hugging Face dataset
    
    def __init__(self, data_dir: Path = None):
        # Use local cache directory
        if data_dir is None:
            # Check if we're on Streamlit Cloud (no historical_data folder)
            local_data = Path(__file__).parent.parent.parent / "historical_data" / "NIFTY"
            if local_data.exists() and any(local_data.glob("**/*.parquet")):
                # Local data exists, use it
                self.data_dir = local_data
                self.use_hf = False
            else:
                # No local data, use Hugging Face
                self.data_dir = Path.home() / ".cache" / "nifty_options_data" / "NIFTY"
                self.use_hf = True
        else:
            self.data_dir = data_dir / "NIFTY" if "NIFTY" not in str(data_dir) else data_dir
            self.use_hf = not self.data_dir.exists()
        
        self._cache: Dict[str, pd.DataFrame] = {}
        self._hf_downloaded = False
    
    def _ensure_data_downloaded(self):
        """Download data from Hugging Face if needed"""
        if not self.use_hf or self._hf_downloaded:
            return
        
        # Check if already cached
        week_dir = self.data_dir / "WEEK"
        if week_dir.exists() and any(week_dir.glob("*.parquet")):
            self._hf_downloaded = True
            return
        
        print(f"Downloading data from Hugging Face: {self.HF_DATASET_REPO}")
        print("This may take a few minutes on first run...")
        
        try:
            # Download entire dataset
            cache_dir = self.data_dir.parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"Downloading to: {cache_dir}")
            
            snapshot_download(
                repo_id=self.HF_DATASET_REPO,
                repo_type="dataset",
                local_dir=cache_dir,
                local_dir_use_symlinks=False
            )
            
            # Verify download
            week_dir = self.data_dir / "WEEK"
            month_dir = self.data_dir / "MONTH"
            
            if week_dir.exists():
                week_files = list(week_dir.glob("*.parquet"))
                print(f"Download complete! Found {len(week_files)} WEEK files")
            else:
                print(f"WARNING: WEEK directory not found at {week_dir}")
                # Try to find where files actually are
                for p in cache_dir.rglob("*.parquet"):
                    print(f"  Found parquet: {p}")
                    break  # Just show first one
            
            self._hf_downloaded = True
        except Exception as e:
            print(f"Error downloading from Hugging Face: {e}")
            print("Please ensure the dataset exists and is accessible.")
            raise
    
    def _get_file_path(self, strike: str, option_type: str, expiry_type: str) -> Path:
        """Get parquet file path for given parameters"""
        self._ensure_data_downloaded()
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
            
            # CRITICAL: Convert UTC to IST (Dhan API provides data in UTC)
            # IST = UTC + 5:30
            df['datetime'] = df['datetime'] + pd.Timedelta(hours=5, minutes=30)
            
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
            
            # Add time column for filtering (now in IST)
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
            start_time: 'HH:MM' in IST (Indian Standard Time)
            end_time: 'HH:MM' in IST
            
        Note: Historical data is stored in UTC. This method converts
        IST input times to UTC for proper filtering.
        IST = UTC + 5:30, so UTC = IST - 5:30
        """
        from datetime import timedelta
        
        # Parse IST times
        start_ist = datetime.strptime(start_time, "%H:%M")
        end_ist = datetime.strptime(end_time, "%H:%M")
        
        # Convert IST to UTC (subtract 5:30)
        ist_offset = timedelta(hours=5, minutes=30)
        start_utc = (start_ist - ist_offset).time()
        end_utc = (end_ist - ist_offset).time()
        
        mask = (df['time'] >= start_utc) & (df['time'] <= end_utc)
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
