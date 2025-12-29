"""
Strategy Engine - Multi-leg strategy coordinator
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, time
import pandas as pd

from .leg import Leg, LegState, LegConfig


class StrategyMode(Enum):
    """Strategy execution modes"""
    INTRADAY = "INTRADAY"       # Square off same day
    BTST = "BTST"               # Buy Today Sell Tomorrow
    POSITIONAL = "POSITIONAL"   # Hold for multiple days


@dataclass
class StrategyConfig:
    """Strategy-level configuration"""
    name: str = "Unnamed Strategy"
    mode: StrategyMode = StrategyMode.INTRADAY
    
    # Entry settings
    entry_time: str = "09:20"
    no_entry_after: str = "14:30"
    
    # Exit settings
    exit_time: str = "15:15"
    
    # Strategy-level risk (takes precedence over leg-level)
    max_loss: Optional[float] = None      # In rupees
    max_profit: Optional[float] = None    # In rupees
    
    # Re-entry settings
    reentry_on_sl: int = 0     # Number of re-entries allowed after SL
    reentry_on_target: int = 0  # Number of re-entries after target
    
    def get_entry_time(self) -> time:
        return datetime.strptime(self.entry_time, "%H:%M").time()
    
    def get_exit_time(self) -> time:
        return datetime.strptime(self.exit_time, "%H:%M").time()
    
    def get_no_entry_after_time(self) -> time:
        return datetime.strptime(self.no_entry_after, "%H:%M").time()


@dataclass 
class Strategy:
    """
    Multi-leg strategy coordinator.
    Manages entry, exit, and risk at strategy level.
    """
    config: StrategyConfig
    legs: List[Leg] = field(default_factory=list)
    
    # State
    is_active: bool = True
    entered_today: bool = False
    exited_today: bool = False
    
    # Re-entry tracking
    sl_reentries_used: int = 0
    target_reentries_used: int = 0
    
    # Statistics
    day_pnl: float = 0.0
    total_pnl: float = 0.0
    
    def add_leg(self, leg_config: LegConfig) -> Leg:
        """Add a leg to the strategy"""
        leg = Leg(config=leg_config)
        self.legs.append(leg)
        return leg
    
    def get_active_legs(self) -> List[Leg]:
        """Get all active legs"""
        return [leg for leg in self.legs if leg.state == LegState.ACTIVE]
    
    def get_total_unrealized_pnl(self) -> float:
        """Get combined unrealized P&L of all active legs"""
        return sum(leg.get_unrealized_pnl() for leg in self.get_active_legs())
    
    def get_total_realized_pnl(self) -> float:
        """Get combined realized P&L of all exited legs"""
        return sum(leg.get_realized_pnl() for leg in self.legs 
                   if leg.state == LegState.EXITED)
    
    def get_total_pnl(self) -> float:
        """Get total P&L (realized + unrealized)"""
        return self.get_total_realized_pnl() + self.get_total_unrealized_pnl()
    
    def should_enter(self, current_time: time) -> bool:
        """Check if strategy should enter now"""
        if not self.is_active:
            return False
        if self.entered_today:
            return False
        if current_time < self.config.get_entry_time():
            return False
        if current_time > self.config.get_no_entry_after_time():
            return False
        return True
    
    def should_exit_time(self, current_time: time) -> bool:
        """Check if time-based exit should trigger"""
        # Positional doesn't use time-based exit
        if self.config.mode == StrategyMode.POSITIONAL:
            return False
        # BTST: Only exit at exit_time if positions were from a PREVIOUS day
        # (i.e., don't exit same day as entry)
        if self.config.mode == StrategyMode.BTST:
            # If we entered today, skip exit - wait for next day
            if self.entered_today:
                return False
            # Positions from previous day - check exit time
            return current_time >= self.config.get_exit_time()
        # Intraday: exit at exit_time same day
        return current_time >= self.config.get_exit_time()
    
    def check_strategy_sl(self) -> bool:
        """Check if strategy-level SL hit"""
        if self.config.max_loss is None:
            return False
        return self.get_total_pnl() <= -abs(self.config.max_loss)
    
    def check_strategy_target(self) -> bool:
        """Check if strategy-level target hit"""
        if self.config.max_profit is None:
            return False
        return self.get_total_pnl() >= self.config.max_profit
    
    def enter_all_legs(self, candle_data: Dict[str, pd.Series], 
                       timestamp: datetime, slippage_pct: float = 0.0):
        """
        Enter all legs at current prices
        
        Args:
            candle_data: Dict mapping leg_id to current candle
            timestamp: Entry time
            slippage_pct: Slippage percentage
        """
        for leg in self.legs:
            if leg.state == LegState.CREATED:
                candle = candle_data.get(leg.config.leg_id)
                if candle is not None:
                    entry_price = candle['close']  # Enter at close of entry candle
                    leg.enter(entry_price, timestamp, slippage_pct)
        
        self.entered_today = True
    
    def exit_all_legs(self, candle_data: Dict[str, pd.Series],
                      timestamp: datetime, reason: str,
                      slippage_pct: float = 0.0):
        """
        Exit all active legs
        
        Args:
            candle_data: Dict mapping leg_id to current candle
            timestamp: Exit time
            reason: Exit reason
            slippage_pct: Slippage percentage
        """
        for leg in self.get_active_legs():
            candle = candle_data.get(leg.config.leg_id)
            if candle is not None:
                exit_price = candle['close']
                leg.exit(exit_price, timestamp, reason, slippage_pct)
        
        self.exited_today = True
        self.day_pnl = self.get_total_realized_pnl()
    
    def update_legs(self, candle_data: Dict[str, pd.Series],
                    timestamp: datetime, slippage_pct: float = 0.0) -> List[tuple]:
        """
        Update all legs with current candles and process exits
        
        Args:
            candle_data: Dict mapping leg_id to current candle
            timestamp: Current time
            slippage_pct: Slippage percentage
        
        Returns:
            List of (leg, exit_reason) for legs that exited
        """
        exits = []
        
        for leg in self.get_active_legs():
            candle = candle_data.get(leg.config.leg_id)
            if candle is not None:
                exit_reason = leg.update(candle)
                if exit_reason:
                    # Determine exit price based on reason
                    if exit_reason == "SL":
                        exit_price = leg.current_sl
                    elif exit_reason == "TARGET":
                        exit_price = leg.config.get_target_price(leg.entry_price)
                    else:
                        exit_price = candle['close']
                    
                    leg.exit(exit_price, timestamp, exit_reason, slippage_pct)
                    exits.append((leg, exit_reason))
        
        return exits
    
    def reset_for_new_day(self):
        """Reset state for a new trading day"""
        self.entered_today = False
        self.exited_today = False
        self.day_pnl = 0.0
        
        # Reset legs for new day (create fresh copies)
        new_legs = []
        for leg in self.legs:
            new_leg = Leg(
                config=leg.config,
                lot_size=leg.lot_size
            )
            new_legs.append(new_leg)
        self.legs = new_legs
    
    def reset_daily_flags(self):
        """
        Reset only daily flags without resetting legs.
        Used for BTST/Positional modes where positions carry over.
        """
        self.entered_today = False
        self.exited_today = False
        self.day_pnl = 0.0
    
    def can_reenter_sl(self) -> bool:
        """Check if re-entry on SL is allowed"""
        return self.sl_reentries_used < self.config.reentry_on_sl
    
    def can_reenter_target(self) -> bool:
        """Check if re-entry on target is allowed"""
        return self.target_reentries_used < self.config.reentry_on_target
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy state to dictionary"""
        return {
            "name": self.config.name,
            "mode": self.config.mode.value,
            "is_active": self.is_active,
            "total_pnl": self.get_total_pnl(),
            "realized_pnl": self.get_total_realized_pnl(),
            "unrealized_pnl": self.get_total_unrealized_pnl(),
            "legs": [leg.to_dict() for leg in self.legs]
        }
