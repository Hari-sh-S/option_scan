"""
Leg Engine - State machine for individual option legs
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd


class LegState(Enum):
    """Leg lifecycle states"""
    CREATED = "created"       # Leg defined but not entered
    ENTERED = "entered"       # Entry order placed
    ACTIVE = "active"         # Position is live
    EXITED = "exited"         # Position closed


class LegAction(Enum):
    """Buy or Sell"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class LegConfig:
    """Configuration for a leg"""
    # Identity
    leg_id: int
    
    # Instrument
    strike: str              # "ATM", "ATM+1", "ATM-5"
    option_type: str         # "CE" or "PE"
    expiry_type: str         # "WEEK" or "MONTH"
    action: LegAction        # BUY or SELL
    lots: int = 1
    
    # Exit parameters - Option premium based
    sl_points: Optional[float] = None           # SL in absolute points on premium
    sl_percent: Optional[float] = None          # SL in % of premium
    target_points: Optional[float] = None       # Target in absolute points on premium
    target_percent: Optional[float] = None      # Target in % of premium
    
    # Exit parameters - Underlying (Nifty 50) based
    sl_underlying_points: Optional[float] = None       # SL based on Nifty movement in points
    sl_underlying_percent: Optional[float] = None      # SL based on Nifty % movement
    target_underlying_points: Optional[float] = None   # Target based on Nifty movement in points
    target_underlying_percent: Optional[float] = None  # Target based on Nifty % movement
    
    # Trailing SL
    trailing_sl: bool = False
    trail_type: str = "points"                  # "points" or "percent"
    trail_activate_points: Optional[float] = None  # Profit to activate trailing (points)
    trail_activate_percent: Optional[float] = None # Profit to activate trailing (percent)
    trail_lock_points: Optional[float] = None      # Profit to lock (points)
    trail_lock_percent: Optional[float] = None     # Profit to lock (percent)
    
    def get_sl_price(self, entry_price: float) -> Optional[float]:
        """Calculate SL price based on option premium"""
        if self.sl_points is not None:
            if self.action == LegAction.BUY:
                return entry_price - self.sl_points
            else:
                return entry_price + self.sl_points
        elif self.sl_percent is not None:
            if self.action == LegAction.BUY:
                return entry_price * (1 - self.sl_percent / 100)
            else:
                return entry_price * (1 + self.sl_percent / 100)
        return None
    
    def get_target_price(self, entry_price: float) -> Optional[float]:
        """Calculate target price based on option premium"""
        if self.target_points is not None:
            if self.action == LegAction.BUY:
                return entry_price + self.target_points
            else:
                return entry_price - self.target_points
        elif self.target_percent is not None:
            if self.action == LegAction.BUY:
                return entry_price * (1 + self.target_percent / 100)
            else:
                return entry_price * (1 - self.target_percent / 100)
        return None
    
    def has_underlying_sl(self) -> bool:
        """Check if SL is based on underlying movement"""
        return self.sl_underlying_points is not None or self.sl_underlying_percent is not None
    
    def has_underlying_target(self) -> bool:
        """Check if target is based on underlying movement"""
        return self.target_underlying_points is not None or self.target_underlying_percent is not None


@dataclass
class Leg:
    """
    Represents a single option leg in a strategy.
    Manages its own state machine and P&L calculations.
    """
    config: LegConfig
    lot_size: int = 50  # NIFTY lot size
    
    # State
    state: LegState = field(default=LegState.CREATED)
    
    # Entry details
    entry_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    
    # Exit details
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    
    # Current position tracking
    current_price: float = 0.0
    current_sl: Optional[float] = None
    peak_profit: float = 0.0  # For trailing SL
    
    def enter(self, price: float, timestamp: datetime, slippage_pct: float = 0.0):
        """
        Enter the position
        
        Args:
            price: Entry price
            timestamp: Entry time
            slippage_pct: Slippage percentage to apply
        """
        if self.state != LegState.CREATED:
            raise ValueError(f"Cannot enter leg in state {self.state}")
        
        # Apply slippage (worse price for us)
        if self.config.action == LegAction.BUY:
            self.entry_price = price * (1 + slippage_pct / 100)
        else:
            self.entry_price = price * (1 - slippage_pct / 100)
        
        self.entry_time = timestamp
        self.state = LegState.ACTIVE
        
        # Set initial SL
        self.current_sl = self.config.get_sl_price(self.entry_price)
    
    def exit(self, price: float, timestamp: datetime, reason: str, 
             slippage_pct: float = 0.0):
        """
        Exit the position
        
        Args:
            price: Exit price
            timestamp: Exit time
            reason: Why exited (SL, TARGET, TIME, STRATEGY_SL, etc.)
            slippage_pct: Slippage percentage
        """
        if self.state != LegState.ACTIVE:
            raise ValueError(f"Cannot exit leg in state {self.state}")
        
        # Apply slippage (worse price for us)
        if self.config.action == LegAction.BUY:
            self.exit_price = price * (1 - slippage_pct / 100)
        else:
            self.exit_price = price * (1 + slippage_pct / 100)
        
        self.exit_time = timestamp
        self.exit_reason = reason
        self.state = LegState.EXITED
    
    def update(self, candle: pd.Series) -> Optional[str]:
        """
        Update leg with current candle and check for exits.
        
        Args:
            candle: Current candle with OHLC data
        
        Returns:
            Exit reason if should exit, None otherwise
        """
        if self.state != LegState.ACTIVE:
            return None
        
        self.current_price = candle['close']
        
        # Check SL and Target using OHLC
        exit_reason = self._check_sl_target(candle)
        if exit_reason:
            return exit_reason
        
        # Update trailing SL if enabled
        if self.config.trailing_sl:
            self._update_trailing_sl()
        
        return None
    
    def _check_sl_target(self, candle: pd.Series) -> Optional[str]:
        """
        Check if SL or Target hit using OHLC logic.
        
        For correct order of checking within a candle:
        - BUY: Check Low first (SL), then High (Target)
        - SELL: Check High first (SL), then Low (Target)
        """
        target_price = self.config.get_target_price(self.entry_price)
        
        if self.config.action == LegAction.BUY:
            # BUY: SL below entry, Target above
            # Check SL first (price going down)
            if self.current_sl and candle['low'] <= self.current_sl:
                return "SL"
            # Then check Target (price going up)
            if target_price and candle['high'] >= target_price:
                return "TARGET"
        else:
            # SELL: SL above entry, Target below
            # Check SL first (price going up)
            if self.current_sl and candle['high'] >= self.current_sl:
                return "SL"
            # Then check Target (price going down)
            if target_price and candle['low'] <= target_price:
                return "TARGET"
        
        return None
    
    def _update_trailing_sl(self):
        """Update trailing stop loss"""
        if not self.config.trailing_sl:
            return
        
        if not self.config.trail_activate_points or not self.config.trail_lock_points:
            return
        
        current_pnl_points = self.get_unrealized_pnl_points()
        
        # Update peak profit
        if current_pnl_points > self.peak_profit:
            self.peak_profit = current_pnl_points
        
        # Check if trailing should activate
        if self.peak_profit >= self.config.trail_activate_points:
            # Calculate new SL to lock in profit
            lock_points = self.config.trail_lock_points
            
            if self.config.action == LegAction.BUY:
                new_sl = self.entry_price + lock_points
            else:
                new_sl = self.entry_price - lock_points
            
            # Only move SL in favorable direction
            if self.config.action == LegAction.BUY:
                if self.current_sl is None or new_sl > self.current_sl:
                    self.current_sl = new_sl
            else:
                if self.current_sl is None or new_sl < self.current_sl:
                    self.current_sl = new_sl
    
    def get_unrealized_pnl_points(self) -> float:
        """Get unrealized P&L in points"""
        if self.entry_price is None:
            return 0.0
        
        if self.config.action == LegAction.BUY:
            return self.current_price - self.entry_price
        else:
            return self.entry_price - self.current_price
    
    def get_unrealized_pnl(self) -> float:
        """Get unrealized P&L in rupees"""
        points = self.get_unrealized_pnl_points()
        return points * self.config.lots * self.lot_size
    
    def get_realized_pnl_points(self) -> float:
        """Get realized P&L in points (after exit)"""
        if self.state != LegState.EXITED:
            return 0.0
        
        if self.config.action == LegAction.BUY:
            return self.exit_price - self.entry_price
        else:
            return self.entry_price - self.exit_price
    
    def get_realized_pnl(self) -> float:
        """Get realized P&L in rupees"""
        points = self.get_realized_pnl_points()
        return points * self.config.lots * self.lot_size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "leg_id": self.config.leg_id,
            "strike": self.config.strike,
            "option_type": self.config.option_type,
            "expiry_type": self.config.expiry_type,
            "action": self.config.action.value,
            "lots": self.config.lots,
            "state": self.state.value,
            "entry_price": self.entry_price,
            "entry_time": str(self.entry_time) if self.entry_time else None,
            "exit_price": self.exit_price,
            "exit_time": str(self.exit_time) if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "pnl_points": self.get_realized_pnl_points() if self.state == LegState.EXITED else self.get_unrealized_pnl_points(),
            "pnl": self.get_realized_pnl() if self.state == LegState.EXITED else self.get_unrealized_pnl()
        }
