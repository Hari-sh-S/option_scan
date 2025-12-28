"""
Leg-Level Risk Management
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from engine.leg import Leg, LegAction


@dataclass
class LegRiskConfig:
    """Risk configuration for a single leg"""
    # Stop Loss
    sl_points: Optional[float] = None
    sl_percent: Optional[float] = None
    
    # Target
    target_points: Optional[float] = None
    target_percent: Optional[float] = None
    
    # Trailing SL
    trailing_sl: bool = False
    trail_activate_points: Optional[float] = None
    trail_lock_points: Optional[float] = None


class LegRiskManager:
    """Manages risk for individual legs"""
    
    @staticmethod
    def calculate_sl_price(entry_price: float, action: LegAction,
                          sl_points: float = None, 
                          sl_percent: float = None) -> Optional[float]:
        """Calculate stop loss price"""
        if sl_points is not None:
            if action == LegAction.BUY:
                return entry_price - sl_points
            else:
                return entry_price + sl_points
        elif sl_percent is not None:
            if action == LegAction.BUY:
                return entry_price * (1 - sl_percent / 100)
            else:
                return entry_price * (1 + sl_percent / 100)
        return None
    
    @staticmethod
    def calculate_target_price(entry_price: float, action: LegAction,
                              target_points: float = None,
                              target_percent: float = None) -> Optional[float]:
        """Calculate target price"""
        if target_points is not None:
            if action == LegAction.BUY:
                return entry_price + target_points
            else:
                return entry_price - target_points
        elif target_percent is not None:
            if action == LegAction.BUY:
                return entry_price * (1 + target_percent / 100)
            else:
                return entry_price * (1 - target_percent / 100)
        return None
    
    @staticmethod
    def is_sl_hit(current_low: float, current_high: float,
                  sl_price: float, action: LegAction) -> bool:
        """Check if SL is hit based on OHLC"""
        if sl_price is None:
            return False
        
        if action == LegAction.BUY:
            # For BUY, SL is below - check if low touched it
            return current_low <= sl_price
        else:
            # For SELL, SL is above - check if high touched it
            return current_high >= sl_price
    
    @staticmethod
    def is_target_hit(current_low: float, current_high: float,
                     target_price: float, action: LegAction) -> bool:
        """Check if target is hit based on OHLC"""
        if target_price is None:
            return False
        
        if action == LegAction.BUY:
            # For BUY, target is above - check if high touched it
            return current_high >= target_price
        else:
            # For SELL, target is below - check if low touched it
            return current_low <= target_price
    
    @staticmethod
    def calculate_trailing_sl(entry_price: float, current_price: float,
                             current_sl: float, action: LegAction,
                             trail_activate: float, trail_lock: float,
                             peak_profit: float) -> tuple:
        """
        Calculate trailing stop loss
        
        Returns:
            (new_sl, new_peak_profit)
        """
        # Calculate current profit
        if action == LegAction.BUY:
            current_profit = current_price - entry_price
        else:
            current_profit = entry_price - current_price
        
        # Update peak profit
        new_peak = max(peak_profit, current_profit)
        
        # Check if should activate trailing
        if new_peak < trail_activate:
            return current_sl, new_peak
        
        # Calculate new SL to lock profit
        if action == LegAction.BUY:
            new_sl = entry_price + trail_lock
            # Only move SL up, never down
            if current_sl is None or new_sl > current_sl:
                return new_sl, new_peak
        else:
            new_sl = entry_price - trail_lock
            # Only move SL down, never up
            if current_sl is None or new_sl < current_sl:
                return new_sl, new_peak
        
        return current_sl, new_peak
