"""
Monte Carlo Risk Module - Trade return resampling simulation
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from engine.backtest import BacktestResult


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results"""
    num_simulations: int
    
    # Drawdown stats
    max_drawdown_95: float
    max_drawdown_median: float
    max_drawdown_5: float
    
    # Streak stats
    worst_losing_streak_95: int
    worst_losing_streak_median: int
    
    # Return distribution
    final_pnl_median: float
    final_pnl_5th: float
    final_pnl_95th: float
    
    # CAGR distribution (if applicable)
    cagr_median: float
    cagr_5th: float
    
    # Risk of ruin
    probability_of_ruin: float  # Probability of losing X% of capital
    ruin_threshold_pct: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to display dictionary"""
        return {
            "Simulations": f"{self.num_simulations:,}",
            "Max Drawdown (95%)": f"₹{self.max_drawdown_95:,.2f}",
            "Max Drawdown (Median)": f"₹{self.max_drawdown_median:,.2f}",
            "Worst Losing Streak (95%)": self.worst_losing_streak_95,
            "Final P&L (Median)": f"₹{self.final_pnl_median:,.2f}",
            "Final P&L (5th %)": f"₹{self.final_pnl_5th:,.2f}",
            "Final P&L (95th %)": f"₹{self.final_pnl_95th:,.2f}",
            "CAGR (Median)": f"{self.cagr_median:.1f}%",
            "CAGR (5th %)": f"{self.cagr_5th:.1f}%",
            f"Prob. of Losing {self.ruin_threshold_pct}%": f"{self.probability_of_ruin:.1f}%"
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation for risk analysis.
    Resamples trade returns to estimate:
    - Worst-case drawdowns
    - Probability of ruin
    - Return distribution
    """
    
    def __init__(self, num_simulations: int = 10000, seed: int = None):
        self.num_simulations = num_simulations
        self.rng = np.random.default_rng(seed)
    
    def simulate(self, result: BacktestResult, 
                 initial_capital: float = 100000,
                 ruin_threshold_pct: float = 50) -> MonteCarloResult:
        """
        Run Monte Carlo simulation
        
        Args:
            result: Backtest result with trade data
            initial_capital: Starting capital for simulations
            ruin_threshold_pct: % loss considered as "ruin"
        
        Returns:
            MonteCarloResult with statistics
        """
        trades_df = result.to_trades_df()
        
        if trades_df.empty or len(trades_df) < 10:
            return self._empty_result(ruin_threshold_pct)
        
        # Get trade returns
        trade_returns = trades_df['net_pnl'].values
        num_trades = len(trade_returns)
        
        # Storage for simulation results
        all_max_drawdowns = []
        all_max_losing_streaks = []
        all_final_pnls = []
        ruin_count = 0
        
        ruin_threshold = initial_capital * (ruin_threshold_pct / 100)
        
        for _ in range(self.num_simulations):
            # Resample trades with replacement
            resampled = self.rng.choice(trade_returns, size=num_trades, replace=True)
            
            # Calculate equity curve
            equity = np.cumsum(resampled)
            equity_with_capital = initial_capital + equity
            
            # Calculate max drawdown
            peak = np.maximum.accumulate(equity_with_capital)
            drawdown = peak - equity_with_capital
            max_dd = drawdown.max()
            all_max_drawdowns.append(max_dd)
            
            # Calculate losing streak
            losing_streak = self._calculate_max_losing_streak(resampled)
            all_max_losing_streaks.append(losing_streak)
            
            # Final P&L
            final_pnl = equity[-1]
            all_final_pnls.append(final_pnl)
            
            # Check for ruin
            if equity_with_capital.min() < (initial_capital - ruin_threshold):
                ruin_count += 1
        
        # Calculate statistics
        max_dd_95 = np.percentile(all_max_drawdowns, 95)
        max_dd_median = np.percentile(all_max_drawdowns, 50)
        max_dd_5 = np.percentile(all_max_drawdowns, 5)
        
        streak_95 = int(np.percentile(all_max_losing_streaks, 95))
        streak_median = int(np.percentile(all_max_losing_streaks, 50))
        
        final_pnl_median = np.percentile(all_final_pnls, 50)
        final_pnl_5 = np.percentile(all_final_pnls, 5)
        final_pnl_95 = np.percentile(all_final_pnls, 95)
        
        # CAGR (simplified - assuming 1 year of trading)
        num_days = result.num_days
        years = max(num_days / 252, 0.1)  # At least 0.1 years
        
        cagr_values = []
        for final_pnl in all_final_pnls:
            total_return = (initial_capital + final_pnl) / initial_capital
            if total_return > 0:
                cagr = (total_return ** (1/years) - 1) * 100
                cagr_values.append(cagr)
            else:
                cagr_values.append(-100)
        
        cagr_median = np.percentile(cagr_values, 50)
        cagr_5 = np.percentile(cagr_values, 5)
        
        # Probability of ruin
        prob_ruin = (ruin_count / self.num_simulations) * 100
        
        return MonteCarloResult(
            num_simulations=self.num_simulations,
            max_drawdown_95=max_dd_95,
            max_drawdown_median=max_dd_median,
            max_drawdown_5=max_dd_5,
            worst_losing_streak_95=streak_95,
            worst_losing_streak_median=streak_median,
            final_pnl_median=final_pnl_median,
            final_pnl_5th=final_pnl_5,
            final_pnl_95th=final_pnl_95,
            cagr_median=cagr_median,
            cagr_5th=cagr_5,
            probability_of_ruin=prob_ruin,
            ruin_threshold_pct=ruin_threshold_pct
        )
    
    def _calculate_max_losing_streak(self, returns: np.ndarray) -> int:
        """Calculate maximum consecutive losing trades"""
        max_streak = 0
        current_streak = 0
        
        for ret in returns:
            if ret < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _empty_result(self, ruin_threshold: float) -> MonteCarloResult:
        """Return empty result for insufficient data"""
        return MonteCarloResult(
            num_simulations=0,
            max_drawdown_95=0, max_drawdown_median=0, max_drawdown_5=0,
            worst_losing_streak_95=0, worst_losing_streak_median=0,
            final_pnl_median=0, final_pnl_5th=0, final_pnl_95th=0,
            cagr_median=0, cagr_5th=0,
            probability_of_ruin=0, ruin_threshold_pct=ruin_threshold
        )
    
    def get_distribution_data(self, result: BacktestResult) -> Dict[str, np.ndarray]:
        """Get raw distribution data for plotting"""
        trades_df = result.to_trades_df()
        
        if trades_df.empty:
            return {}
        
        trade_returns = trades_df['net_pnl'].values
        num_trades = len(trade_returns)
        
        final_pnls = []
        max_drawdowns = []
        
        for _ in range(self.num_simulations):
            resampled = self.rng.choice(trade_returns, size=num_trades, replace=True)
            equity = np.cumsum(resampled)
            
            final_pnls.append(equity[-1])
            
            peak = np.maximum.accumulate(equity)
            drawdown = peak - equity
            max_drawdowns.append(drawdown.max())
        
        return {
            'final_pnls': np.array(final_pnls),
            'max_drawdowns': np.array(max_drawdowns)
        }
