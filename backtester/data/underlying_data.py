"""
Underlying Data Loader - Fetch Nifty 50 data from Yahoo Finance
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
import yfinance as yf


class UnderlyingDataLoader:
    """
    Loads Nifty 50 (underlying) data from Yahoo Finance.
    Caches data locally for faster backtesting.
    """
    
    NIFTY_SYMBOL = "^NSEI"  # Yahoo Finance symbol for Nifty 50
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "underlying_data"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self._data_cache: Optional[pd.DataFrame] = None
        self._datetime_index: Dict[datetime, float] = {}
    
    def download_data(self, start_date: str, end_date: str, 
                      interval: str = "1d") -> pd.DataFrame:
        """
        Download Nifty 50 data from Yahoo Finance
        
        Args:
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            interval: '1m', '5m', '15m', '1h', '1d' etc.
        
        Returns:
            DataFrame with OHLCV data
        """
        ticker = yf.Ticker(self.NIFTY_SYMBOL)
        
        # For intraday data, Yahoo limits to 7 days for 1m, 60 days for 1h
        # For daily data, we can get years of history
        df = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if df.empty:
            raise ValueError(f"No data found for {self.NIFTY_SYMBOL} from {start_date} to {end_date}")
        
        # Standardize column names
        df = df.reset_index()
        df.columns = df.columns.str.lower()
        
        # Handle datetime/date column
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
        elif 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'])
            df = df.drop(columns=['date'])
        
        # Add date column for filtering
        df['date'] = df['datetime'].dt.strftime('%Y-%m-%d')
        
        return df
    
    def load_daily_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Load daily Nifty 50 data (preferred for underlying-based SL/Target)
        
        Args:
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
        
        Returns:
            DataFrame with daily OHLCV
        """
        cache_file = self.cache_dir / f"nifty50_daily_{start_date}_{end_date}.parquet"
        
        # Check cache
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            df['datetime'] = pd.to_datetime(df['datetime'])
            return df
        
        # Download from Yahoo Finance
        print(f"Downloading Nifty 50 data from {start_date} to {end_date}...")
        df = self.download_data(start_date, end_date, interval="1d")
        
        # Save to cache
        df.to_parquet(cache_file, index=False)
        print(f"Cached to {cache_file}")
        
        return df
    
    def get_entry_price(self, date: str) -> Optional[float]:
        """
        Get the Nifty 50 opening/entry price for a given date.
        This is used as the reference for underlying-based SL/Target.
        
        Args:
            date: 'YYYY-MM-DD'
        
        Returns:
            Opening price of Nifty 50 on that date
        """
        if self._data_cache is None:
            return None
        
        day_data = self._data_cache[self._data_cache['date'] == date]
        if day_data.empty:
            return None
        
        return float(day_data.iloc[0]['open'])
    
    def get_price_at_time(self, timestamp: datetime) -> Optional[float]:
        """
        Get the Nifty 50 price at a specific timestamp.
        For daily data, returns the day's close price.
        
        Args:
            timestamp: datetime object
        
        Returns:
            Price at that time (or nearest available)
        """
        if self._data_cache is None:
            return None
        
        date_str = timestamp.strftime('%Y-%m-%d')
        day_data = self._data_cache[self._data_cache['date'] == date_str]
        
        if day_data.empty:
            return None
        
        # For daily data, return close (represents end of day)
        return float(day_data.iloc[0]['close'])
    
    def preload_data(self, start_date: str, end_date: str):
        """
        Preload data for a date range (call before backtesting)
        
        Args:
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
        """
        self._data_cache = self.load_daily_data(start_date, end_date)
        
        # Build datetime index for fast lookups
        self._datetime_index = {}
        for _, row in self._data_cache.iterrows():
            self._datetime_index[row['date']] = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close']
            }
    
    def get_day_ohlc(self, date: str) -> Optional[Dict[str, float]]:
        """
        Get OHLC for a specific date
        
        Args:
            date: 'YYYY-MM-DD'
        
        Returns:
            Dict with open, high, low, close
        """
        return self._datetime_index.get(date)
    
    def calculate_underlying_sl_hit(self, entry_date: str, entry_underlying: float,
                                     current_date: str, sl_points: Optional[float] = None,
                                     sl_percent: Optional[float] = None,
                                     action: str = "SELL") -> bool:
        """
        Check if underlying-based SL has been hit
        
        For SELL: SL hit when underlying moves UP by the specified amount
        For BUY: SL hit when underlying moves DOWN by the specified amount
        
        Args:
            entry_date: Entry date
            entry_underlying: Nifty 50 price at entry
            current_date: Current date to check
            sl_points: SL in absolute points
            sl_percent: SL in percentage
            action: "BUY" or "SELL"
        
        Returns:
            True if SL hit
        """
        ohlc = self.get_day_ohlc(current_date)
        if ohlc is None:
            return False
        
        if sl_points is not None:
            if action == "SELL":
                # Selling option = bullish on underlying
                # SL hit when underlying moves down
                sl_price = entry_underlying - sl_points
                return ohlc['low'] <= sl_price
            else:
                # Buying option = bearish on underlying (for puts) or bullish (for calls)
                sl_price = entry_underlying + sl_points
                return ohlc['high'] >= sl_price
        
        elif sl_percent is not None:
            if action == "SELL":
                sl_price = entry_underlying * (1 - sl_percent / 100)
                return ohlc['low'] <= sl_price
            else:
                sl_price = entry_underlying * (1 + sl_percent / 100)
                return ohlc['high'] >= sl_price
        
        return False
    
    def calculate_underlying_target_hit(self, entry_underlying: float,
                                         current_date: str, 
                                         target_points: Optional[float] = None,
                                         target_percent: Optional[float] = None,
                                         action: str = "SELL") -> bool:
        """
        Check if underlying-based target has been hit
        
        For SELL: Target hit when underlying moves DOWN (option premium decreases)
        For BUY: Target hit when underlying moves in favorable direction
        
        Args:
            entry_underlying: Nifty 50 price at entry
            current_date: Current date to check
            target_points: Target in absolute points
            target_percent: Target in percentage
            action: "BUY" or "SELL"
        
        Returns:
            True if target hit
        """
        ohlc = self.get_day_ohlc(current_date)
        if ohlc is None:
            return False
        
        if target_points is not None:
            if action == "SELL":
                # For selling, target when underlying moves up (for CE) or down (for PE)
                # Simplified: check if underlying moved by target points in any direction
                target_up = entry_underlying + target_points
                target_down = entry_underlying - target_points
                return ohlc['high'] >= target_up or ohlc['low'] <= target_down
            else:
                target_up = entry_underlying + target_points
                target_down = entry_underlying - target_points
                return ohlc['high'] >= target_up or ohlc['low'] <= target_down
        
        elif target_percent is not None:
            target_up = entry_underlying * (1 + target_percent / 100)
            target_down = entry_underlying * (1 - target_percent / 100)
            return ohlc['high'] >= target_up or ohlc['low'] <= target_down
        
        return False
