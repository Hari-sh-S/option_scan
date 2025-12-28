"""
Strategy-Level Risk Management
"""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from engine.strategy import Strategy


@dataclass
class StrategyRiskConfig:
    """Strategy-level risk configuration"""
    max_loss: Optional[float] = None      # Maximum loss in rupees
    max_profit: Optional[float] = None    # Maximum profit in rupees
    
    # Re-entry settings
    reentry_on_sl: int = 0
    reentry_on_target: int = 0
    
    # Daily limits
    max_trades_per_day: int = 0  # 0 = unlimited


class StrategyRiskManager:
    """
    Manages strategy-level risk.
    
    PRECEDENCE RULES:
    1. Strategy SL/Target always overrides leg-level
    2. Time-based exit overrides leg-level
    3. Leg-level SL/Target processed after strategy checks
    """
    
    def __init__(self, config: StrategyRiskConfig = None):
        self.config = config or StrategyRiskConfig()
    
    def should_exit_strategy_sl(self, strategy: Strategy) -> bool:
        """Check if strategy-level SL hit"""
        if self.config.max_loss is None:
            return False
        
        total_pnl = strategy.get_total_pnl()
        return total_pnl <= -abs(self.config.max_loss)
    
    def should_exit_strategy_target(self, strategy: Strategy) -> bool:
        """Check if strategy-level target hit"""
        if self.config.max_profit is None:
            return False
        
        total_pnl = strategy.get_total_pnl()
        return total_pnl >= self.config.max_profit
    
    def can_reenter_after_sl(self, strategy: Strategy) -> bool:
        """Check if re-entry after SL is allowed"""
        if self.config.reentry_on_sl <= 0:
            return False
        return strategy.sl_reentries_used < self.config.reentry_on_sl
    
    def can_reenter_after_target(self, strategy: Strategy) -> bool:
        """Check if re-entry after target is allowed"""
        if self.config.reentry_on_target <= 0:
            return False
        return strategy.target_reentries_used < self.config.reentry_on_target
    
    def get_risk_status(self, strategy: Strategy) -> dict:
        """Get current risk status"""
        total_pnl = strategy.get_total_pnl()
        
        status = {
            "total_pnl": total_pnl,
            "max_loss_limit": self.config.max_loss,
            "max_profit_limit": self.config.max_profit,
            "sl_hit": self.should_exit_strategy_sl(strategy),
            "target_hit": self.should_exit_strategy_target(strategy),
        }
        
        if self.config.max_loss:
            status["loss_used_pct"] = min(100, abs(total_pnl / self.config.max_loss * 100)) if total_pnl < 0 else 0
        
        if self.config.max_profit:
            status["profit_used_pct"] = min(100, total_pnl / self.config.max_profit * 100) if total_pnl > 0 else 0
        
        return status
